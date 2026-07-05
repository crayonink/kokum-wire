"""
One-time, idempotent taxonomy backfill for a LIVE Kokum Wire ledger.

Rows logged before the device_type / affected_industries / region fields existed
(e.g. a Railway ledger seeded with the earlier scripts) carry blank tags, so the
device / industry / region filters return nothing for them. This reads the
canonical tags from the seed files (the single source of truth) and updates the
matching rows by entity via the keyed /admin/retag endpoint. logged_at and all
signal content are preserved. Safe to re-run.

Run this AFTER Railway has redeployed (so /admin/retag exists). It only UPDATEs
rows that are already on the ledger; if the NXP / STMicro rows aren't there yet,
run seed_mcu_auto.py as well to create them (already tagged).

Usage (PowerShell):
    $env:KOKUM_URL = "https://kokum-wire-production.up.railway.app"
    $env:LEDGER_WRITE_KEY = "<the key you set in Railway>"
    python seed_backfill_taxonomy.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

from seed_cycle2026 import ROWS as CYC
from seed_wfe import ROWS as WFE
from seed_mcu_auto import ROWS as MCU

BASE_URL = os.environ.get("KOKUM_URL", "").rstrip("/")
WRITE_KEY = os.environ.get("LEDGER_WRITE_KEY", "")

# Magdeburg rows are SignalIn objects (seed_magdeburg imports main); all six
# share one entity, so hardcode that single mapping rather than import main here.
MAGDEBURG = {
    "entity": "Intel Magdeburg",
    "device_type": "Logic",
    "affected_industries": "Computing,Automotive",
    "region": "EMEA",
}


def _tag(r: dict) -> dict:
    return {
        "entity": r["entity"],
        "device_type": r.get("device_type", ""),
        "affected_industries": r.get("affected_industries", ""),
        "region": r.get("region", ""),
    }


# One update per distinct entity (the endpoint updates all rows for that entity).
UPDATES, _seen = [MAGDEBURG], {"Intel Magdeburg"}
for r in CYC + WFE + MCU:
    if r["entity"] in _seen:
        continue
    _seen.add(r["entity"])
    UPDATES.append(_tag(r))


def main() -> None:
    if not BASE_URL:
        sys.exit("Set KOKUM_URL to your deployed base URL.")
    if not WRITE_KEY:
        sys.exit("Set LEDGER_WRITE_KEY to the key you configured in Railway.")

    req = urllib.request.Request(
        f"{BASE_URL}/admin/retag",
        data=json.dumps(UPDATES).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Ledger-Key": WRITE_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        sys.exit(f"FAILED ({e.code}): {detail}\n"
                 f"401 = wrong LEDGER_WRITE_KEY. "
                 f"404 = redeploy first (the /admin/retag endpoint is missing).")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach {BASE_URL}: {e.reason}")

    print(f"retagged {body.get('rows_updated', 0)} rows:")
    for ent, n in (body.get("updated") or {}).items():
        print(f"  {ent}: {n}")
    print("\nNow filter the live ledger:")
    print("  /signals?device=MCU   /signals?industry=Automotive   /signals?region=APAC")


if __name__ == "__main__":
    main()
