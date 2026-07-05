"""
Seed automotive-MCU signals into a LIVE Kokum Wire instance over HTTP: NXP and
STMicroelectronics, the two makers most relevant to an automotive embedded buyer
(instrument clusters, body/zonal control, sensors — i.e. Pricol's bill of
materials). These give the ledger real MCU-tagged rows so a device=MCU or
industry=automotive filter isn't empty.

The honest read here differs from memory: automotive MCU supply has largely
NORMALIZED off the 2021-22 shortage and the 2024-25 inventory correction, with
the tightness risk shifting to advanced zonal/SDV and safety MCUs. So these are
low-severity (recovery) signals, not allocation alarms — which is exactly the
point of device-typing: an automotive MCU buyer should see a calmer picture than
a memory buyer.

Figures are from the Q1 2026 earnings, cross-checked across multiple outlets on
2026-07-05. IMPORTANT: the primary SEC / investor-relations pages were not
machine-fetchable at draft time, so RE-VERIFY every figure AND the exact report
dates against NXP and ST investor relations before publishing — the ledger's
credibility is that the numbers and dates are real. ST's exact Q1 2026 report
date in particular should be confirmed (late April 2026 is an estimate).

Usage (PowerShell):
    $env:KOKUM_URL = "https://kokum-wire-production.up.railway.app"
    $env:LEDGER_WRITE_KEY = "<the key you set in Railway>"
    python seed_mcu_auto.py

Not idempotent — run once.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("KOKUM_URL", "").rstrip("/")
WRITE_KEY = os.environ.get("LEDGER_WRITE_KEY", "")

ROWS = [
    # NXP — the automotive MCU market leader (S32). Recovery + SDV concentration.
    {
        "observed_date": "2026-04-29",
        "entity": "NXP Semiconductors",
        "signal_type": "other",
        "severity": 2,
        "note": "NXP Q1 2026 (reported 29 Apr 2026): revenue $3.18bn (+12% YoY); automotive $1.782bn (+6% YoY, +10% adjusted for the divested MEMS sensors business). Automotive MCU demand is recovering after the post-2021 inventory correction. Growth is concentrating in software-defined-vehicle / zonal processors, radar and electrification — now ~45% of auto revenue (up from 39% in late 2025) and ~90% of YoY auto growth; the S32 SDV platform is guided to 20-30% revenue CAGR. Read for a cluster/embedded buyer: commodity automotive MCU supply has normalized, but demand and future tightness are shifting to advanced zonal/SDV parts.",
        "source": "NXP Q1 2026 results (SEC 8-K, 29 Apr 2026) + Q1 2026 earnings call",
        "source_url": "https://www.stocktitan.net/sec-filings/NXPI/8-k-nxp-semiconductors-n-v-reports-material-event-86c628442e79.html",
        "tags": "nxp,mcu,microcontroller,s32,automotive,sdv,zonal,radar",
        "verdict_horizon": "",
        "device_type": "MCU,Logic",
        "affected_industries": "Automotive,Industrial",
        "region": "EMEA,Americas,APAC",
    },
    # STMicroelectronics — #1 in general-purpose MCUs; automotive design-win engine.
    {
        "observed_date": "2026-04-24",
        "entity": "STMicroelectronics",
        "signal_type": "other",
        "severity": 2,
        "note": "STMicroelectronics Q1 2026 (reported ~24 Apr 2026 — confirm exact date): revenue $3.10bn (+23% YoY), GAAP gross margin 33.8%. Automotive fell 10% sequentially but rose 15% YoY on EV/hybrid design wins; Industrial +26% YoY. ST remains #1 in general-purpose microcontrollers. Read: automotive and industrial MCU demand is recovering off the 2024-25 trough, but the sequential decline shows the recovery is still uneven quarter to quarter.",
        "source": "STMicroelectronics Q1 2026 results (press release, ~24 Apr 2026)",
        "source_url": "https://www.sec.gov/Archives/edgar/data/0000932787/000093278726000022/q126earningspressrelease-2.htm",
        "tags": "stmicro,st,mcu,microcontroller,automotive,industrial,analog",
        "verdict_horizon": "",
        "device_type": "MCU,Analog",
        "affected_industries": "Automotive,Industrial",
        "region": "EMEA,Americas,APAC",
    },
]


def main() -> None:
    if not BASE_URL:
        sys.exit("Set KOKUM_URL to your deployed base URL.")
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
                print(f"logged #{body.get('id')}: {row['observed_date']}  "
                      f"{row['entity']}  [{row['device_type']}]  sev {row['severity']}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            sys.exit(f"FAILED ({e.code}) on '{row['entity']}': {detail}\n"
                     f"401 = wrong LEDGER_WRITE_KEY. 404 = wrong KOKUM_URL. "
                     f"422 = server missing the device_type field (redeploy first).")
        except urllib.error.URLError as e:
            sys.exit(f"Could not reach {BASE_URL}: {e.reason}")

    print(f"\n{len(ROWS)} automotive-MCU signals sent. "
          f"Filter the ledger: /signals?device=MCU  or  /signals?industry=automotive")


if __name__ == "__main__":
    main()
