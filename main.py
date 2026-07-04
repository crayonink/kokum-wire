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


class DecideIn(BaseModel):
    part_class: str = Field(
        ..., description="e.g. 'eMMC/UFS automotive', 'DRAM', 'NAND'"
    )
    monthly_volume: int = Field(
        0, ge=0, description="units per month (optional, for sizing the shortfall)"
    )
    coverage_months: float = Field(
        0, ge=0, description="months of inventory + contracted supply on hand"
    )


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


# Structured-output schema — the API constrains the response to exactly this
# shape, so the dispatch is guaranteed valid JSON with a valid verdict. This
# removes the whole class of "LLM returned prose/fences -> json.loads fails ->
# silent fallback" bugs. Supported on Sonnet 5 / Opus 4.8 / Haiku 4.5.
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": VERDICTS},
        "answer": {"type": "string"},
    },
    "required": ["verdict", "answer"],
    "additionalProperties": False,
}


def compose_with_claude(question: str, signals: list[dict]) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    signal_lines = "\n".join(
        f"- observed {s['observed_date']} | {s['entity']} | {s['signal_type']} "
        f"| severity {s['severity']}/5 | {s['note']} | source: {s['source']}"
        for s in signals
    )
    q = question or "What's new?"
    kwargs = dict(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        # Composing a terse dispatch from rows we already supply is a constrained
        # task, not a reasoning one. Sonnet 5 runs adaptive thinking at the
        # default high effort when left alone — several seconds of latency the
        # demo doesn't need. Disable thinking and run at low effort so the
        # dispatch returns in ~1-2s. The rows do the work; the model just writes.
        thinking={"type": "disabled"},
        messages=[
            {
                "role": "user",
                "content": f"QUESTION: {q}\n\nLEDGER SIGNALS:\n{signal_lines}",
            }
        ],
    )
    try:
        msg = client.messages.create(
            **kwargs,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
            },
        )
    except anthropic.BadRequestError:
        # A KOKUM_MODEL that doesn't support structured outputs rejects
        # output_config with a 400 — retry plain and rely on tolerant parsing.
        msg = client.messages.create(**kwargs)
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    # With structured outputs this is already clean JSON; the fence/preamble
    # tolerance stays as a belt-and-suspenders guard for any model that ignores
    # output_config (e.g. an older KOKUM_MODEL override).
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
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
# Layer 2b — the decision engine ("buy now vs. later")
#
# Deterministic and inspectable: transparent thresholds over the ledger's own
# verdicts, with the dated rows as the evidence trail. No LLM — a procurement
# lead can audit exactly which signal tripped which recommendation, and every
# claim carries a date and a source. This is the "what should I do" rung of the
# ladder, derived only from signals we actually track (never a hallucinated
# optimization).
# ----------------------------------------------------------------------
def _haystack(r: dict) -> str:
    return " ".join([r["entity"], r["note"], r["tags"], r["signal_type"]]).lower()


def _has(r: dict, terms) -> bool:
    h = _haystack(r)
    return any(t in h for t in terms)


def _ddmmyyyy(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return d


def _cite(r: dict) -> str:
    return f"{r['source']}, {_ddmmyyyy(r['observed_date'])}"


# Terms that classify a row into the two axes the decision reconciles.
_ALLOC_TERMS = [
    "sold out", "sold-out", "short of demand", "half to two-thirds",
    "allocation", "allocated", "lowest allocation", "lockout",
]
_TOP_TERMS = [
    "cycle top", "top forming", "inflection", "balk", "peak", "asps peaking",
]
_STRUCT_TERMS = [
    "late 2027", "2027-2028", "new capacity", "structural",
]
_TIGHTEST_TERMS = [
    "lowest allocation priority", "lowest priority", "tightest gap", "hardest",
]


def decide_buy_timing(part_class: str, monthly_volume: int,
                      coverage_months: float) -> dict:
    """Reconcile the two live tensions for a memory buyer — allocation is tight
    (2026 sold out) but a cycle top may be forming — into a timing call, sized
    against the buyer's own coverage. Every recommendation is traced to a dated
    ledger row."""
    part_rows = retrieve(part_class, limit=25)
    with db() as conn:
        all_rows = [
            dict(r) for r in conn.execute(
                "SELECT * FROM signals ORDER BY severity DESC, observed_date DESC"
            )
        ]

    alloc_rows = [r for r in all_rows
                  if r["signal_type"] == "allocation" or _has(r, _ALLOC_TERMS)]
    top_rows = [r for r in all_rows if _has(r, _TOP_TERMS)]
    struct_rows = [r for r in all_rows if _has(r, _STRUCT_TERMS)]

    allocation_risk = max((r["severity"] for r in alloc_rows), default=0)
    price_top = any(r["severity"] >= 3 for r in top_rows)
    part_flag = next((r for r in part_rows if _has(r, _TIGHTEST_TERMS)), None)

    verdict = ("DOUBTFUL" if allocation_risk >= 5 else
               "CONCERN" if allocation_risk == 4 else
               "WATCH" if allocation_risk == 3 else "CLEAR")

    # Honest bail-out: the part class isn't in the ledger's coverage (no rows
    # match it), or the ledger holds nothing to reason over. Without this gate
    # the market-wide memory signals would fire for any part — even ones the
    # ledger has never tracked.
    if not part_rows or (allocation_risk == 0 and not top_rows and not struct_rows):
        return {
            "part_class": part_class, "verdict": "CLEAR", "urgency": "LOW",
            "headline": "No signal on the ledger for this part class yet — "
                        "scope it to a memory part family the ledger tracks "
                        "(DRAM, NAND, eMMC/UFS), or log signals for it first.",
            "allocation_action": "Log signals for this part class, then re-run.",
            "price_action": "—",
            "coverage_target_months": 0, "coverage_gap_months": 0,
            "rationale": [], "evidence": [],
            "inputs": {"part_class": part_class, "monthly_volume": monthly_volume,
                       "coverage_months": coverage_months},
            "as_of": datetime.now(timezone.utc).strftime("%d %b %Y").upper(),
        }

    # Coverage math: prudent buffer scales with how tight allocation is.
    target_cover = 6 if allocation_risk >= 4 else 4 if allocation_risk == 3 else 2
    gap_months = round(max(0.0, target_cover - coverage_months), 1)
    buffer_units = int(monthly_volume * coverage_months)
    gap_units = int(monthly_volume * gap_months)

    if allocation_risk >= 4 and coverage_months < 3:
        urgency = "URGENT"
    elif allocation_risk >= 4:
        urgency = "HIGH"
    elif allocation_risk == 3:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    if allocation_risk >= 4:
        allocation_action = ("Lock allocation now — contract the fullest "
                             "volume and tenor you can secure.")
    elif allocation_risk == 3:
        allocation_action = ("Start locking allocation this quarter — the "
                             "market is tightening.")
    else:
        allocation_action = "No allocation pressure — standard procurement cadence."

    if price_top:
        price_action = ("Keep price exposure SHORT — prefer index-linked or "
                        "short-tenor terms over long fixed prices. A contested "
                        "cycle-top call is live.")
    else:
        price_action = "Standard price terms — no cycle-top signal on the ledger."

    if allocation_risk >= 4 and price_top:
        headline = "Lock allocation now; keep price exposure short."
    elif allocation_risk >= 4:
        headline = "Lock allocation now."
    elif allocation_risk == 3 and price_top:
        headline = "Begin locking allocation; keep price exposure short."
    elif price_top:
        headline = "No allocation pressure; keep price exposure short."
    else:
        headline = "Standard cadence — no urgent timing signal."

    # Rationale — each line traced to a real dated row.
    rationale, used = [], []
    if alloc_rows:
        r = max(alloc_rows, key=lambda x: x["severity"])
        rationale.append(f"2026 supply is allocated (severity {r['severity']}/5): "
                         f"{r['note']} ({_cite(r)}).")
        used.append(r)
    if part_flag and part_flag["id"] not in {u["id"] for u in used}:
        rationale.append("Your part class sits in the tightest segment: "
                         f"{part_flag['note']} ({_cite(part_flag)}).")
        used.append(part_flag)
    if price_top:
        r = max(top_rows, key=lambda x: x["severity"])
        rationale.append("But a cycle top may be forming — reason not to lock "
                         f"long fixed prices: {r['note']} ({_cite(r)}).")
        used.append(r)
    if struct_rows:
        r = struct_rows[0]
        rationale.append(f"The squeeze is structural, not a blip: {r['note']} "
                         f"({_cite(r)}).")
        used.append(r)
    if coverage_months is not None:
        line = f"You hold {coverage_months:g} months of cover"
        if monthly_volume:
            line += f" (~{buffer_units:,} units)"
        line += f" against a prudent {target_cover}-month buffer for this risk level"
        if gap_months > 0:
            line += f" — a {gap_months:g}-month"
            if monthly_volume:
                line += f" / ~{gap_units:,}-unit"
            line += " shortfall to close."
        else:
            line += (" — near-term cover is adequate, but allocation must "
                     "still be secured ahead of the sold-out window.")
        rationale.append(line)

    seen, evidence = set(), []
    for r in used:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        evidence.append({
            "date": r["observed_date"], "entity": r["entity"],
            "text": r["note"], "source": r["source"],
            "source_url": r.get("source_url", ""), "horizon": r["verdict_horizon"],
        })

    return {
        "part_class": part_class,
        "verdict": verdict,
        "urgency": urgency,
        "headline": headline,
        "allocation_action": allocation_action,
        "price_action": price_action,
        "coverage_target_months": target_cover,
        "coverage_gap_months": gap_months,
        "rationale": rationale,
        "evidence": evidence,
        "inputs": {"part_class": part_class, "monthly_volume": monthly_volume,
                   "coverage_months": coverage_months},
        "as_of": datetime.now(timezone.utc).strftime("%d %b %Y").upper(),
    }


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


@app.post("/decide")
def decide(body: DecideIn):
    return decide_buy_timing(
        body.part_class.strip(), body.monthly_volume, body.coverage_months
    )


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
