"""
Seed the Strait-of-Hormuz materials signals into a LIVE Kokum Wire instance.

Origin: a practitioner signal from Claus (network input), independently verified
2026-07-06 before logging — the ledger's rule is verify-before-log, and this is
the moat sentence for the YC application: a practitioner network feeds signals in,
and the ledger only publishes what checks out.

Verified 2026-07-06 against tier-1 coverage:
  - Helium: Iranian strikes on Qatar's Ras Laffan (late Feb 2026); ~27-30% of
    global helium supply offline since the early-March Hormuz closure; ultra-pure
    6N (fab-grade, JIT, no stockpile) hit hardest; spot +40-100% (Bank of America);
    South Korea sources ~65% of its helium from Qatar.
    Fortune (2026-03-21), Forbes (2026-04-07), AGBI (2026-03).
  - Photoresist solvents: Japan imports >40% of its naphtha from the Middle East;
    the Hormuz cutoff choked PGME/PGMEA (naphtha spot $600 -> $1,190/t, +92%);
    Shin-Etsu / TOK / JSR / Fujifilm / Nissan warned Samsung & SK Hynix (~22 Apr);
    switching solvent sources needs ~1yr Process-Change-Notification requalification.
    TrendForce (2026-04-24), The Elec, Seoul Economic Daily.
  Correction to Claus's mechanism (kept in the note): photoresists are not made in
  the Middle East (Japan dominates) — the chokepoint is upstream naphtha/solvent
  feedstock. Bromine (~2/3 from Israel/Jordan) is a second adjacent ME material.

observed_date is the date the call was made/logged (2026-07-06); logged_at is set
by the server. RE-CONFIRM the figures against the linked sources before the demo.

Usage (PowerShell):
    $env:KOKUM_URL = "https://wire.kokumlabs.in"
    $env:LEDGER_WRITE_KEY = "<the key you set in Railway>"
    python seed_hormuz.py

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
    # 1 — FORWARD CALL: Hormuz materials squeeze reaches mature-node automotive.
    {
        "observed_date": "2026-07-06",
        "entity": "Hormuz materials (helium + solvents)",
        "signal_type": "allocation",
        "severity": 4,
        "note": "FORWARD CALL (practitioner: Claus; independently verified 06 Jul 2026). The Strait of Hormuz closure since early March 2026 has rebased two chip-materials inputs at once. (1) Helium: Iranian strikes on Qatar's Ras Laffan (late Feb 2026) took ~27-30% of global supply offline; ultra-pure 6N (fabs, JIT, no stockpile) worst hit, spot +40-100% (BofA); South Korea sources ~65% of helium from Qatar; SEMI sees 4-6 months to normalize even after reopening, and destroyed LNG trains face 3-5yr rebuilds (turbine queues). (2) Photoresist solvents: Japan imports >40% of naphtha from the Middle East; PGME/PGMEA choked (naphtha $600->$1,190/t, +92%); Shin-Etsu/TOK/JSR/Fujifilm/Nissan warned Samsung & SK Hynix; switching solvent sources needs ~1yr requalification. (Bromine, ~2/3 from Israel/Jordan, is a second adjacent ME material.) Most exposed: tier-2/3 mature-node fabs with thin buffers and low leverage — where automotive silicon lives. FALSIFIABLE: expect lead-time extension or price escalation on automotive-grade mature-node parts (MCU / analog / PMIC / discretes) in the Q4 2026-H1 2027 window (weeks-to-months of buffer + 4-6 month post-reopen recovery lag).",
        "source": "Practitioner signal (Claus), verified 06 Jul 2026 vs Fortune, TrendForce, Bank of America, SEMI",
        "source_url": "https://www.trendforce.com/news/2026/04/24/news-japan-photoresist-suppliers-flag-shortage-amid-40-middle-east-naphtha-reliance-risks-for-chipmakers/",
        "tags": "hormuz,helium,photoresist,pgmea,naphtha,bromine,qatar,japan,materials,claus,mature-node,automotive",
        "verdict_horizon": "2027-06-30",
        "device_type": "MCU,Analog,Discretes",
        "affected_industries": "Automotive,Industrial",
        "region": "EMEA,Japan,APAC",
    },
    # 2 — CORROBORATION of the 04 Jul 2026 NAND cycle WATCH (append-only, not an edit).
    {
        "observed_date": "2026-07-06",
        "entity": "DRAM/NAND cycle",
        "signal_type": "other",
        "severity": 4,
        "note": "CORROBORATION of the 04 Jul 2026 NAND cycle WATCH (practitioner: Claus; verified 06 Jul 2026). The memory squeeze now carries independent SUPPLY-side drivers on top of the demand cycle. Samsung and SK Hynix are hit simultaneously by (a) ultra-pure helium — South Korea sources ~65% from Qatar's Ras Laffan, ~27-30% of global supply offline since the early-March Hormuz closure, spot +40-100% — and (b) photoresist solvents PGME/PGMEA, choked by Japan's >40% Middle East naphtha reliance, with Shin-Etsu/TOK/JSR warning both makers and ~1yr requalification to re-source. PGMEA also feeds the temporary bonding adhesives used in HBM packaging. Net: the July-4 demand-side WATCH now has two corroborating supply-side drivers — conviction that memory tightness holds through 2026 is upgraded.",
        "source": "Practitioner signal (Claus), verified 06 Jul 2026 vs Fortune, TrendForce, Bank of America",
        "source_url": "https://fortune.com/2026/03/21/iran-war-helium-shortage-qatar-chip-supply-chains-ai-boom/",
        "tags": "nand,dram,hbm,memory,helium,photoresist,pgmea,samsung,skhynix,hormuz,claus,corroboration",
        "verdict_horizon": "2026-12-31",
        "device_type": "DRAM,NAND,HBM",
        "affected_industries": "Computing,Automotive,Industrial,Consumer",
        "region": "APAC,Japan,EMEA",
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
                     f"401 = wrong LEDGER_WRITE_KEY. 404 = wrong KOKUM_URL.")
        except urllib.error.URLError as e:
            sys.exit(f"Could not reach {BASE_URL}: {e.reason}")

    print(f"\n{len(ROWS)} Hormuz materials signals sent. "
          f"Ask the wire: what's the risk to automotive chips from Hormuz?")


if __name__ == "__main__":
    main()
