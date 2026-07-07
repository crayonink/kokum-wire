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

from archetypes import ARCHETYPES

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "ledger.db"))
WRITE_KEY = os.environ.get("LEDGER_WRITE_KEY", "changeme")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("KOKUM_MODEL", "claude-sonnet-5")
# Synthesis is genuine cross-row reasoning, not phrasing — worth a stronger
# model than the dispatch. Opus 4.8 by default; overridable.
SYNTH_MODEL = os.environ.get("KOKUM_SYNTH_MODEL", "claude-opus-4-8")

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
                verdict_horizon TEXT DEFAULT '',      -- YYYY-MM-DD by which a forward call
                                                      -- can be scored true/false ('' = not a call)
                device_type     TEXT DEFAULT '',      -- device-type group(s), comma-sep (WSTS/
                                                      -- IC Insights vocab): DRAM, NAND, NOR,
                                                      -- MCU, DSP, Logic, Analog, ASIC, ASSP,
                                                      -- Discretes, Optoelectronics; sub-tags
                                                      -- HBM, eMMC/UFS
                affected_industries TEXT DEFAULT '',  -- comma-sep: Automotive, Computing,
                                                      -- Consumer, Industrial, Wired
                                                      -- infrastructure, Wireless communication
                region          TEXT DEFAULT ''       -- comma-sep: Americas, EMEA, Japan,
                                                      -- China, APAC
            )
            """
        )
        # Idempotent migration: add any missing columns to a pre-existing table.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(signals)")}
        for col in ("verdict_horizon", "device_type", "affected_industries", "region"):
            if col not in cols:
                conn.execute(f"ALTER TABLE signals ADD COLUMN {col} TEXT DEFAULT ''")


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
    device_type: str = Field(
        "", description="device-type group(s), comma-separated (WSTS/IC Insights vocab): DRAM, NAND, NOR, MCU, DSP, Logic, Analog, ASIC, ASSP, Discretes, Optoelectronics (sub-tags: HBM, eMMC/UFS)"
    )
    affected_industries: str = Field(
        "", description="comma-separated industries: Automotive, Computing, Consumer, Industrial, Wired infrastructure, Wireless communication"
    )
    region: str = Field(
        "", description="comma-separated regions: Americas, EMEA, Japan, China, APAC"
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


class SynthesizeIn(BaseModel):
    question: str = ""


class RetagRow(BaseModel):
    entity: str
    device_type: str = ""
    affected_industries: str = ""
    region: str = ""


def insert_signal(s: SignalIn) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO signals
               (logged_at, observed_date, entity, signal_type, severity,
                note, source, source_url, tags, verdict_horizon,
                device_type, affected_industries, region)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                s.device_type.strip(),
                s.affected_industries.strip(),
                s.region.strip(),
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
            [r["entity"], r["note"], r["tags"], r["signal_type"],
             r["device_type"], r["affected_industries"], r["region"]]
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
4. Voice: plain, direct business English — detailed and explanatory. Spell out
   the reasoning behind each point, not just the conclusion: state the takeaway,
   then explain why the signals support it. Clear, complete sentences a
   non-expert can follow. Prefer common words over jargon; when a domain term is
   unavoidable (e.g. allocation), explain it in plain words. No telegram style,
   no dramatic flourishes, no hedging filler.
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
            "answer": "The ledger has no entries on this yet. Try a company, "
            "fab, or part family, and ask again.",
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
# Layer 2c — synthesis (signal -> insight)
#
# Cross-row reasoning: surface claims that emerge from combining >=2 dated rows,
# which no single row states. This is the one place the model genuinely reasons
# rather than phrases, so it's also where hallucination could enter — the guard
# is grounding: the model cites signal numbers, and we DROP any insight whose
# citations aren't real rows in the retrieved set. Every surviving claim is
# traceable to specific dated, sourced rows.
# ----------------------------------------------------------------------
SYNTH_SYSTEM = """You are a senior semiconductor supply-chain analyst writing for
procurement leaders.

You receive a QUESTION and a numbered list of dated LEDGER SIGNALS. Your job is
SYNTHESIS: surface insights that emerge from combining TWO OR MORE signals — a
claim no single signal states on its own. Insight types:
  cross_row_inference — combining signals implies a conclusion none states alone
  tension            — signals point in conflicting directions; name the conflict
  causal_chain       — signals link into a cause -> effect sequence
  convergence        — independent signals corroborate the same conclusion

Rules, absolute:
1. Every insight must combine AT LEAST TWO signals; cite them by their [number].
2. Use ONLY facts present in the cited signals. No outside knowledge, no figures
   not in the signals, no speculation the signals don't support.
3. If the signals do not support a genuine multi-signal insight, return an EMPTY
   list. Do not manufacture connections to fill space — fewer real insights beat
   many shallow ones. Cap at 4.
4. Each claim is plain, direct business English that spells out HOW the combined
   signals lead to the conclusion: state the conclusion first, then the reasoning
   that connects the cited signals. Two to four sentences; prefer common words
   over jargon.

Reply with ONLY JSON:
{"insights":[{"claim":"...","insight_type":"...","signal_numbers":[1,4]}]}"""


# Structured-output schema. Array-size limits (>=2 numbers) aren't expressible in
# the schema, so they're enforced in ground_insights() below.
INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "insight_type": {
                        "type": "string",
                        "enum": ["cross_row_inference", "tension",
                                 "causal_chain", "convergence"],
                    },
                    "signal_numbers": {
                        "type": "array", "items": {"type": "integer"},
                    },
                },
                "required": ["claim", "insight_type", "signal_numbers"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["insights"],
    "additionalProperties": False,
}


def synthesize_insights(question: str, signals: list[dict]) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    numbered = "\n".join(
        f"[{i}] observed {s['observed_date']} | {s['entity']} | "
        f"sev {s['severity']}/5 | {s['note']} | source: {s['source']}"
        for i, s in enumerate(signals, 1)
    )
    q = question or "What do these signals mean together?"
    kwargs = dict(
        model=SYNTH_MODEL,
        max_tokens=3000,
        # Synthesis is the reasoning task — thinking ON (unlike the dispatch).
        thinking={"type": "adaptive"},
        system=SYNTH_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"QUESTION: {q}\n\nLEDGER SIGNALS (numbered):\n{numbered}",
            }
        ],
    )
    try:
        msg = client.messages.create(
            **kwargs,
            output_config={
                "effort": "high",
                "format": {"type": "json_schema", "schema": INSIGHT_SCHEMA},
            },
        )
    except anthropic.BadRequestError:
        msg = client.messages.create(**kwargs)
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        data = json.loads(m.group(0))
    return data.get("insights", [])


def ground_insights(raw_insights: list[dict],
                    signals: list[dict]) -> tuple[list[dict], int]:
    """The anti-hallucination guard. Keep only insights that cite >=2 real rows
    from the set we handed the model; map their citations to the dated rows.
    Returns (grounded_insights, dropped_count)."""
    n = len(signals)
    grounded, dropped = [], 0
    for ins in raw_insights or []:
        claim = (ins.get("claim") or "").strip()
        nums = sorted({
            int(x) for x in ins.get("signal_numbers", [])
            if isinstance(x, bool) is False and str(x).lstrip("-").isdigit()
        })
        nums = [x for x in nums if 1 <= x <= n]  # only citations that exist
        if not claim or len(nums) < 2:           # synthesis needs >=2 real rows
            dropped += 1
            continue
        supporting = [{
            "n": x,
            "date": signals[x - 1]["observed_date"],
            "entity": signals[x - 1]["entity"],
            "text": signals[x - 1]["note"],
            "source": signals[x - 1]["source"],
            "source_url": signals[x - 1].get("source_url", ""),
            "device_type": signals[x - 1]["device_type"],
            "affected_industries": signals[x - 1]["affected_industries"],
            "region": signals[x - 1]["region"],
        } for x in nums]
        grounded.append({
            "claim": claim,
            "insight_type": ins.get("insight_type", "cross_row_inference"),
            "supporting": supporting,
        })
    return grounded, dropped


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
            "headline": "The ledger doesn't track this part yet. Try a memory "
                        "part it does cover (DRAM, NAND, eMMC/UFS), or add "
                        "signals for it first.",
            "allocation_action": "Add signals for this part, then run it again.",
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
        allocation_action = ("Secure your supply now by contracting as much "
                             "volume, and as long a term, as you can. The supply "
                             "the ledger tracks is already committed to other "
                             "buyers, so waiting means smaller allocations and "
                             "longer lead times.")
    elif allocation_risk == 3:
        allocation_action = ("Start securing supply this quarter. The market is "
                             "tightening, and locking terms now — before it turns "
                             "fully committed — protects your volume.")
    else:
        allocation_action = ("No supply pressure right now, so you can buy on your "
                             "normal schedule rather than committing early.")

    if price_top:
        price_action = ("Avoid long fixed-price deals. A credible signal suggests "
                        "prices may be near their peak, so keeping terms short or "
                        "market-linked protects you if they fall from here.")
    else:
        price_action = ("Normal price terms are fine — nothing on the ledger "
                        "suggests prices are about to fall, so there's no need to "
                        "keep terms unusually short.")

    if allocation_risk >= 4 and price_top:
        headline = "Secure supply now; keep prices flexible."
    elif allocation_risk >= 4:
        headline = "Secure your supply now."
    elif allocation_risk == 3 and price_top:
        headline = "Start securing supply; keep prices flexible."
    elif price_top:
        headline = "No supply pressure; keep prices flexible."
    else:
        headline = "No urgent timing signal — buy on your normal schedule."

    # Rationale — each line traced to a real dated row.
    rationale, used = [], []
    if alloc_rows:
        r = max(alloc_rows, key=lambda x: x["severity"])
        rationale.append("2026 supply is already committed to other buyers "
                         f"(severity {r['severity']}/5): {r['note']} ({_cite(r)}).")
        used.append(r)
    if part_flag and part_flag["id"] not in {u["id"] for u in used}:
        rationale.append("Your part is in the hardest-hit group: "
                         f"{part_flag['note']} ({_cite(part_flag)}).")
        used.append(part_flag)
    if price_top:
        r = max(top_rows, key=lambda x: x["severity"])
        rationale.append("But prices may be near their peak — a reason not to lock "
                         f"in long fixed prices: {r['note']} ({_cite(r)}).")
        used.append(r)
    if struct_rows:
        r = struct_rows[0]
        rationale.append(f"This shortage is long-term, not a brief dip: {r['note']} "
                         f"({_cite(r)}).")
        used.append(r)
    if coverage_months is not None:
        line = f"You have {coverage_months:g} months of supply on hand"
        if monthly_volume:
            line += f" (~{buffer_units:,} units)"
        line += f". For this level of risk, {target_cover} months is a safer cushion"
        if gap_months > 0:
            line += f" — you're short by about {gap_months:g} months"
            if monthly_volume:
                line += f" (~{gap_units:,} units)"
            line += "."
        else:
            line += (" — your near-term supply is fine, but you should still lock "
                     "in future supply before it's all committed.")
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
            "device_type": r["device_type"],
            "affected_industries": r["affected_industries"], "region": r["region"],
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
                "entity": s["entity"],
                "text": s["note"],
                "source": s["source"],
                "horizon": s["verdict_horizon"],
                "device_type": s["device_type"],
                "affected_industries": s["affected_industries"],
                "region": s["region"],
            }
            for s in signals[:8]
        ],
        "as_of": datetime.now(timezone.utc).strftime("%d %b %Y").upper(),
    }


@app.post("/synthesize")
def synthesize(body: SynthesizeIn):
    signals = retrieve(body.question)
    as_of = datetime.now(timezone.utc).strftime("%d %b %Y").upper()
    base = {"question": body.question, "insights": [], "dropped": 0,
            "signals_considered": len(signals), "as_of": as_of}
    if len(signals) < 2:
        return {**base, "note": "Need at least two related signals to find a "
                                "connection. Try a broader question."}
    if not ANTHROPIC_API_KEY:
        return {**base, "note": "Finding connections needs the AI model. "
                                "Set ANTHROPIC_API_KEY."}
    try:
        raw = synthesize_insights(body.question, signals)
    except Exception as e:
        print(f"[/synthesize] failed: {type(e).__name__}: {e}", flush=True)
        return {**base, "note": "Synthesis call failed; see server logs."}
    grounded, dropped = ground_insights(raw, signals)
    note = None
    if not grounded:
        note = ("No connection the evidence supports yet — the rows on this "
                "don't join up into a single insight.")
    return {**base, "insights": grounded, "dropped": dropped, "note": note}


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


def _tagset(s: str) -> list[str]:
    return [t.strip().lower() for t in (s or "").split(",") if t.strip()]


def filter_rows(rows: list[dict], device: str, industry: str,
                region: str) -> list[dict]:
    """Keep rows whose device_type / affected_industries / region include the
    requested tag (substring match, so 'eMMC' matches 'eMMC/UFS'). Lets a buyer
    see only what touches their BOM — e.g. device=MCU, industry=Automotive,
    region=APAC."""
    dev = device.strip().lower()
    ind = industry.strip().lower()
    reg = region.strip().lower()
    out = []
    for r in rows:
        if dev and not any(dev in t for t in _tagset(r["device_type"])):
            continue
        if ind and not any(ind in t for t in _tagset(r["affected_industries"])):
            continue
        if reg and not any(reg in t for t in _tagset(r["region"])):
            continue
        out.append(r)
    return out


@app.get("/signals")
def list_signals(q: str = "", device: str = "", industry: str = "",
                 region: str = "", limit: int = 50):
    rows = filter_rows(retrieve(q, limit=200), device, industry, region)
    return {"signals": rows[:min(limit, 200)]}


# ----------------------------------------------------------------------
# Layer 1b — company flow (the archetype journey, signal-overlaid)
#
# A company-anchored view: products -> device types -> designers -> fabs ->
# OSATs -> distributors -> the line, with the ledger's live signal state on each
# device. The chain entities are the INFERRED typical universe (archetypes.py);
# the signal state is a real query over the dated rows. See docs/pricol-archetype.md.
# ----------------------------------------------------------------------
def flow_signal(match_tokens: list[str], all_rows: list[dict]) -> tuple[str, list[dict]]:
    """Signal state for one device node: scan the ledger for rows whose
    device_type/tags contain any match token. HOT if any matched row is severity
    >= 3, CALM if matched but all <= 2, DARK if none. Returns (state, up-to-4
    evidence rows, most-severe first)."""
    toks = [t.lower() for t in match_tokens]
    matches = [
        r for r in all_rows
        if any(t in (r["device_type"] + " " + r["tags"]).lower() for t in toks)
    ]
    if not matches:
        return "DARK", []
    matches.sort(key=lambda r: r["severity"], reverse=True)
    state = "HOT" if matches[0]["severity"] >= 3 else "CALM"
    ev = [{
        "date": r["observed_date"], "entity": r["entity"], "text": r["note"],
        "source": r["source"], "source_url": r["source_url"],
        "device_type": r["device_type"],
        "affected_industries": r["affected_industries"], "region": r["region"],
    } for r in matches[:4]]
    return state, ev


@app.get("/flow")
def flow(company: str = "pricol"):
    arch = ARCHETYPES.get(company.strip().lower())
    if not arch:
        raise HTTPException(
            status_code=404,
            detail="No archetype for that company. Available: "
                   + ", ".join(a["company"] for a in ARCHETYPES.values()),
        )
    with db() as conn:
        all_rows = [dict(r) for r in conn.execute("SELECT * FROM signals")]
    devices = []
    for d in arch["devices"]:
        state, ev = flow_signal(d["match"], all_rows)
        devices.append({
            "device": d["device"],
            "designers": d["designers"],
            "fab": d["fab"], "node": d["node"], "osat": d["osat"],
            "distributors": d["distributors"],
            "signal_state": state, "evidence": ev,
        })
    return {
        "company": arch["company"],
        "product": arch["product"],
        "product_note": arch.get("product_note", ""),
        "devices": devices,
        "companies": [a["company"] for a in ARCHETYPES.values()],
        "as_of": datetime.now(timezone.utc).strftime("%d %b %Y").upper(),
    }


@app.post("/admin/retag")
def retag(rows: list[RetagRow], x_ledger_key: str = Header(default="")):
    """Keyed, idempotent taxonomy backfill: set device_type / affected_industries
    / region on existing rows by exact entity match — for upgrading rows logged
    before those fields existed. Only touches the taxonomy columns; logged_at and
    all signal content are preserved. Safe to re-run."""
    if x_ledger_key != WRITE_KEY:
        raise HTTPException(status_code=401, detail="Bad ledger key.")
    updated = {}
    with db() as conn:
        for r in rows:
            cur = conn.execute(
                "UPDATE signals SET device_type=?, affected_industries=?, region=? "
                "WHERE entity=?",
                (r.device_type.strip(), r.affected_industries.strip(),
                 r.region.strip(), r.entity.strip()),
            )
            if cur.rowcount:
                updated[r.entity] = cur.rowcount
    return {"updated": updated, "rows_updated": sum(updated.values())}


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
