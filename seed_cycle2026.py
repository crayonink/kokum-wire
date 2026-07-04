"""
Seed the 2026 memory-cycle signals into a LIVE Kokum Wire instance over HTTP.

These are analyst calls logged for the current up-cycle. Rows are ordered by
value to the ledger; the top ones are FORWARD-LOOKING calls with a
verdict_horizon (the date by which they can be scored true/false).

  verdict encoding (matches the app's severity->verdict logic):
    DOUBTFUL = 5, CONCERN = 4, WATCH = 3, INFO = 1-2

!! SOURCES ARE AS-PROVIDED BY THE ANALYST AND NOT YET INDEPENDENTLY VERIFIED,
   except row 6 (India OSAT), which was corroborated across multiple outlets.
   Fill source_url on rows 1-5 with real links before demoing.

Usage (PowerShell):
    $env:KOKUM_URL = "https://kokum-wire-production.up.railway.app"
    $env:LEDGER_WRITE_KEY = "<the key you set in Railway>"
    python seed_cycle2026.py

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
    # 1 — cycle inflection watch (WATCH). Scoreable by 27 Jul.
    {
        "observed_date": "2026-07-04",
        "entity": "DRAM/NAND cycle",
        "signal_type": "other",
        "severity": 3,
        "note": "Possible cycle top forming: spot buyers stopped chasing quotes and NAND spot trading has gone quiet while contract prices stay green — strain showing in behaviour before price. Ackerman note now sees DRAM/NAND ASPs peaking mid-2026, falling from 2027 (a year earlier than his prior call).",
        "source": "Spot-market read + contested Ackerman ASP note",
        "source_url": "",
        "tags": "dram,nand,cycle,inflection,spot,pricing",
        "verdict_horizon": "2026-07-27",
    },
    # 2 — NAND overtakes DRAM (CONCERN for flash buyers).
    {
        "observed_date": "2026-06-30",
        "entity": "NAND flash",
        "signal_type": "allocation",
        "severity": 4,
        "note": "NAND contract prices rising faster than DRAM for the first time this cycle (~70-75% vs ~58-63% QoQ in Q2), driven by enterprise-SSD demand from AI. eMMC/UFS faces the tightest gap — capacity overlaps enterprise SSD at worse margins, so it is lowest allocation priority; hits automotive/embedded buyers hardest.",
        "source": "Q2 2026 contract price data (TrendForce)",
        "source_url": "",
        "tags": "nand,emmc,ufs,ssd,allocation,automotive,embedded",
        "verdict_horizon": "2026-07-27",
    },
    # 3 — allocation lockout (CONCERN for small/mid buyers).
    {
        "observed_date": "2026-07-04",
        "entity": "DRAM allocation",
        "signal_type": "allocation",
        "severity": 4,
        "note": "Micron can fulfil only ~55-60% of core-customer demand; suppliers locking hyperscalers into allocation-only frameworks that structurally disadvantage smaller buyers; DRAM lead times past 40 weeks. Phison CEO: every NAND maker says 2026 capacity is sold out.",
        "source": "Micron disclosure; Phison CEO commentary",
        "source_url": "",
        "tags": "dram,nand,allocation,leadtime,micron,phison,hyperscaler",
        "verdict_horizon": "2026-07-27",
    },
    # 4 — supply relief date (structural, log once).
    {
        "observed_date": "2026-07-04",
        "entity": "DRAM/HBM supply",
        "signal_type": "other",
        "severity": 3,
        "note": "Meaningful new capacity not expected until late 2027-2028. IDC projects 2026 supply growth of ~16% DRAM / ~17% NAND, below the 20-30% historical norm — a structural reallocation, not a cyclical shortage (HBM consumes ~3x wafer capacity per GB vs DDR5).",
        "source": "IDC 2026 supply outlook",
        "source_url": "",
        "tags": "dram,nand,hbm,capacity,structural,idc,ddr5",
        "verdict_horizon": "2027-12-31",
    },
    # 5 — cost pass-through propagation (confirmed downstream impact).
    {
        "observed_date": "2026-03-30",
        "entity": "PC/server OEM pricing",
        "signal_type": "other",
        "severity": 3,
        "note": "Cost pass-through propagating: Dell raised hardware prices +17% on 30 Mar 2026, Cisco raised compute prices 7 Mar 2026; memory now ~35% of PC build materials, up from ~20% a year ago. Evidence the fab->contract->OEM price chain propagates on a traceable lag.",
        "source": "Dell (30 Mar 2026) & Cisco (7 Mar 2026) price actions",
        "source_url": "",
        "tags": "dell,cisco,oem,pc,server,passthrough,pricing",
        "verdict_horizon": "",
    },
    # 6 — India OSAT capacity (INFO, capacity-side). Corroborated.
    {
        "observed_date": "2026-07-03",
        "entity": "India OSAT",
        "signal_type": "subsidy",
        "severity": 2,
        "note": "India approved 12 chip projects under Semiconductor Mission 2.0 (1 fab + 2 component + 9 packaging/testing), ~Rs 1.64 lakh crore (~US$17-19bn) investment pipeline. Medium-term assembly/test capacity signal. (Note: separate Rs 1,695 cr figure is the incentive outlay, not the pipeline.)",
        "source": "India Semiconductor Mission 2.0 approvals (Indian press / TV BRICS, 3 Jul 2026)",
        "source_url": "https://www.ibtimes.co.in/india-approves-12-chip-manufacturing-projects-rs-1-64-lakh-crore-investment-pipeline-903349",
        "tags": "india,osat,packaging,test,subsidy,capacity",
        "verdict_horizon": "",
    },
    # 7 — Vietnam MPW center (INFO, low priority; ecosystem only).
    {
        "observed_date": "2026-07-03",
        "entity": "Vietnam semiconductors",
        "signal_type": "other",
        "severity": 1,
        "note": "Vietnam opens a new semiconductor development / MPW center. Ecosystem signal only; no near-term supply impact. Logged to show the ledger distinguishes signal importance, not just existence.",
        "source": "Vietnam semiconductor center announcement (TV BRICS)",
        "source_url": "",
        "tags": "vietnam,mpw,ecosystem,design",
        "verdict_horizon": "",
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
                horizon = f"  score-by {row['verdict_horizon']}" if row["verdict_horizon"] else ""
                print(f"logged #{body.get('id')}: {row['observed_date']}  "
                      f"{row['entity']}  sev {row['severity']}{horizon}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            sys.exit(f"FAILED ({e.code}) on '{row['entity']}': {detail}\n"
                     f"401 = wrong LEDGER_WRITE_KEY. 404 = wrong KOKUM_URL. "
                     f"422 = server not yet redeployed with the verdict_horizon field.")
        except urllib.error.URLError as e:
            sys.exit(f"Could not reach {BASE_URL}: {e.reason}")

    print(f"\n{len(ROWS)} cycle signals sent. Ask the wire: what's the memory market doing?")


if __name__ == "__main__":
    main()
