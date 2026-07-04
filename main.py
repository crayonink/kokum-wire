"""
KOKUM WIRE — backend (Layers 2 & 3)

Layer 3: SQLite signal ledger. Every row is dated twice:
         observed_date (when it happened in the world) and
         logged_at (immutable — when WE recorded it; the track record).
Layer 2: /ask — retrieves ledger rows relevant to the question and has
         Claude compose a dispatch STRICTLY from those rows.

Run locally:
    uvicorn main:app --reload --port 8000
Environment:
    ANTHROPIC_API_KEY   optional — without it /ask degrades to a non-LLM
                        composed answer (fine for local testing)
    LEDGER_WRITE_KEY    required to POST /signals (defaults to "changeme")
    DB_PATH             defaults to ./ledger.db
"""

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "ledger.db"))
WRITE_KEY = os.environ.get("LEDGER_WRITE_KEY", "changeme")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("KOKUM_MODEL", "claude-sonnet-5")

VERDICTS = ["CLEAR", "WATCH", "CONCERN", "DOUBTFUL"]

app = FastAPI(title="Kokum Wire", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your domain once deployed
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# Layer 3 — the ledger
# ----------------------------------------------------------------------
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at     TEXT NOT NULL,          -- immutable, set by server
                observed_date TEXT NOT NULL,          -- YYYY-MM-DD, when it happened
                entity        TEXT NOT NULL,          -- e.g. 'Intel Magdeburg', 'TSMC CoWoS'
                signal_type   TEXT NOT NULL,          -- capex_cut, equipment_absence, hiring,
                                                      -- subsidy, customs, allocation, other
                severity      INTEGER NOT NULL,       -- 1 (noise) .. 5 (alarm)
                note          TEXT NOT NULL,          -- one-line interpretation
                source        TEXT NOT NULL,          -- e.g. 'Intel Q1 2023 earnings call'
                source_url    TEXT DEFAULT '',
                tags          TEXT DEFAULT '',        -- comma-separated: 'intel,fab,europe,mcu'
                verdict_horizon TEXT DEFAULT ''       -- YYYY-MM-DD by which a forward call
                                                      -- can be scored true/false ('' = not a call)
            )
            """
        )
        # Idempotent migration: add verdict_horizon to a pre-existing table.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(signals)")}
        if "verdict_horizon" not in cols:
            conn.execute("ALTER TABLE signals ADD COLUMN verdict_horizon TEXT DEFAULT ''")


init_db()


class SignalIn(BaseModel):
    observed_date: str = Field(..., description="YYYY-MM-DD")
    entity: str
    signal_type: str
    severity: int = Field(..., ge=1, le=5)
    note: str
    source: str
    source_url: str = ""
    tags: str = ""
    verdict_horizon: str = Field(
        "", description="YYYY-MM-DD by which this call can be scored true/false; blank if not a forward call"
    )


class AskIn(BaseModel):
    question: str = ""


def insert_signal(s: SignalIn) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO signals
               (logged_at, observed_date, entity, signal_type, severity,
                note, source, source_url, tags, verdict_horizon)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                s.observed_date,
                s.entity.strip(),
                s.signal_type.strip(),
                s.severity,
                s.note.strip(),
                s.source.strip(),
                s.source_url.strip(),
                s.tags.strip().lower(),
                s.verdict_horizon.strip(),
            ),
        )
        return cur.lastrowid


STOPWORDS = {
    "what", "whats", "what's", "new", "the", "in", "on", "for", "with",
    "is", "are", "of", "a", "an", "any", "latest", "update", "updates",
    "news", "about", "tell", "me", "and", "to", "how",
    # question filler that shouldn't drive matching
    "there", "was", "were", "be", "been", "being", "has", "have", "had",
    "do", "does", "did", "we", "you", "i", "it", "its", "it's", "this",
    "that", "these", "those", "get", "getting", "got", "will", "would",
    "when", "where", "who", "which", "why", "going", "happening", "happen",
    "going", "at", "as", "by", "or", "from", "up", "out", "now", "still",
    "going", "anything", "something",
}

# Domain synonyms: a query term also matches rows that use these words. This
# lets natural questions ('is there a NAND shortage?') hit rows that phrase the
# same idea differently ('sold out', 'half to two-thirds', 'allocation').
SYNONYMS = {
    "shortage": ["tight", "tightness", "sold out", "short of demand",
                 "constrained", "allocation", "scarce", "crunch", "sold"],
    "shortages": ["tight", "sold out", "allocation", "crunch"],
    "tight": ["shortage", "sold out", "allocation", "constrained"],
    "allocation": ["allocated", "sold out", "lockout", "quota", "fulfil",
                   "fulfill", "sold"],
    "price": ["cost", "asp", "pricing", "contract price"],
    "prices": ["cost", "costs", "asp", "pricing"],
    "pricing": ["cost", "price", "asp"],
    "cost": ["price", "pricing", "asp"],
    "memory": ["dram", "nand", "hbm", "ddr5", "flash"],
    "supply": ["capacity", "wafer", "bit-supply"],
    "capacity": ["supply", "wafer", "fab"],
    "automotive": ["auto", "car", "vehicle", "mcu", "embedded"],
    "recover": ["relief", "recovery", "ease", "normalize"],
    "recovery": ["relief", "recover", "ease"],
    "shortfall": ["shortage", "short of demand"],
    "flash": ["nand", "ssd"],
    "oem": ["dell", "cisco", "hp", "lenovo", "server", "pc"],
}


def retrieve(question: str, limit: int = 25) -> list[dict]:
    """Keyword retrieval over entity / note / tags / signal_type, with synonym
    expansion. Empty or generic question ("what's new?") -> most recent signals."""
    words = [
        w for w in re.findall(r"[a-z0-9']+", question.lower())
        if w not in STOPWORDS and len(w) > 1
    ]
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY observed_date DESC, id DESC"
        ).fetchall()

    if not words:
        return [dict(r) for r in rows[:limit]]

    # For each query word, the set of terms that count as a hit (the word plus
    # its synonyms). A row scores 1 per query word for which ANY of its terms
    # appears in the haystack.
    term_sets = [[w] + SYNONYMS.get(w, []) for w in words]

    scored = []
    for r in rows:
        haystack = " ".join(
            [r["entity"], r["note"], r["tags"], r["signal_type"]]
        ).lower()
        score = sum(1 for terms in term_sets if any(t in haystack for t in terms))
        if score >= 1:  # any strong term matches; ranking floats the best rows up
            scored.append((score, dict(r)))
    # Highest score first; within an equal score, most recent observation first.
    scored.sort(key=lambda t: (t[0], t[1]["observed_date"]), reverse=True)
    return [r for _, r in scored[:limit]]


# ----------------------------------------------------------------------
# Layer 2 — the answering brain
# ----------------------------------------------------------------------
SYSTEM_PROMPT = """You are the dispatch writer for KOKUM WIRE, a semiconductor
supply chain intelligence service read by procurement leaders and commodity
managers.

You will receive a question and a set of LEDGER SIGNALS (dated observations
logged by an analyst). Rules, absolute:

1. Answer ONLY from the provided signals. No outside knowledge, no training
   data, no speculation beyond what the signals support.
2. Cite the observed date of every claim inline, e.g. (27 Apr 2023).
3. If the signals do not cover the question, say plainly that the ledger has
   no entries on it yet — do not improvise.
4. Voice: terse wire-dispatch style. Short declarative sentences. Lead with
   the verdict-relevant facts. No pleasantries, no hedging filler. Plain
   words a commodity manager respects.
5. Choose ONE verdict for the question's subject:
   CLEAR (no adverse signals), WATCH (early smoke), CONCERN (multiple
   corroborating adverse signals), DOUBTFUL (evidence points to disruption,
   delay, or cancellation).
6. Reply with ONLY a JSON object, no markdown fences, exactly:
   {"verdict": "...", "answer": "..."}
   The answer may use \\n\\n for paragraph breaks. 120-220 words."""


def compose_with_claude(question: str, signals: list[dict]) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    signal_lines = "\n".join(
        f"- observed {s['observed_date']} | {s['entity']} | {s['signal_type']} "
        f"| severity {s['severity']}/5 | {s['note']} | source: {s['source']}"
        for s in signals
    )
    q = question or "What's new?"
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"QUESTION: {q}\n\nLEDGER SIGNALS:\n{signal_lines}",
            }
        ],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Tolerate a stray preamble/suffix: pull the outermost JSON object.
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        data = json.loads(m.group(0))
    if data.get("verdict") not in VERDICTS:
        data["verdict"] = "WATCH"
    if not data.get("answer"):
        raise ValueError("LLM response missing 'answer'")
    return data


def compose_fallback(question: str, signals: list[dict]) -> dict:
    """No API key: deterministic composition so the loop is testable."""
    if not signals:
        return {
            "verdict": "CLEAR",
            "answer": "The ledger has no entries matching this question yet. "
            "Scope it to a company, fab, or part family and transmit again.",
        }
    max_sev = max(s["severity"] for s in signals)
    verdict = (
        "DOUBTFUL" if max_sev >= 5
        else "CONCERN" if max_sev == 4
        else "WATCH" if max_sev == 3
        else "CLEAR"
    )
    entities = sorted({s["entity"] for s in signals})
    lines = [f"{', '.join(entities).upper()} — {len(signals)} signal(s) on ledger.", ""]
    for s in signals[:6]:
        try:
            d = datetime.strptime(s["observed_date"], "%Y-%m-%d").strftime("%d %b %Y")
        except ValueError:
            d = s["observed_date"]
        lines.append(f"({d}) {s['note']} — {s['source']}.")
    lines += ["", "[Composed without LLM — set ANTHROPIC_API_KEY for full dispatches.]"]
    return {"verdict": verdict, "answer": "\n".join(lines)}


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@app.post("/ask")
def ask(body: AskIn):
    signals = retrieve(body.question)
    if ANTHROPIC_API_KEY:
        try:
            composed = compose_with_claude(body.question, signals)
        except Exception as e:
            # Log WHY we fell back so it shows in the server/Railway logs —
            # a set-but-broken key (bad model, no quota, parse error) otherwise
            # degrades silently to the "[Composed without LLM]" fallback.
            print(f"[/ask] LLM compose failed, using fallback: "
                  f"{type(e).__name__}: {e}", flush=True)
            composed = compose_fallback(body.question, signals)
    else:
        composed = compose_fallback(body.question, signals)

    def fmt_date(d: str) -> str:
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return d

    return {
        "verdict": composed["verdict"],
        "answer": composed["answer"],
        "signals": [
            {
                "date": fmt_date(s["observed_date"]),
                "text": s["note"],
                "source": s["source"],
                "horizon": s["verdict_horizon"],
            }
            for s in signals[:8]
        ],
        "as_of": datetime.now(timezone.utc).strftime("%d %b %Y").upper(),
    }


@app.post("/signals", status_code=201)
def add_signal(body: SignalIn, x_ledger_key: str = Header(default="")):
    if x_ledger_key != WRITE_KEY:
        raise HTTPException(status_code=401, detail="Bad ledger key.")
    return {"id": insert_signal(body)}


@app.get("/signals")
def list_signals(q: str = "", limit: int = 50):
    return {"signals": retrieve(q, limit=min(limit, 200))}


@app.get("/health")
def health():
    with db() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM signals").fetchone()["n"]
    return {"ok": True, "signals_on_ledger": n, "llm": bool(ANTHROPIC_API_KEY)}


@app.get("/")
def root():
    page = Path(__file__).parent / "whiteboard.html"
    if page.exists():
        return FileResponse(page)
    return {"service": "kokum-wire", "hint": "place whiteboard.html next to main.py"}
