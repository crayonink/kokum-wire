"""
Pre-demo check for a live Kokum Wire instance. Read-only: it does NOT write
to the ledger. Run it against your Railway URL right before demoing.

Usage (PowerShell):
    $env:KOKUM_URL = "https://wire.kokumlabs.in"
    python preflight.py

Exit code is 0 only if every check passes.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("KOKUM_URL", "").rstrip("/")
FALLBACK_TAG = "[Composed without LLM"
DEMO_Q = "what's new with Intel Magdeburg?"

ok = True


def result(passed: bool, label: str, detail: str = "") -> None:
    global ok
    ok = ok and passed
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail else ""))


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def post(path: str, body: dict, headers: dict):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def main() -> None:
    if not BASE:
        sys.exit("Set KOKUM_URL, e.g. https://wire.kokumlabs.in")
    print(f"Kokum Wire pre-flight against {BASE}\n")

    # 1. Health / reachability
    try:
        _, h = get("/health")
    except Exception as e:
        sys.exit(f"  [FAIL] /health unreachable — {e}\nIs the service deployed and awake?")
    result(h.get("ok") is True, "service healthy", "/health ok")

    # 2. Ledger seeded (survives redeploys only if a volume is mounted)
    n = h.get("signals_on_ledger", 0)
    result(n >= 6, "ledger seeded", f"{n} signals on ledger (expected >= 6)")

    # 3. API key present
    result(h.get("llm") is True, "ANTHROPIC_API_KEY set", f'health llm={h.get("llm")}')

    # 4. LLM path actually WORKS (key valid + model reachable), not silently falling back
    try:
        _, a = post("/ask", {"question": DEMO_Q}, {})
    except Exception as e:
        sys.exit(f"  [FAIL] /ask failed — {e}")
    answer = a.get("answer", "")
    result(bool(a.get("signals")), "dispatch returns evidence", f'{len(a.get("signals", []))} signals cited')
    if h.get("llm") is True:
        result(FALLBACK_TAG not in answer, "LLM composed the dispatch",
               "fallback tag present — key set but call is failing (bad key / model / quota)"
               if FALLBACK_TAG in answer else f'verdict={a.get("verdict")}')
    else:
        print("  [ -- ] LLM composition skipped (no key; using deterministic fallback)")

    # 5. Write endpoint is protected (send a deliberately WRONG key — never inserts)
    try:
        post("/signals", {"observed_date": "2000-01-01", "entity": "x", "signal_type": "other",
                          "severity": 1, "note": "x", "source": "x"},
             {"X-Ledger-Key": "definitely-not-the-key"})
        result(False, "write endpoint protected", "wrong key was accepted (!)")
    except urllib.error.HTTPError as e:
        result(e.code == 401, "write endpoint protected", f"wrong key -> HTTP {e.code} (want 401)")

    print()
    if ok:
        print("ALL CHECKS PASSED — safe to demo.")
    else:
        print("SOME CHECKS FAILED — fix the FAILs above before demoing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
