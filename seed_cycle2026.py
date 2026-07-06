"""
Seed the 2026 memory-cycle signals into a LIVE Kokum Wire instance over HTTP.

These are analyst calls logged for the current up-cycle. Rows are ordered by
value to the ledger; the top ones are FORWARD-LOOKING calls with a
verdict_horizon (the date by which they can be scored true/false).

  verdict encoding (matches the app's severity->verdict logic):
    DOUBTFUL = 5, CONCERN = 4, WATCH = 3, INFO = 1-2

Figures cross-checked against tier-1 sources on 2026-07-04 (TrendForce, Tom's
Hardware, IDC, Micron, Phison, HP, Indian press). source_url is populated on
every substantive row. Corrections applied vs the original analyst brief:
  - Row 3: Micron figure set to its actual words 'half to two-thirds' (was
    '55-60%'); unverified '40-week lead time' specific dropped.
  - Row 4: IDC 16%/17% confirmed; HBM wafer ratio set to ~3-4x (was ~3x).
  - Row 5: the ~35%-of-BOM stat is HP's disclosure (not Dell's); Dell/Cisco
    kept as the dated price actions.
  - Row 1: reworded to the verified 'buyers balking' behaviour; the early-peak
    call is flagged as a contested minority view.

Usage (PowerShell):
    $env:KOKUM_URL = "https://wire.kokumlabs.in"
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
        "note": "Possible cycle top forming: buyers starting to balk even as DRAM/NAND contract prices keep rising in mid-2026 — strain showing in behaviour before price. Contrarian read: a contested analyst call sees ASPs peaking mid-2026 and falling from 2027, against a mainstream view that prices hold up through 2027+.",
        "source": "Spot/contract read (BuySellRam, mid-2026) + contested early-peak analyst call",
        "source_url": "https://www.buysellram.com/blog/dram-nand-prices-mid-2026/",
        "tags": "dram,nand,cycle,inflection,spot,pricing",
        "verdict_horizon": "2026-07-27",
        "device_type": "DRAM,NAND",
        "affected_industries": "Automotive,Industrial,Consumer,Computing",
        "region": "Americas,EMEA,APAC",
    },
    # 2 — NAND overtakes DRAM (CONCERN for flash buyers).
    {
        "observed_date": "2026-06-30",
        "entity": "NAND flash",
        "signal_type": "allocation",
        "severity": 4,
        "note": "NAND contract prices rising faster than DRAM for the first time this cycle (~70-75% vs ~58-63% QoQ in Q2), driven by enterprise-SSD demand from AI. eMMC/UFS faces the tightest gap — capacity overlaps enterprise SSD at worse margins, so it is lowest allocation priority; hits automotive/embedded buyers hardest.",
        "source": "TrendForce Q2 2026 contract price data (via Tom's Hardware)",
        "source_url": "https://www.tomshardware.com/pc-components/dram/dram-and-nand-contract-prices-to-climb-again-in-q2",
        "tags": "nand,emmc,ufs,ssd,allocation,automotive,embedded",
        "verdict_horizon": "2026-07-27",
        "device_type": "NAND,eMMC/UFS",
        "affected_industries": "Automotive,Industrial",
        "region": "Americas,EMEA,APAC",
    },
    # 3 — allocation lockout (CONCERN for small/mid buyers).
    {
        "observed_date": "2026-07-04",
        "entity": "DRAM allocation",
        "signal_type": "allocation",
        "severity": 4,
        "note": "Micron (FQ2 2026 call) can meet only 'half to two-thirds' of key-customer demand; expects supply short of demand beyond calendar 2026, with limited allocations and longer lead times hitting smaller/consumer buyers hardest. Phison CEO: 'every NAND manufacturer told us 2026 is sold out.'",
        "source": "Micron FQ2 2026 earnings call (via Tom's Hardware); Phison CEO (Digitimes)",
        "source_url": "https://www.tomshardware.com/pc-components/dram/micron-outlines-grim-outlook-for-dram-supply-in-first-earnings-call-since-killing-crucial-memory-and-ssd-brand-ceo-says-it-can-only-meet-half-to-two-thirds-of-demand",
        "tags": "dram,nand,allocation,leadtime,micron,phison,hyperscaler",
        "verdict_horizon": "2026-07-27",
        "device_type": "DRAM,NAND",
        "affected_industries": "Automotive,Industrial,Consumer,Computing",
        "region": "Americas,APAC",
    },
    # 4 — supply relief date (structural, log once).
    {
        "observed_date": "2026-07-04",
        "entity": "DRAM/HBM supply",
        "signal_type": "other",
        "severity": 3,
        "note": "Meaningful new capacity not expected until late 2027-2028. IDC projects 2026 bit-supply growth of ~16% DRAM / ~17% NAND, below the 20-30% historical norm — a structural reallocation, not a cyclical shortage (HBM consumes ~3-4x wafer capacity vs standard DDR5).",
        "source": "IDC 2026 global memory shortage outlook",
        "source_url": "https://www.idc.com/resource-center/blog/global-memory-shortage-crisis-market-analysis-and-the-potential-impact-on-the-smartphone-and-pc-markets-in-2026/",
        "tags": "dram,nand,hbm,capacity,structural,idc,ddr5",
        "verdict_horizon": "2027-12-31",
        "device_type": "DRAM,HBM,NAND",
        "affected_industries": "Computing,Automotive,Industrial",
        "region": "Americas,EMEA,APAC",
    },
    # 5 — cost pass-through propagation (confirmed downstream impact).
    {
        "observed_date": "2026-03-30",
        "entity": "PC/server OEM pricing",
        "signal_type": "other",
        "severity": 3,
        "note": "Cost pass-through propagating: Dell raised commercial-PC/workstation prices effective 30 Mar 2026 (memory cost 'out of our control'), Cisco raised compute list prices effective 7 Mar 2026. HP says memory is now ~35% of its PC bill of materials, ~double a year ago. Evidence the fab->contract->OEM price chain propagates on a traceable lag.",
        "source": "Dell (30 Mar 2026) & Cisco (7 Mar 2026) price actions; HP BOM disclosure",
        "source_url": "https://www.pcgamer.com/hardware/memory/hp-warns-that-memory-now-makes-up-around-35-percent-of-the-cost-its-pcs-double-that-of-a-year-ago/",
        "tags": "dell,cisco,oem,pc,server,passthrough,pricing",
        "verdict_horizon": "",
        "device_type": "DRAM,NAND",
        "affected_industries": "Computing",
        "region": "Americas",
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
        "device_type": "",
        "affected_industries": "Automotive,Industrial,Consumer",
        "region": "APAC",
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
        "device_type": "",
        "affected_industries": "",
        "region": "APAC",
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
