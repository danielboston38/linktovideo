# Ordering SMD-only assembly from PCBWay

This board is mostly through-hole. Only four parts reflow, and all four are on the
top side. PCBWay can thus do a single-sided SMT run and ship boards with the fiddly
parts already placed. The through-hole half stays ordinary hand-soldering.

This document describes that order. The tooling regenerates the files themselves for
each run. See [Regenerating the package](#regenerating-the-package).

## The split

| | Parts | Who fits them |
|---|---|---|
| **SMD (PCBWay)** | C3, R6, U1, USB-C1 | reflowed, top side only |
| **Through-hole (you)** | C1, C2, D1, F1, J2, J3, J4, J5, Q1, R1, R2, R3, R4, R5, R7 | hand-soldered after delivery |

The order has four placements over four distinct part numbers. An assembly order does
not get much smaller than this.

TP1–TP4 are bare plated holes, not parts. The BOM and the placement file exclude them.

## USB-C1 is Hybrid, not SMD

The Type-C receptacle has ten pads: six SMD signal pads and **four through-hole shell
stakes**. The shell stakes sit on `F.Paste`, so they are *pin-in-paste*. The stencil
deposits paste into the holes, and the stakes reflow in the same pass as the other
parts. No separate operation and no hand-soldering are necessary.

The BOM lists the part as `Hybrid` in the Type column for exactly this reason. If it
said `SMD`, an assembler would have every reason to place the part and leave the four
mechanical anchors dry. Six 0.7 mm signal pads would then hold the connector that
takes all the insertion force.

> [!CAUTION]
> **Tell PCBWay to paste and reflow the four shell stakes with the SMD pass.**
> They can quote this part as through-hole assembly, or ask about the shell pins.
> The answer in both cases is the instruction above.

## Sourcing

PCBWay turnkey sources by MPN from wherever they can. All four SMD lines are
now LCSC parts — checked 2026-09-09:

| Ref | MPN | Status |
|---|---|---|
| C3 | `CC0805KRX7R9BB104` | LCSC C49678 — basic part, 7.2 M in stock, $0.015 |
| R6 | `0805W8F2202T5E` | LCSC C17560 — basic part, 449 k in stock, $0.0035 |
| **U1** | `TPS2553DBVR` | **DigiKey 0, Mouser 0 (112-day factory lead). LCSC C55266 has 44 k @ $0.298 — insist on LCSC.** |
| **USB-C1** | `USB4125-GF-A-0190` | LCSC C5246813 — ~630–3,670 in stock, MOQ 1, $0.85. **From v2 this replaces the `USB4970-00-A`, which LCSC does not stock**; the USB4125 is a different GCT line number that LCSC carries, and the board was already laid out to its land pattern. Stock is thin, so tell them to buy spares. |

U1 is the part that can quietly wreck a schedule. It is a live, in-production TI part,
but Western distribution is empty right now. The factory lead is close to four months,
while LCSC holds 44,000 of them. Put the LCSC part number in front of PCBWay. Do not
let them quote it blind.

The LCSC column in the assembly BOM makes that easy. It is not part of the expected
format of PCBWay, and they will ignore it if they prefer their own source.

Substitution rules worth passing on:

- **R6 must stay ±1%.** It sets the eFuse current limit (`I_OS = 25.9 / R_kΩ`).
  A 5% part is not an acceptable substitute.
- **U1 must be `TPS2553` and not `TPS2552` or any `-1` suffix.** The 2-against-3
  digit is active-high against active-low enable. The `-1` suffix is the latch-off
  variant. This board ties EN high and needs auto-retry.
- **C3 is ordinary.** Any ≥16 V X7R 0805 is correct.

## What to upload

From the newest `pcbway_production/<timestamp>/` directory, upload these files:

| File | Purpose |
|---|---|
| `gerbers/` + `drill/` | fabrication |
| `assembly_bom_smd.csv` | the four SMD lines, PCBWay turnkey column order |
| `assembly_cpl_smd.csv` | placements for those four only |
| `manifest.json` | what was checked, and the hashes it was checked against |

> [!CAUTION]
> **Do not upload `bom.csv` and `cpl.csv`.** These two files in the same directory
> cover the **whole board**, all 19 parts. They are the correct files for a
> fully-assembled order and the wrong ones here. If you upload them, you ask PCBWay to
> source and fit the through-hole parts too. Use the `_smd` pair.

Order settings: 2 layers, 59.9 × 59.7 mm, 1.6 mm, assembly **top side only**,
minimum 5 boards. PCBWay quotes assembly manually, so expect 1–2 business days before
you see a price. This delay is the main scheduling difference from JLCPCB.

## Fabrication notes

The board sits well inside PCBWay's standard process: minimum track 0.2 mm and
clearance 0.2 mm against their 0.1 mm capability, minimum drill 0.3 mm against
0.15 mm. Nothing here needs an advanced-process surcharge.

One DFM point worth knowing rather than acting on: C3, R6 and U1 use KiCad's
`HandSolder` / `Handsoldering` footprint variants, whose lands extend further
out than the IPC nominal. They reflow fine — PCBWay builds these every day — but
they take more paste than the nominal land would, which is a mild tombstoning
risk on the two 0805s. The footprints were chosen so the board stays
hand-assemblable, which is the right trade for this project. If a future
revision ever goes fully machine-assembled, switching those three to the
standard variants is the cleanup.

Order a framed stencil only if you plan to reflow boards yourself. It is not
needed for a PCBWay assembly order.

## Regenerating the package

The gate refuses to package a board that has not passed DRC and schematic
parity, so this is also the verification step. `prefab_gate` comes from
[danielboston38/prefab-gate](https://github.com/danielboston38/prefab-gate),
which is a separate tool rather than part of this project:

```bash
export KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
python3 tools/check_nets.py
prefab_gate package nes_power_video.kicad_pcb --out pcbway_production
python3 tools/pcbway_assembly.py nes_power_video.kicad_pcb pcbway_production/<new-timestamp>
```

`pcbway_assembly.py` reads the mount type from the board's own `(attr ...)` and
pad list rather than a hand-kept list of designators, so a part that changes
mounting — or a new SMD part — lands on the correct side of the split without
anyone remembering to update it. It refuses to write anything if an SMD part has
no MPN, since that is the field PCBWay sources by, and it prints whether the SMD
parts span one side or two.
