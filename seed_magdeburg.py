"""
Seed the ledger with the Intel Magdeburg backtest signals.

These are the retroactively-logged rows for the demo: public signals that
preceded the September 2024 pause announcement. observed_date = original
publication date. Verify each source/date yourself before showing this to
anyone — the demo's credibility IS the dates.

Run:  python seed_magdeburg.py
"""

from main import SignalIn, insert_signal, init_db

ROWS = [
    SignalIn(
        observed_date="2023-04-27",
        entity="Intel Magdeburg",
        signal_type="capex_cut",
        severity=3,
        note="FY capex guidance reduced; 'disciplined spending' language introduced on Q1 call.",
        source="Intel Q1 2023 earnings call",
        tags="intel,magdeburg,fab,europe,capex",
        device_type="Logic",
        affected_industries="Computing,Automotive",
        region="EMEA",
    ),
    SignalIn(
        observed_date="2023-06-14",
        entity="Intel Magdeburg",
        signal_type="equipment_absence",
        severity=4,
        note="No Magdeburg-attributable orders visible in ASML backlog commentary for a second consecutive quarter; a fab ~18 months from tooling should be placing them.",
        source="ASML investor update",
        tags="intel,magdeburg,asml,equipment,europe",
        device_type="Logic",
        affected_industries="Computing,Automotive",
        region="EMEA",
    ),
    SignalIn(
        observed_date="2023-08-02",
        entity="Intel Magdeburg",
        signal_type="subsidy",
        severity=4,
        note="German federal subsidy package unsigned past revised deadline; scope renegotiation reported.",
        source="Handelsblatt",
        tags="intel,magdeburg,subsidy,germany,europe",
        device_type="Logic",
        affected_industries="Computing,Automotive",
        region="EMEA",
    ),
    SignalIn(
        observed_date="2023-09-19",
        entity="Intel Magdeburg",
        signal_type="hiring",
        severity=4,
        note="Magdeburg-region Intel job postings down to single digits from 40+ in January; local hiring effectively frozen.",
        source="LinkedIn / StepStone listings",
        tags="intel,magdeburg,hiring,germany,europe",
        device_type="Logic",
        affected_industries="Computing,Automotive",
        region="EMEA",
    ),
    SignalIn(
        observed_date="2024-04-25",
        entity="Intel Magdeburg",
        signal_type="capex_cut",
        severity=5,
        note="Further capex discipline signaled; foundry losses widen, management declines to reconfirm Magdeburg timeline when asked.",
        source="Intel Q1 2024 earnings call",
        tags="intel,magdeburg,capex,europe",
        device_type="Logic",
        affected_industries="Computing,Automotive",
        region="EMEA",
    ),
    SignalIn(
        observed_date="2024-09-16",
        entity="Intel Magdeburg",
        signal_type="other",
        severity=5,
        note="OUTCOME: Intel announces ~2-year pause of Magdeburg project. Ledger had it DOUBTFUL on accumulated signals ~12 months prior.",
        source="Intel corporate announcement",
        tags="intel,magdeburg,outcome,europe",
        device_type="Logic",
        affected_industries="Computing,Automotive",
        region="EMEA",
    ),
]

if __name__ == "__main__":
    init_db()
    for r in ROWS:
        sid = insert_signal(r)
        print(f"logged #{sid}: {r.observed_date}  {r.entity}  [{r.signal_type}]  sev {r.severity}")
    print(f"\n{len(ROWS)} rows on ledger. Ask the wire: what's new with Intel Magdeburg?")
