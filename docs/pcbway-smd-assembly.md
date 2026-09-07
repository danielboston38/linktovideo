# Ordering SMD-only assembly from PCBWay

This board is mostly through-hole. Only four parts reflow, and they are all on
the top side, so PCBWay can do a single-sided SMT run and ship boards with the
fiddly parts already placed — leaving the through-hole half as ordinary
hand-soldering.

This document is the standing description of that order. The files themselves
are regenerated per run; see [Regenerating the package](#regenerating-the-package).

## The split

| | Parts | Who fits them |
|---|---|---|
| **SMD (PCBWay)** | C3, R6, U1, USB-C1 | reflowed, top side only |
| **Through-hole (you)** | C1, C2, D1, F1, J2, J3, J4, J5, Q1, R1, R2, R3, R4, R5, R7 | hand-soldered after delivery |

Four placements over four distinct part numbers — this is about as small as an
assembly order gets. TP1–TP4 are bare plated holes, not parts; they are
excluded from the BOM and the placement file.

## USB-C1 is Hybrid, not SMD

The Type-C receptacle has ten pads: six SMD signal pads and **four through-hole
shell stakes**. The shell stakes sit on `F.Paste`, so they are *pin-in-paste* —
the stencil deposits paste into the holes and they reflow in the same pass as
everything else. No separate operation, no hand-soldering.

It is listed as `Hybrid` in the Type column for exactly this reason. If it said
`SMD`, an assembler would have every reason to place the part and leave the four
mechanical anchors dry, and the connector that takes all the insertion force
would be held on by six 0.7 mm signal pads. **If PCBWay quotes this as
through-hole assembly or asks about the shell pins, the answer is: paste and
reflow them with the SMD pass.**

## Sourcing

PCBWay turnkey sources by MPN from wherever they can. Two of the four lines
need steering — checked 2026-09-07:

| Ref | MPN | Status |
|---|---|---|
| C3 | `CC0805KRX7R9BB104` | LCSC C49678 — basic part, 7.2 M in stock, $0.015 |
| R6 | `0805W8F2202T5E` | LCSC C17560 — basic part, 449 k in stock, $0.0035 |
| **U1** | `TPS2553DBVR` | **DigiKey 0, Mouser 0 (112-day factory lead). LCSC C55266 has 44 k @ $0.298 — insist on LCSC.** |
| **USB-C1** | `USB4970-00-A` | **Not an LCSC part.** DigiKey 5,956 cut-tape @ $0.32; T&R 4,000 @ MOQ 1,000. The one line PCBWay must buy in the West. |

U1 is the one that can quietly wreck a schedule. It is a live, in-production TI
part, but Western distribution is empty right now and the factory lead is close
to four months — while LCSC is sitting on 44,000 of them. Put the LCSC part
number in front of PCBWay rather than letting them quote it blind.

The LCSC column in the assembly BOM is there to make that easy; it is not part
of PCBWay's expected format, and they will ignore it if they prefer their own
source.

Substitution rules worth passing on:

- **R6 must stay ±1%.** It sets the eFuse current limit (`I_OS = 25.9 / R_kΩ`).
  A 5% part is not an acceptable substitute.
- **U1 must be `TPS2553` and not `TPS2552` or any `-1` suffix.** The 2-vs-3
  digit is active-high vs active-low enable, and `-1` is the latch-off variant.
  This board ties EN high and wants auto-retry.
- **C3 is ordinary** — any ≥16 V X7R 0805 is fine.

## What to upload

From the newest `pcbway_production/<timestamp>/` directory:

| File | Purpose |
|---|---|
| `gerbers/` + `drill/` | fabrication |
| `assembly_bom_smd.csv` | the four SMD lines, PCBWay turnkey column order |
| `assembly_cpl_smd.csv` | placements for those four only |
| `manifest.json` | what was checked, and the hashes it was checked against |

`bom.csv` and `cpl.csv` in the same directory are the **whole board**, all 19
parts. They are the right files for a fully-assembled order and the wrong ones
here — uploading them asks PCBWay to source and fit the through-hole parts too.
Use the `_smd` pair.

Order settings: 2 layers, 59.9 × 59.7 mm, 1.6 mm, assembly **top side only**,
minimum 5 boards. Assembly is manually quoted — expect 1–2 business days before
you see a price, which is the main scheduling difference from JLCPCB.

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
