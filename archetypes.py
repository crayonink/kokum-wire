"""
Company archetype graphs for the flow view (see docs/pricol-archetype.md).

CURATED and human-verified. The stage entities (designers / fab / OSAT /
distributors) are the INFERRED *typical* universe for each device class — NOT a
claim about the company's actual vendor. The device list itself is deterministic
(what the product contains); the supply-chain entities are inference and must be
shown as such. Signal state at each device is computed LIVE from the ledger by
/flow — it is never stored here.

`match` holds the token(s) looked up against each ledger row's device_type/tags
to decide the device's signal state. Memory/MCU tokens hit real rows; the tokens
for parts we haven't sourced yet (DDIC, PMIC, CAN, stepper, sensor) intentionally
match nothing, so those stages render as honest DARK until the gap-fill rows land.
"""

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
        },
        {
            "device": "LPDDR / DRAM",
            "match": ["dram", "lpddr"],
            "designers": ["Samsung", "SK hynix", "Micron"],
            "fab": "own DRAM fabs",
            "node": "",
            "osat": "own backend",
            "distributors": ["Arrow", "WPG", "direct"],
        },
        {
            "device": "eMMC / NAND",
            "match": ["emmc", "nand"],
            "designers": ["Kioxia", "Samsung", "Micron", "SK hynix"],
            "fab": "own 3D-NAND fabs",
            "node": "",
            "osat": "own backend",
            "distributors": ["Arrow", "WPG", "direct"],
        },
        {
            "device": "Display driver (DDIC)",
            "match": ["ddic"],
            "designers": ["Novatek", "Himax", "Synaptics"],
            "fab": "TSMC / UMC / VIS",
            "node": "HV mature 40–150nm",
            "osat": "Chipbond / ChipMOS",
            "distributors": ["WPG", "direct"],
        },
        {
            "device": "PMIC",
            "match": ["pmic"],
            "designers": ["TI", "STMicroelectronics", "Infineon", "ROHM"],
            "fab": "own + foundry",
            "node": "BCD 130–180nm",
            "osat": "in-house + ASE",
            "distributors": ["Arrow", "Avnet"],
        },
        {
            "device": "CAN / LIN transceiver",
            "match": ["can-transceiver"],
            "designers": ["NXP", "TI", "Infineon", "Microchip"],
            "fab": "own",
            "node": "mature / HV",
            "osat": "in-house + OSAT",
            "distributors": ["Arrow", "Avnet"],
        },
        {
            "device": "Stepper-motor driver",
            "match": ["stepper"],
            "designers": ["onsemi", "TI", "Allegro", "Melexis"],
            "fab": "own + foundry",
            "node": "mature",
            "osat": "in-house + OSAT",
            "distributors": ["Arrow", "Avnet"],
        },
        {
            "device": "Sensors (Hall / pressure / temp)",
            "match": ["hall-sensor"],
            "designers": ["Allegro", "Melexis", "Infineon", "TDK", "Bosch"],
            "fab": "MEMS + mature",
            "node": "",
            "osat": "own",
            "distributors": ["Avnet", "direct"],
        },
    ],
}

# Registry keyed by lowercase company name. Add curated companies here.
ARCHETYPES = {"pricol": PRICOL}
