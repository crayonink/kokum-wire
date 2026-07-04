# KOKUM WIRE

Semiconductor supply chain intelligence. A dated signal ledger (Layer 3), an
LLM dispatch composer (Layer 2), and a one-question whiteboard front end
(Layer 1), in one small FastAPI app.

## Run locally

```bash
pip install -r requirements.txt
python seed_magdeburg.py          # loads the Intel Magdeburg backtest rows
uvicorn main:app --reload
# open http://localhost:8000  →  ask: what's new with Intel Magdeburg?
```

Without `ANTHROPIC_API_KEY` set, `/ask` composes a plain, deterministic
answer from the ledger (marked as such). With the key set, Claude writes the
dispatch — strictly from ledger rows, dates cited, no outside knowledge.

## Environment

| Variable            | Purpose                                  | Default    |
|---------------------|------------------------------------------|------------|
| `ANTHROPIC_API_KEY` | Enables LLM-composed dispatches          | (unset)    |
| `LEDGER_WRITE_KEY`  | Required header to POST /signals         | `changeme` |
| `DB_PATH`           | SQLite location                          | ./ledger.db|
| `KOKUM_MODEL`       | Claude model for dispatches              | claude-sonnet-5 |

**Change `LEDGER_WRITE_KEY` before deploying.**

## Daily logging (this is the company)

Every signal you read — earnings call, ASML commentary, customs data, job
postings — goes on the ledger the day you read it. `logged_at` is set by the
server and never edited: that timestamp trail is your track record.

```bash
curl -X POST https://<your-app>/signals \
  -H 'Content-Type: application/json' \
  -H 'X-Ledger-Key: <your key>' \
  -d '{
    "observed_date": "2026-07-04",
    "entity": "TSMC CoWoS",
    "signal_type": "allocation",
    "severity": 3,
    "note": "Advanced packaging capacity commentary tightening on Q2 call.",
    "source": "TSMC Q2 2026 earnings call",
    "source_url": "https://...",
    "tags": "tsmc,cowos,packaging,ai",
    "verdict_horizon": "2026-09-30"
  }'
```

`signal_type` vocabulary: `capex_cut`, `equipment_absence`, `hiring`,
`subsidy`, `customs`, `allocation`, `other`. Severity 1 (noise) → 5 (alarm).

`verdict_horizon` (optional, `YYYY-MM-DD`) is the date by which a *forward-looking*
call can be scored true or false — leave it blank for backward-looking or
purely informational rows. It's what lets the ledger prove a call *now*, not
just backtest history: a row logged today with a horizon inside the week can be
graded against reality before you show the demo.

## Endpoints

- `GET  /` — the whiteboard
- `POST /ask` — `{question}` → `{verdict, answer, signals[], as_of}`
- `POST /signals` — log a signal (needs `X-Ledger-Key` header)
- `GET  /signals?q=magdeburg` — inspect the ledger
- `GET  /health` — row count + whether LLM mode is on

## Deploy to Railway

Push this folder to a repo, create a Railway service from it (Procfile is
included), set `ANTHROPIC_API_KEY` and `LEDGER_WRITE_KEY` in service
variables. **Add a Railway volume and point `DB_PATH` at it** — otherwise
the ledger resets on every redeploy, which destroys the timestamp trail.

## Before demoing the backtest

Verify every date and source in `seed_magdeburg.py` against the original
documents. The demo's entire credibility is that the dates are real.
