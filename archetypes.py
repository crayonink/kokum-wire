"""
Company archetype graphs for the flow / geo view (see docs/pricol-archetype.md).

CURATED and human-verified. Everything supplier- and geography-level here is the
INFERRED *typical* picture for each device class — NOT a claim about the company's
actual vendor or sourcing. The device list itself is deterministic (what the
product contains); the chain entities and the fab-origin shares are inference and
must be shown as such. Signal state is computed LIVE from the ledger by /flow —
never stored here.

`match`   — token(s) looked up against each ledger row's device_type/tags to set
            the device's signal state.
`origins` — inferred share of where that device class is typically WAFER-FABBED,
            by country code (see COUNTRIES). Shares are approximate and sum ~1.0;
            /flow aggregates them across the BOM into a per-country probability.
"""

# Country metadata for the world map. lon/lat drive the equirectangular plot;
# region maps a country onto the ledger's region taxonomy.
COUNTRIES = {
    "TW": {"name": "Taiwan",        "lon": 121.0, "lat": 23.7, "region": "APAC"},
    "KR": {"name": "South Korea",   "lon": 127.8, "lat": 36.5, "region": "APAC"},
    "JP": {"name": "Japan",         "lon": 138.0, "lat": 37.5, "region": "Japan"},
    "US": {"name": "United States", "lon": -98.0, "lat": 39.5, "region": "Americas"},
    "CN": {"name": "China",         "lon": 104.0, "lat": 35.0, "region": "China"},
    "DE": {"name": "Germany",       "lon": 10.4,  "lat": 51.2, "region": "EMEA"},
    "FR": {"name": "France",        "lon": 2.4,   "lat": 47.0, "region": "EMEA"},
}

PRICOL = {
    "company": "Pricol",
    "product": "Digital instrument cluster",
    "product_note": "driver information system — hybrid TFT display + physical needles",
    "devices": [
        {
            "device": "Cluster MCU / SoC",
            "match": ["mcu"],
            "designers": ["NXP", "Renesas", "STMicroelectronics", "Infineon"],
            "fab": "own + TSMC",
            "node": "40–90nm mature (16–28nm high-end SoC)",
            "osat": "in-house + ASE / Amkor",
            "distributors": ["Arrow", "Avnet", "WPG", "direct"],
            "origins": {"TW": 0.45, "JP": 0.15, "DE": 0.15, "FR": 0.10, "US": 0.10, "CN": 0.05},
        },
        {
            "device": "LPDDR / DRAM",
            "match": ["dram", "lpddr"],
            "designers": ["Samsung", "SK hynix", "Micron"],
            "fab": "own DRAM fabs",
            "node": "",
            "osat": "own backend",
            "distributors": ["Arrow", "WPG", "direct"],
            "origins": {"KR": 0.65, "US": 0.20, "JP": 0.05, "TW": 0.05, "CN": 0.05},
        },
        {
            "device": "eMMC / NAND",
            "match": ["emmc", "nand"],
            "designers": ["Kioxia", "Samsung", "Micron", "SK hynix"],
            "fab": "own 3D-NAND fabs",
            "node": "",
            "osat": "own backend",
            "distributors": ["Arrow", "WPG", "direct"],
            "origins": {"KR": 0.40, "JP": 0.30, "US": 0.20, "CN": 0.10},
        },
        {
            "device": "Display driver (DDIC)",
            "match": ["ddic"],
            "designers": ["Novatek", "Himax", "Synaptics"],
            "fab": "TSMC / UMC / VIS",
            "node": "HV mature 40–150nm",
            "osat": "Chipbond / ChipMOS",
            "distributors": ["WPG", "direct"],
            "origins": {"TW": 0.85, "CN": 0.10, "KR": 0.05},
        },
        {
            "device": "PMIC",
            "match": ["pmic"],
            "designers": ["TI", "STMicroelectronics", "Infineon", "ROHM"],
            "fab": "own + foundry",
            "node": "BCD 130–180nm",
            "osat": "in-house + ASE",
            "distributors": ["Arrow", "Avnet"],
            "origins": {"US": 0.30, "TW": 0.20, "JP": 0.20, "DE": 0.15, "CN": 0.10, "KR": 0.05},
        },
        {
            "device": "CAN / LIN transceiver",
            "match": ["can-transceiver"],
            "designers": ["NXP", "TI", "Infineon", "Microchip"],
            "fab": "own",
            "node": "mature / HV",
            "osat": "in-house + OSAT",
            "distributors": ["Arrow", "Avnet"],
            "origins": {"DE": 0.30, "US": 0.25, "TW": 0.20, "JP": 0.15, "CN": 0.10},
        },
        {
            "device": "Stepper-motor driver",
            "match": ["stepper"],
            "designers": ["onsemi", "TI", "Allegro", "Melexis"],
            "fab": "own + foundry",
            "node": "mature",
            "osat": "in-house + OSAT",
            "distributors": ["Arrow", "Avnet"],
            "origins": {"US": 0.30, "JP": 0.25, "TW": 0.20, "DE": 0.15, "CN": 0.10},
        },
        {
            "device": "Sensors (Hall / pressure / temp)",
            "match": ["hall-sensor"],
            "designers": ["Allegro", "Melexis", "Infineon", "TDK", "Bosch"],
            "fab": "MEMS + mature",
            "node": "",
            "osat": "own",
            "distributors": ["Avnet", "direct"],
            "origins": {"DE": 0.35, "US": 0.25, "JP": 0.20, "TW": 0.10, "CN": 0.10},
        },
    ],
}

# Registry keyed by lowercase company name. Add curated companies here.
ARCHETYPES = {"pricol": PRICOL}
