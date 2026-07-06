"""
Seed the WFE (wafer-fab-equipment) earnings signals into a LIVE Kokum Wire
instance over HTTP: ASML and Lam Research, the two upstream reads on whether new
memory/leading-edge capacity is actually being built.

These are the most-recent *reported* calls as of mid-2026 — ASML Q1 2026 and Lam
Research fiscal Q3 2026, both reported in April 2026. observed_date is the report
date; logged_at is stamped by the server when you run this (the track record).

Figures verified 2026-07-04 against primary sources:
  - ASML: Q1 2026 press release (asml.com, 15 Apr 2026) for net sales / income /
    margin / FY guidance; Q1 2026 earnings-call coverage for the memory-EUV,
    China %, and SK Hynix EUV detail (not in the press release itself).
  - Lam: FQ3 2026 earnings-call transcript (22 Apr 2026) for revenue, the
    DRAM/NAND systems-revenue mix, the $40B NAND-conversion timing, the $140B
    2026 WFE forecast, and China %. An initial secondary search misreported
    several of these (DRAM 23%, WFE $135B, China "declining"); the figures below
    are the transcript's actual numbers.

Before publishing to the demo, re-check each figure against the primary document
linked in source_url — the ledger's whole credibility is that the numbers are real.

Usage (PowerShell):
    $env:KOKUM_URL = "https://wire.kokumlabs.in"
    $env:LEDGER_WRITE_KEY = "<the key you set in Railway>"
    python seed_wfe.py

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
    # ASML — the lithography gate on new leading-edge and HBM capacity.
    {
        "observed_date": "2026-04-15",
        "entity": "ASML",
        "signal_type": "other",
        "severity": 3,
        "note": "ASML Q1 2026 (reported 15 Apr 2026): net sales EUR 8.8bn, net income EUR 2.8bn, gross margin 53% (EUR 4.1bn EUV within EUR 6.3bn system sales). FY2026 guidance raised to EUR 36-40bn on AI-driven memory demand. China fell to 19% of Q1 system sales (from 36% in Q4 2025); ~20% expected full-year, vs 41% in 2024. Memory-EUV surging: SK Hynix plans ~20 Low-NA EUV units over two years dedicated to HBM; ASML targets 60+ EUV shipments in 2026. Litho lead time is the real gate on when new HBM/leading-edge capacity comes online.",
        "source": "ASML Q1 2026 results (press release, 15 Apr 2026) + Q1 2026 earnings call",
        "source_url": "https://www.asml.com/en/news/press-releases/2026/q1-2026-financial-results",
        "tags": "asml,euv,lithography,hbm,memory,capex,skhynix,china,capacity",
        "verdict_horizon": "2026-12-31",
        "device_type": "DRAM,HBM,NAND,Logic",
        "affected_industries": "Computing,Automotive",
        "region": "EMEA,China,APAC",
    },
    # Lam Research — deposition/etch demand; the NAND-conversion timeline.
    {
        "observed_date": "2026-04-22",
        "entity": "Lam Research",
        "signal_type": "other",
        "severity": 3,
        "note": "Lam Research FQ3 2026 (call 22 Apr 2026): revenue $5.84bn, +24% YoY / +9% QoQ. DRAM 27% of systems revenue (up from 23% the prior quarter) on the 1C / 4F2 shift; NAND 12% (up from 11%). Now sees the ~$40bn NAND-conversion investment landing MOSTLY BEFORE the end of CY2027 — an accelerated timeline. Raised 2026 WFE forecast to $140bn 'with a bias to the upside', vs ~$110bn in 2025. China 34% of revenue (from 35%). Etch/deposition demand corroborates the memory up-cycle and the pre-2028 capacity build.",
        "source": "Lam Research FQ3 2026 earnings call transcript (22 Apr 2026)",
        "source_url": "https://www.fool.com/earnings/call-transcripts/2026/04/22/lam-research-lrcx-q3-2026-earnings-transcript/",
        "tags": "lamresearch,wfe,nand,dram,etch,deposition,capex,china,capacity",
        "verdict_horizon": "2027-12-31",
        "device_type": "DRAM,NAND",
        "affected_industries": "Computing,Automotive,Industrial,Consumer",
        "region": "Americas,China,APAC",
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

    print(f"\n{len(ROWS)} WFE signals sent. Ask the wire: what are ASML and Lam saying about capacity?")


if __name__ == "__main__":
    main()
