# KOKUM WIRE

Understand what changed overnight across memory, foundries, packaging, and
suppliers. A dated signal ledger (Layer 3), an
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
    "verdict_horizon": "2026-09-30",
    "device_type": "DRAM,HBM",
    "affected_industries": "Computing,Automotive",
    "region": "APAC,Americas"
  }'
```

`signal_type` vocabulary: `capex_cut`, `equipment_absence`, `hiring`,
`subsidy`, `customs`, `allocation`, `other`. Severity 1 (noise) → 5 (alarm).

The taxonomy fields below follow the standard WSTS / IC Insights market-report
segmentation, so the ledger reads in the vocabulary procurement teams already
use. All are optional, comma-separated, and let a buyer filter to their bill of
materials.

- **`device_type`** — `DRAM`, `NAND`, `NOR`, `MCU`, `DSP`, `Logic`, `Analog`,
  `ASIC`, `ASSP`, `Discretes`, `Optoelectronics`. Sub-tags `HBM` (under DRAM) and
  `eMMC/UFS` (under NAND) carry the finer distinction the coarse groups lose.
- **`affected_industries`** — `Automotive`, `Computing`, `Consumer`,
  `Industrial`, `Wired infrastructure`, `Wireless communication`.
- **`region`** — `Americas`, `EMEA`, `Japan`, `China`, `APAC`.
- **Company** is the `entity` field itself (e.g. `NXP Semiconductors`, `Micron`,
  `ASML`) — the fourth axis of the same report structure, already filterable via
  `?q=`. Coverage universe spans the major memory makers (Micron, Samsung, SK
  hynix, KIOXIA), automotive/MCU (NXP, STMicroelectronics, Infineon, Renesas,
  Microchip), foundry/OSAT, and equipment (ASML, Lam, Applied Materials).

`verdict_horizon` (optional, `YYYY-MM-DD`) is the date by which a *forward-looking*
call can be scored true or false — leave it blank for backward-looking or
purely informational rows. It's what lets the ledger prove a call *now*, not
just backtest history: a row logged today with a horizon inside the week can be
graded against reality before you show the demo.

## Endpoints

- `GET  /` — the whiteboard
- `POST /ask` — `{question}` → `{verdict, answer, signals[], as_of}`
- `POST /signals` — log a signal (needs `X-Ledger-Key` header)
- `GET  /signals?q=magdeburg` — inspect the ledger. Filter to a buyer's BOM with
  `?device=eMMC`, `?industry=Automotive`, or `?region=APAC` (each matches on the
  comma-separated tags; combine them freely)
- `GET  /health` — row count + whether LLM mode is on

## Deploy to Railway

Push this folder to a repo, create a Railway service from it (Procfile is
included), set `ANTHROPIC_API_KEY` and `LEDGER_WRITE_KEY` in service
variables. **Add a Railway volume and point `DB_PATH` at it** — otherwise
the ledger resets on every redeploy, which destroys the timestamp trail.

## Before demoing the backtest

Verify every date and source in `seed_magdeburg.py` against the original
documents. The demo's entire credibility is that the dates are real.
