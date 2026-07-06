# Pricol Archetype Flow — Spec (DRAFT, for sign-off)

Status: **draft for review.** Nothing is built from this yet. Once the archetype
below is signed off, it becomes the data source for the flow-view feature.

---

## 1. What the feature is

Type a company (dropdown of pre-curated companies for the demo; free-text
post-YC) → see the semiconductor journey behind its products:

> **products → device types → who designs those chips → which foundries fab them
> → which OSATs package them → which distributors carry them → into the line**

…with the live ledger's signal state overlaid on each stage. The pitch:
*"We don't know your bill of materials yet — but we know what companies like you
are built from, and here's where that flow is under stress right now."* The flow
is the hook; *"give us your actual part numbers and this becomes exact"* is the
close.

---

## 2. The inference contract (non-negotiable rendering rules)

Every element carries a confidence level, and the UI must **show inference as
inference**. A wrong "fact" shown confidently about the viewer's own company
destroys the neutral-Bloomberg credibility that is the whole positioning.

| Level | Applies to | Source | Renders as |
|---|---|---|---|
| **PUBLIC** | Pricol's product lines | Pricol's own published catalogue | solid / plain |
| **DETERMINISTIC** | device types inside each product | settled electronics engineering | solid, "standard BOM" |
| **INFERRED** | designers / fabs / OSATs / distributors | typical for the device *class* — **not** Pricol's actual vendor | visibly "typical / likely", dashed / italic / "inferred" tag |

Two hard build constraints:
- **Pre-curated, not live-LLM.** Claude can help *pre-build* 3–5 target
  companies; each is human-verified before it is ever shown. No live generation
  in the demo — a hallucinated foundry relationship in front of a procurement
  lead is fatal.
- **Signal state is real, archetype is inferred.** The overlay at each stage is
  a genuine query over the dated ledger; the stage *entities* are the inferred
  archetype. Keep those two visually distinct.

---

## 3. The flow model

Stages, left to right:

```
DESIGN ──▶ FAB (+node class) ──▶ PACKAGE (OSAT) ──▶ DISTRIBUTE ──▶ INTEGRATE (Pricol line)
```

- A **stage node** = an `entity` (company) + a `device_type`.
- The **signal overlay** at a node = the existing ledger filter
  `?device=<type>&q=<entity>` → HOT / CALM / DARK from the matching rows'
  severities. This reuses the taxonomy already built; no new tables.

Signal legend:
- 🔴 **HOT** — matching rows at severity ≥ 3 (WATCH/CONCERN/DOUBTFUL).
- 🟡 **CALM** — matching rows, all severity ≤ 2 (logged but not alarming).
- ⚫ **DARK** — no rows logged for this stage yet (render gray, labelled "no live
  signal" — honest gap, never faked).

---

## 4. Layer 0 — Pricol products (PUBLIC)

| Product line | Chip content | In demo scope? |
|---|---|---|
| Digital / hybrid **instrument clusters** (Driver Information Systems) | high | ✅ **flagship** |
| **Telematics** / connected-vehicle units | high | ✅ secondary |
| **TPMS & sensors** | medium | ○ optional |
| Chargers / USB | low-medium | ○ optional |
| Pumps, actuators, wiping systems, switches | mechanical | ✗ out (low chip content) |

---

## 5. Flagship path — Digital Instrument Cluster

### 5a. Device BOM (Layer 1, DETERMINISTIC)

A modern hybrid cluster (TFT display + physical needles) contains:

1. **Cluster MCU / graphics SoC** — the brain
2. **LPDDR / DRAM** — frame buffer
3. **eMMC / NAND** — graphics assets + firmware storage
4. **Display driver IC (DDIC)** — drives the TFT panel
5. **PMIC** — power management
6. **CAN / LIN transceivers** — vehicle bus
7. **Stepper-motor driver ICs** — physical gauge needles (Pricol does hybrid
   analog+digital clusters, so this belongs)
8. **Sensors** — Hall / pressure / temperature
9. (supporting) supervisor/watchdog IC, boot flash

### 5b. Per-device archetype + live signal state

Designers/fabs/OSATs below are the **INFERRED archetype universe** for each
device class — the typical players, **not** a claim about Pricol's actual supplier.

| Device type | `device_type` tag | Designers (archetype) | Fab / node class | OSAT (archetype) | **Ledger today** |
|---|---|---|---|---|---|
| Cluster MCU / SoC | `MCU` / `Logic` | NXP (S32/i.MX), Renesas (RH850/R-Car), ST (Stellar/SPC5), Infineon (AURIX) | own + TSMC; **40–90nm** mature (16–28nm high-end SoC) | in-house + ASE / Amkor | 🟡 **CALM** — NXP/ST recovery rows (sev 2) |
| LPDDR / DRAM | `DRAM` | Samsung, SK hynix, Micron (Nanya/Winbond niche auto) | own DRAM fabs | own backend | 🔴 **HOT** — DRAM allocation + cycle-top rows |
| eMMC / NAND | `NAND` / `eMMC/UFS` | Kioxia, Samsung, Micron, SK hynix (+ Phison/SMI controllers) | own 3D-NAND fabs | own backend | 🔴 **HOT** — eMMC/UFS "lowest priority" + NAND allocation |
| Display driver (DDIC) | `Logic` (DDIC) | Novatek, Himax, Synaptics, Raydium | TSMC / UMC / **VIS**; **HV mature 40–150nm** | Chipbond, ChipMOS | ⚫ **DARK** |
| PMIC | `Analog` | TI, ST, Infineon, ROHM, Renesas | own + foundry; **BCD 130–180nm** | in-house + ASE | ⚫ **DARK** |
| CAN / LIN transceiver | `Analog` | NXP, TI, Infineon, Microchip, ROHM | own; mature / HV | in-house + OSAT | ⚫ **DARK** |
| Stepper-motor driver | `Analog` / `Discretes` | onsemi, TI, Allegro, Melexis | own + foundry; mature | in-house + OSAT | ⚫ **DARK** |
| Sensors (Hall/press/temp) | `Discretes` (sensors) | Allegro, Melexis, Infineon, TDK, Bosch, ST | MEMS + mature | own | ⚫ **DARK** |

Distribution layer (all devices): **Arrow, Avnet, WPG, Rutronik**, or **direct**
for a tier-1 the size of Pricol. (⚫ DARK — no distributor signals logged.)

---

## 6. Signal coverage — the honest read

| State | Stages | Backed by |
|---|---|---|
| 🔴 HOT | eMMC/NAND, LPDDR/DRAM | real dated rows (the memory squeeze — genuinely where the cluster is stressed) |
| 🟡 CALM | Cluster MCU | real rows (auto MCU normalized — honest, and makes HOT stand out) |
| ⚫ DARK | DDIC, PMIC, CAN, stepper, sensors, **all mature-node fabs, all OSATs, all distributors** | nothing logged yet |

**~2 of ~8 device paths are live-HOT, 1 CALM, ~5 DARK.** The memory path — the
part actually under stress — is fully backed by dated sources. The rest renders
as honest gray "typical path, no live signal."

This is the feature working as intended: **the demo is credible today** (real
signal where it matters, labelled inference elsewhere), and the DARK stages are a
natural "here's where we expand coverage" story rather than a weakness.

---

## 7. Secondary path — Telematics unit (condensed)

Adds to the cluster BOM: an **application processor / connectivity SoC**
(Qualcomm, MediaTek, NXP), a **cellular modem** (Qualcomm, Sony/Altair), a
**GNSS** chip, and often **NOR flash**. Same archetype pattern; same overlay.
Draft in full only if we demo telematics as a second company-path.

---

## 8. Gaps to fill (to turn DARK stages amber)

If we want the fab and package layers to light up, source a few rows (same
verify-from-primary discipline as the ASML/Lam rows):

1. **Mature-node automotive foundry capacity** — TSMC / UMC / VIS commentary on
   28–90nm auto utilization. *(This is exactly where allocation squeezes bite for
   automotive, so it's high-value.)* → lights the **FAB** stage.
2. **OSAT** — ASE / Amkor / JCET automotive packaging capacity. → lights the
   **PACKAGE** stage. (We already have the India OSAT row, tangentially.)
3. Optional: **DDIC** (Novatek/Himax) and **PMIC** demand notes.

~½ day of sourcing turns two DARK stages amber and makes the flow feel fuller.

---

## 9. Build mapping (for when this is signed off)

- **Static per-company graph**: `{ company, products[], per-product device[],
  per-device stage entities[] }` — curated & human-verified. One JSON per target
  company (Pricol first).
- **Signal overlay**: reuse the existing taxonomy — each stage node runs
  `?device=<type>` (+ entity match) against the ledger; severities → HOT/CALM/DARK.
  No new tables; the graph joins onto rows already tagged.
- **Flow view**: render the staged graph with the confidence + signal styling.
- Estimate: 3–4 focused days for one polished company.

---

## 10. Sign-off questions

1. **Is the cluster BOM right?** Especially: keep stepper-motor drivers (hybrid
   clusters) and the high-end graphics-SoC split? Anything missing?
2. **Is the designer/fab/OSAT archetype accurate enough** to put in front of a
   procurement lead as "typical"?
3. **Fill the DARK stages first (§8) or demo with honest gaps?**
4. **Which companies beyond Pricol** for the dropdown (3–5 total)?
