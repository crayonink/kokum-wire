"""
Seed a LIVE Kokum Wire instance over HTTP (e.g. your Railway deployment).

Unlike seed_magdeburg.py (which writes the local SQLite file directly), this
POSTs each row to the running server's /signals endpoint, so it seeds the
database the deployed app is actually using — including a Railway volume.

Usage (PowerShell):
    $env:KOKUM_URL = "https://<your-app>.up.railway.app"
    $env:LEDGER_WRITE_KEY = "<the key you set in Railway>"
    python seed_remote.py

Safe to think about before re-running: it does NOT dedupe, so running it
twice inserts the rows twice. Seed once.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("KOKUM_URL", "").rstrip("/")
WRITE_KEY = os.environ.get("LEDGER_WRITE_KEY", "")

ROWS = [
    {
        "observed_date": "2023-04-27",
        "entity": "Intel Magdeburg",
        "signal_type": "capex_cut",
        "severity": 3,
        "note": "FY capex guidance reduced; 'disciplined spending' language introduced on Q1 call.",
        "source": "Intel Q1 2023 earnings call",
        "tags": "intel,magdeburg,fab,europe,capex",
    },
    {
        "observed_date": "2023-06-14",
        "entity": "Intel Magdeburg",
        "signal_type": "equipment_absence",
        "severity": 4,
        "note": "No Magdeburg-attributable orders visible in ASML backlog commentary for a second consecutive quarter; a fab ~18 months from tooling should be placing them.",
        "source": "ASML investor update",
        "tags": "intel,magdeburg,asml,equipment,europe",
    },
    {
        "observed_date": "2023-08-02",
        "entity": "Intel Magdeburg",
        "signal_type": "subsidy",
        "severity": 4,
        "note": "German federal subsidy package unsigned past revised deadline; scope renegotiation reported.",
        "source": "Handelsblatt",
        "tags": "intel,magdeburg,subsidy,germany,europe",
    },
    {
        "observed_date": "2023-09-19",
        "entity": "Intel Magdeburg",
        "signal_type": "hiring",
        "severity": 4,
        "note": "Magdeburg-region Intel job postings down to single digits from 40+ in January; local hiring effectively frozen.",
        "source": "LinkedIn / StepStone listings",
        "tags": "intel,magdeburg,hiring,germany,europe",
    },
    {
        "observed_date": "2024-04-25",
        "entity": "Intel Magdeburg",
        "signal_type": "capex_cut",
        "severity": 5,
        "note": "Further capex discipline signaled; foundry losses widen, management declines to reconfirm Magdeburg timeline when asked.",
        "source": "Intel Q1 2024 earnings call",
        "tags": "intel,magdeburg,capex,europe",
    },
    {
        "observed_date": "2024-09-16",
        "entity": "Intel Magdeburg",
        "signal_type": "other",
        "severity": 5,
        "note": "OUTCOME: Intel announces ~2-year pause of Magdeburg project. Ledger had it DOUBTFUL on accumulated signals ~12 months prior.",
        "source": "Intel corporate announcement",
        "tags": "intel,magdeburg,outcome,europe",
    },
]


def main() -> None:
    if not BASE_URL:
        sys.exit("Set KOKUM_URL to your deployed base URL, e.g. https://kokum-wire.up.railway.app")
    if not WRITE_KEY:
        sys.exit("Set LEDGER_WRITE_KEY to the key you configured in Railway.")

    for row in ROWS:
        req = urllib.request.Request(
            f"{BASE_URL}/signals",
            data=json.dumps(row).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Ledger-Key": WRITE_KEY},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                print(f"logged #{body.get('id')}: {row['observed_date']}  {row['entity']}  [{row['signal_type']}]")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            sys.exit(f"FAILED ({e.code}) on {row['observed_date']}: {detail}\n"
                     f"401 = wrong LEDGER_WRITE_KEY. 404 = wrong KOKUM_URL.")
        except urllib.error.URLError as e:
            sys.exit(f"Could not reach {BASE_URL}: {e.reason}")

    print(f"\n{len(ROWS)} rows sent. Now ask the wire: what's new with Intel Magdeburg?")


if __name__ == "__main__":
    main()
