# Link to Video

A replacement for the RF modulator in the original Nintendo Entertainment System (NES-001). Drops into the stock RF module slot inside the shell and provides composite video and USB-C power in place of a part that fails by design.

<a href="https://certification.oshwa.org/us002842.html">
  <img src="./certification-mark-US002842-stacked.svg" alt="OSHWA Certified Open Source Hardware UID US002842" width="140" align="right">
</a>

> [!CAUTION]
> **Safety advisory for boards built before 2026-09-08.**
> On every board fabricated so far, the USB-C VBUS input reaches F1 through 9.06 mm of
> 0.2 mm-wide trace. That trace fails at a current well below F1's guaranteed trip
> current. If a fault occurs downstream, **F1 cannot protect the input trace on the
> board**.
> The defect has no effect on normal operation (48 °C, 17 mV drop). It is a
> fault-tolerance defect, not a wear-out defect: a board that works now will keep working.
> Commit [`247334c`](../../commit/247334c) corrects the layout. Reworking an affected
> board takes about 15 minutes.
>
> **→ Read the full advisory: [docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md](docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md)**

> **Renamed.** The first revision of this project was called **Kirby's New Dream**.
> From v2 on, it is **Link to Video**. Anything carrying the old name is the same
> project: the v1 board silkscreen, the 2026-07-16 PCBWay fab package, and older commits.
> The GitHub repository has been renamed too, and the old `kirbysnewdream` URL still
> redirects to it.

## Why this board exists

The NES-001's RF modulator already carries composite video, so this isn't about
adding an output the console lacks. It's about replacing a part that reliably
destroys itself.

Nintendo packed the modulator's regulator and RF stages into a sealed can with no
ventilation. It cooks its own electrolytics, they leak, and the electrolyte eats
the traces underneath. Across three NES-001 units on the author's bench, **all
three** had modulator failures from exactly this — including a Mitsumi unit that
looked pristine externally and had every capacitor leaking inside.

So the modulator is a consumable on a forty-year-old console, and the usual
options are to recap a corroded board or to fit an aftermarket board. This is the
second option, with the power input modernised to USB-C while the slot is open.

## Disclosure

This project's schematic design, debugging, and documentation were developed with the assistance of AI (Claude, by Anthropic). All hardware was hand-assembled, tested, and validated by the author. Use, review, and verify independently before building.

## Status

🟡 First prototype assembled and power-tested successfully (5V confirmed clean on rail, no protection trips). Video output path **does not work on v1 hardware** — traced to a schematic defect in which Q1's emitter node was shorted to the +5V rail (see Known Issues). Fixed in source; v1 boards need a rework.

<!-- Swap the line above for something like this once video's confirmed:
🟢 Fully validated — power and composite video both confirmed working on hardware.
-->

## Features

- USB-C power input (power only, no data lines)
- Composite video output
- Active overcurrent protection: TPS2553 eFuse with a ~1.18 A resistor-programmed limit, soft-start and thermal shutdown, and a polyfuse as backup
- Fits inside the original NES shell at the stock RF module location
- Bring-up test points for video, ground, +5 V and audio, labeled on the silkscreen
- Header that feeds an external 8-pin mini-DIN RGB connector (NESRGB)
- All resistor and capacitor values printed on the silkscreen (v1 had four identical, unlabeled axial footprints holding four different values, which led to three wrong-resistor build errors)
- 2-layer PCB, designed in KiCad

## Power path

```
USB-C  ──  F1 polyfuse  ──  U1 TPS2553 eFuse  ──  +5V rail  ──  J4.3 → NES
  VBUS      2.0A hold        ~1.18A limit          C1 100µF
            3.8A trip        soft-start            D1 TVS
            (backup)         thermal shutdown
```

F1 doesn't trip until 3.8 A, and the console only draws about 0.5–0.7 A, so on its
own F1 protects almost nothing. U1 does the real work. F1 is there in case the eFuse
fails short.

R6 on U1's ILIM pin sets the current limit. The relationship is
**inverse**: a larger resistor gives a *lower* limit.

| R6 | Limit (typ) |
|---|---|
| 15 kΩ | 1700 mA |
| 20 kΩ | 1295 mA |
| **22 kΩ (fitted)** | **~1180 mA** |
| 49.9 kΩ | 520 mA |
| 210 kΩ | 130 mA |

As a rule of thumb, I_OS(A) ≈ 25.9 / R6(kΩ), valid across TI's recommended range of
15 kΩ–232 kΩ.

U1's EN (pin 3) is active-high and tied to U1's own input, so the switch is always on.
FAULT (pin 4) is open-drain and left unconnected, since nobody can see an indicator
inside a closed NES shell. If you want a fault LED anyway, FAULT can sink 25 mA directly.

**Useful side effect: a reversed D1 is survivable.** D1 is a unidirectional TVS, so
installing it backwards puts a forward-biased diode straight across the 5 V rail.
Before the board had U1, that was a near-dead short, with only the polyfuse (which
takes seconds to react) in the way. Now the eFuse holds the current to ~1.18 A and
then shuts down thermally, so the mistake limits itself instead of destroying parts.

## Test points (v2)

The board has four through-hole test points (2.0 mm pad, 1.0 mm drill) for bring-up.
Each takes a 0.64 mm square header pin, so you can solder pins in and hang scope
grabbers off them.

The silkscreen shows only the signal name (`VIDEO`, `GND`, `+5V`, `AUDIO`), so you
can read the board without this table. The reference designators are on F.Fab, for
the fab drawings.

The first pass of v2 had this backwards: the signal names were on F.Fab, which never
reaches the physical board, so the silkscreen showed only `TP1`–`TP4`.

| TP  | Net          | Location (mm) | Notes |
|-----|--------------|---------------|-------|
| TP1 | `/VIDEO_OUT` | 62.0, 60.0    | Jack-side video, after C2 and the 75 Ω series resistor R5. This is what the TV sees. A high-impedance probe reads roughly double the terminated amplitude. |
| TP2 | `GND`        | 58.5, 60.0    | Connects directly to the B.Cu ground pour. |
| TP3 | `/5V`        | 52.0, 43.1    | On the protected 5 V trunk, downstream of F1 and the TPS2553. |
| TP4 | `/AUDIO_OUT` | 65.9, 28.35   | Audio pass-through between J4 pin 2 and J2. |

TP2 is just a convenience. The whole back layer is ground pour, so any B.Cu feature
works for a ground clip.

To probe the buffer itself rather than its output, go straight to Q1's emitter leg.
`Net-(Q1-E)` has no test point.

## RGB output (v2)

This board can feed the RGB connector for the [NESRGB](https://etim.net.au/nesrgb/)
board, which uses the 8-pin mini-DIN pinout of the Micomsoft XRGB-mini Framemeister.

The connector itself is **not** on this board. It comes with the NESRGB kit as a
panel-mount jack that is epoxied into a 12 mm hole in the shell. R/G/B run straight
from the NESRGB to that jack, and **J5** on this board supplies the other three pins:

| J5 pin | Net          | mini-DIN pin | |
|--------|--------------|--------------|---|
| 1 | `/RGB_VIDEO` | 3 | Composite video / sync, 75 Ω terminated |
| 2 | `GND`        | 4 | |
| 3 | `/5V`        | 5 | Downstream of the TPS2553, so it is current-limited |

Mini-DIN pins 1 and 2 are unconnected. Pins 6, 7 and 8 are Blue, Green and Red from
the NESRGB. The pinout carries no audio, so audio stays on the RCA jack. That was a
deliberate choice by Tim Worthington, to keep video noise out of the audio.

**Why R7 exists.** The output of the video buffer (`/VIDEO_BUF`, Q1's emitter
through C2) now feeds two outputs, and each needs its own 75 Ω source termination:
R5 for the RCA jack, R7 for the mini-DIN. A single shared resistor would put two
75 Ω loads in parallel whenever both cables were plugged in, halving the amplitude.

**One output at a time.** Composite and RGB are alternatives, and the design doesn't
target using both at once. Whichever cable is plugged in sees a correct 75 Ω source,
and the unused branch is just an unloaded stub.

If both cables are plugged in anyway, R7 still gives each output a correctly
terminated 75 Ω source, and the amplitude doesn't halve. The limit then becomes Q1's
drive, which is why **R1 is 220 Ω from v2**, down from the original 330 Ω.

In an ngspice simulation with 2 Vpp at the tap and both outputs terminated, the
follower clips the positive (white) peaks by 33 % at 330 Ω and by 11 % at 220 Ω.
With one output loaded (the supported mode), 220 Ω is clean and symmetric
(+0.439 / −0.447 V at the jack). These are simulated numbers, not bench
measurements, and driving both outputs is still unsupported.

## Hardware

- Designed in KiCad (schematic + PCB source included in this repo)
- Fabricated by PCBWay
- See [BOM.csv](./BOM.csv) for the full parts list

### Sponsored by PCBWay

The most recent fabrication run of this board — the 2026-08-26 package, ordered
**2026-08-27** — was
**sponsored by [PCBWay](https://www.pcbway.com/)**, who covered the manufacturing
of the boards this project is built and tested on. Thank you — having the fab
covered is what let this revision get made, populated and put on the bench rather
than staying a set of gerbers.

Those boards predate [`247334c`](../../commit/247334c), so like every board
fabricated so far they carry the `/raw_5v` trace-ampacity defect described in the
caution at the top of this file — see
[the safety advisory](docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md).

PCBWay have been good to work with on the practical side too: the 2-layer,
1.6 mm FR4 board here is an unremarkable order for them, the gate-generated fab
package uploaded without any back-and-forth over the drill or layer files, and
they will run the four SMD lines (C3, R6, U1, USB-C1) as single-sided SMT while
leaving the through-hole parts to the bench — including sourcing the TPS2553
from LCSC, which DigiKey and Mouser have on a 112-day lead. See
[docs/pcbway-smd-assembly.md](./docs/pcbway-smd-assembly.md) for that workflow.

The project is also published on PCBWay's community site, with the same design
files and documentation as this repository:

**→ [Link to Video on PCBWay Community](https://www.pcbway.com/project/shareproject/Link_to_video_7f1f9279.html)**

The sponsorship covered fabrication only, and carries no editorial influence over
this documentation. The design remains [CERN-OHL-S v2](./LICENSE.txt) and
OSHWA-certified, free for anyone to study, modify, build and have made wherever
they like. The PCBWay-hosted copy is published under GPL v3 because their form
does not offer CERN-OHL-S — see [License](#license).

## Build Notes / Known Issues (v1)

- **Q1 emitter node shorted to +5 V (breaks video).** The rail clamps Q1's emitter,
  so C2 couples +5 V, not video, into R5/J3.

  The exact wiring differs between revisions. In the pre-v1.1 source in this
  repository, R1 had *both* ends on `/5V`. On the boards fabricated from the
  2026-07-16 gerbers, R1 pad 1 is on `/5V` and pad 2 is on a separate net with only C1.

  Root cause: an edit on 2026-07-04 deleted an R2 (110 Ω) from the schematic, and
  KiCad merged the two leftover collinear wire stubs into a single wire that tied the
  emitter node to `/5V`. The source is fixed as of v1.1. To rework an existing board,
  see [Q1 emitter rework (v1 boards)](#q1-emitter-rework-v1-boards).
- The mounting holes of the RCA jack are slightly asymmetric. This is cosmetic and
  doesn't affect the fit in the NES shell.
- The v1 silkscreen has no component values and no E/C/B markers for Q1.
  **v2 adds the values.** R1/R3/R4/R5/R7 share one footprint across four values, and
  on v1 that led to three wrong-resistor errors in R1: a 5.1 kΩ and an 820 Ω both
  went in before the correct value. Q1 pin markers are still missing.
- **VBUS input trace is undersized for its own fuse (all fabbed boards).** `/raw_5v`
  reaches F1 through 9.06 mm of 0.2 mm trace. At 2.22 A the trace heats past the glass
  transition of FR4, and at 2.83 A it chars. F1 (RHEF200) is guaranteed to hold up to
  2.0 A but only guaranteed to trip above 3.8 A, so in the 2.2–3.8 A window the trace
  can burn out before the fuse ever opens.

  Root cause: a gap in the netclass patterns. `/5V*`, `GND*` and `VBUS` were assigned
  the `Power` class (0.8 mm), but none of them matched the actual net name `/raw_5v`,
  so it fell through to `Default` (0.2 mm). DRC can't catch this, because it enforces
  the board's `min_track_width` (0.2 mm), not the netclass width. Commit `247334c`
  fixes the pattern and reroutes the trace at 0.8 mm.
  **Existing boards need a rework.** See
  [the safety advisory](docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md).

- **D1 does not protect U1.** The installed TVS is a Littelfuse 1.5KE6.8A: stand-off
  5.80 V, breakdown 6.45–7.14 V at 10 mA, clamping 10.5 V at 144.8 A. The TPS2553's
  absolute maximum on IN and OUT is 7 V, which is where the TVS is only just starting
  to conduct. In a real surge, it lets the rail reach 10.5 V. D1 protects the console
  downstream, but not U1.

  Moving D1 wouldn't help, since both U1 pins share the same 7 V rating, and no
  avalanche TVS both clamps below 7 V and stands off USB-C's 5.5 V worst case. The
  real fix is a switch with a built-in overvoltage cutoff. That's a v3 change; v2
  ships with this gap.
- D1's symbol (`Diode:1.5KExxA`) labels its pins A1/A2 and shows no cathode, because
  KiCad uses the same pin names for the unidirectional and bidirectional variants of
  this part. Only the footprint's silkscreen band shows the polarity. The band is at
  the pad-1 (+5 V) end, which is correct, so go by the band when you assemble by hand.

### Q1 emitter rework (v1 boards)

This applies to boards fabricated from the 2026-07-16 gerbers, whose IPC netlist
reads:

- `/5V = J4.3, F1.1, R1.1, Q1.1, C2.1, D1.1`
- `Net-(C1-Pad1) = R1.2, C1.1`

That revision has two defects:

- The rail clamps Q1's emitter.
- C1 only reaches the rail through R1, so the bulk capacitor isn't decoupling the
  rail.

This procedure fixes both at once.

> [!CAUTION]
> **Do not power the board with Q1 installed until the cut is done.** This short kills transistors.
> With the emitter clamped at +5 V and the base at the NES video level, the B-E
> junction is forward-biased by 3–4 V. Q1 saturates into a collector tied straight to
> ground, and nothing limits the current: Q1 is a 150 mA part, and F1 won't trip until
> 3.8 A. Every power-up in that state can take out another transistor, which is
> probably how the first one died.

**Confirm the diagnosis before you cut.**

1. Disconnect the power.
2. Make sure the capacitors are discharged.
3. Put one meter lead on +5 V, at J4 pin 3 or at D1's K-marked lead.
4. Take the two measurements in the table. A defective board and a correct board
   give opposite results:

| Measurement | Defective board | Correctly wired |
|---|---|---|
| Q1 emitter → +5 V | **~0 Ω** | ~330 Ω (R1) |
| C1 **+** terminal → +5 V | **~330 Ω** (stranded behind R1) | ~0 Ω |

After the rework, the two readings swap.

To identify Q1's legs without relying on the TO-92 orientation, measure each leg:

- 0 Ω to GND: collector
- Continuity to J4 pin 1: base
- The remaining leg: emitter

Two tests look useful but aren't:

- **Emitter → J3 tip.** C2 blocks DC, so this reads open on every board.
- **C1 + → Q1 emitter.** This reads ~330 Ω on good and bad boards alike, because R1
  sits between these two points in both wirings.

With power on, the quickest check is the DC voltage at Q1's emitter: about 1.5–3 V
on a correct board, exactly the rail voltage on a shorted one.

**R1's left pad is a star point.** Three connections meet there:

- F1 (the source)
- The D1 + J4.3 branch (the load)
- Q1's emitter

The two incoming rail traces are *collinear*, so one cut severs both. That's why the
rework needs **two** jumpers, not one.

1. **Cut** the 0.8 mm trace that runs from R1's left pad toward the **upper
   left**, about 5–8 mm from the pad.

   Leave the trace coming in from the upper right alone. That one is Q1's emitter.

   Cut below the level of D1's cathode. Above that point, only one of the two
   overlapping traces is present, and you need to cut both.

2. **Install two jumpers.** Pull R1 first. Its right pad is much easier to solder
   when it's empty.

   The cut leaves three islands. Join all three into one rail:

   | Island | Pads |
   |---|---|
   | A | C1's **+** pad, R1's **right** pad |
   | B | F1 pad 1 (left pad, trace toward D1 — not the USB-C side) |
   | C | D1's cathode (K), J4 pin 3 |

   Any two wires that join all three islands will work. For example, with one wire
   per pad:
   - **C1+ → F1 pad 1** (~14 mm)
   - **R1's right pad → D1 cathode** (~25 mm)

3. **Install R1 = 300–330 Ω.** Double-check the part before it goes in. R1, R3, R4,
   R5 (and R7 on v2) share the same `R_Axial_DIN0207` footprint across four different
   values, and the v1 silkscreen shows none of them.

   At least one board ended up with a 5.1 kΩ from the R3/R4 pile in the R1 position.
   That gives ~0.6 mA of standing current instead of ~9 mA. The board looks plausible
   but produces no usable video.

4. **Check that R5 (75 Ω) is fitted.** Measure across its pads; you should see
   ~75 Ω. R5 has no parallel path in the circuit (C2 blocks DC on one side and the
   jack is open on the other), so this doubles as a sanity check of the meter.

5. **Install the transistor last.** If you power up before the cut is complete, Q1
   saturates and the rail dumps straight into ground with nothing limiting the
   current. See the caution above.

Before you power up, check with a meter:

- R1 left pad to D1 cathode: **open**
- R1 left pad to F1 pad 1: **~330 Ω**, through R1
- R1 left pad to Q1's emitter and to C2 pin 1: continuity
- D1 cathode to J4 pin 3 *and* to F1 pad 1: **~0 Ω**

With power on, Q1's emitter should sit at about 1.5–3 V. If it reads 5 V, the cut
didn't separate the traces.

## Video input biasing

Q1's base is DC-coupled directly to the NES video line, with no bias network. That's
deliberate, and it took a long bench session to work out why it works.

**The NES mainboard supplies a 1 kΩ pulldown on its video output pin.** It measures
0.999 kΩ in circuit, the same with the meter leads either way round, so it's a real
resistor and not a semiconductor junction. Q1's base sources about 46 µA, which that
1 kΩ soaks up at about 46 mV. The base can't float up, and Q1 can't cut off.

That's also why Nintendo's original modulator has no base pulldown. It's consistent
with the load Nintendo put on that pin, too: a 330 Ω series resistor into a
5.6 kΩ / 330 Ω divider, roughly 500 Ω in total. The NES is designed to drive a few
hundred ohms.

**So this board has no base pulldown and no input coupling capacitor.** If you
adapt this design for something other than an NES-001, measure that pin to ground
first, and if it reads open, add a pulldown (~47 kΩ).

**R2 (330 Ω) is not a bias resistor.** It sits in series between J4 pin 1 and Q1's
base, in the same position as Nintendo's own 330 Ω. Against Q1's ~21 kΩ base input
impedance it has almost no effect on the signal. Its job is to limit fault current
into the base-emitter junction, which is only rated for 5 V in reverse.

## Design checks

Beyond ERC and DRC, this project runs three more checks. The first two catch faults
this board actually shipped with. The third closes the gap between checking a board
and fabricating it.

### `tools/check_nets.py`

```
python3 tools/check_nets.py
```

The script exports the schematic netlist, reads the pad nets from the PCB, checks
that the two agree, and then asserts a set of invariants.

The most important invariant is that **Q1's emitter is not on any power net**.
That was the v1 fault: the emitter follower's output was tied to +5 V along with
J4.3, D1.1 and F1.1, so Q1 saturated into a grounded collector with nothing limiting
the current. Every power-up killed a transistor.

**ERC and DRC both passed on that board with no errors.** Neither can tell that a
net is *wrong*, only that it's internally consistent. That's why this script exists.

Run it before you generate a fab package. Gerbers carry no net information, so once
they're generated the mistake is invisible.

### `nes_power_video.kicad_dru`

Custom DRC rules for the geometric half of the problem:

- More clearance between the supply rails and the emitter and base nodes
- More clearance between the two USB-C configuration channels

These catch the same class of mistake when it shows up as adjacent copper in the
layout. They can't catch a wrong net assignment, because DRC knows nothing about
design intent. That's what the script above is for.

### `prefab-gate`

```
export KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
prefab_gate package nes_power_video.kicad_pcb --out pcbway_production
```

**prefab-gate now lives in its own repository:
[danielboston38/prefab-gate](https://github.com/danielboston38/prefab-gate).**
It's a general-purpose KiCad tool with its own MIT license and users beyond this
project, so it moved out of this hardware repo.

You can install it any of these ways:

- As a KiCad plugin, through the Plugin and Content Manager
- As a Claude Code plugin: `/plugin marketplace add danielboston38/prefab-gate`
- By cloning the repository and running `scripts/prefab_gate.py` directly

The gate refuses to write a fab package unless the board passes both DRC with zone
refill *and* schematic parity. It hashes the board and the schematic after the
refill and checks them again right before publishing, so the package always
describes the board the gate actually verified. `manifest.json` records the result
along with every finding, including the cosmetic findings the gate waived.

To get the verdict without writing files, run `check` instead of `package`.

`pcbway_production/` isn't tracked in git, since the packages can be regenerated
from the board. The first two fab packages are still in the git history, at the
2026-07-07 and 2026-07-16 commits. The 2026-08-26 package for the sponsored run was
never committed, but its copper and outline gerbers have been checked byte-identical
to the board at [`f672f8d`](../../commit/f672f8d), and all 49 drill hits match.

When you order, generate a fresh fab package rather than reusing an old directory,
so the gate re-verifies the exact board you're paying for.

## Assembly

<!-- Add step-by-step or reference photos here once you've got a documented build process -->

See BOM.csv for the exact part values and footprints. Every component's sourcing
data lives in two places, and the two agree:

- The `Manufacturer`, `MPN`, `LCSC`, `Supplier Link` and `Datasheet` fields on the
  schematic symbol
- The matching columns in `BOM.csv`

Generic passives deliberately have no manufacturer part number. They carry a `Spec`
field instead (tolerance, rating, package), and any part that meets it will do. To
pull the fields straight from the schematic:

```
kicad-cli sch export bom --group-by '' \
    --fields 'Reference,Value,Manufacturer,MPN,LCSC,Datasheet,Supplier Link,Spec' \
    -o bom.csv nes_power_video.kicad_sch
```

The `Mount` column in `BOM.csv` marks each line `SMD` or `THT`, taken from the
footprint attributes on the board.

### Having PCBWay fit the SMD parts

Only four parts need reflow — C3, R6, U1 and USB-C1 — and all four are on the top
side. PCBWay can do those as single-sided SMT while you hand-solder the 15
through-hole parts. That way you skip the two hardest joints on the board (the
SOT-23-6 and the Type-C receptacle) without paying for full assembly.

`tools/pcbway_assembly.py` builds the SMD-only upload pair from a gate-generated fab
package. It takes the SMD/THT split from the board, not from a hand-maintained list:

```
python3 tools/pcbway_assembly.py nes_power_video.kicad_pcb pcbway_production/<timestamp>
```

Two things to know before you order:

- **U1 is out of stock at both DigiKey and Mouser** (112-day factory lead). LCSC has
  44,000, so tell PCBWay to source U1 from LCSC.
- **USB-C1 is Hybrid, not SMD.** Its four shell stakes are through-hole pads on the
  paste layer, and they must reflow pin-in-paste with everything else. Don't leave
  them dry.

As of v2, all four SMD lines (C3, R6, U1, USB-C1) are LCSC parts, so PCBWay can source
the whole assembly BOM from LCSC. For the full workflow, including what to upload and
what not to, see **[docs/pcbway-smd-assembly.md](./docs/pcbway-smd-assembly.md)**.

Key notes:
- D1 (zener/TVS): put the cathode (banded end) toward the VBUS/+5V side. From v2, the
  silkscreen shows the actual part, `1.5KE6.8A`. Earlier boards show KiCad's generic
  symbol name, `1.5KExxA`, which isn't an orderable part.
- Q1 (**2SA733**, PNP): with the flat side facing you and the leads down, the pins are
  Emitter-Collector-Base, left to right.
  This replaces the 2SA1015/KSA1015, **both of which are end of life** (checked 2026-08-29): MCC's
  `2SA1015-GR-AP` is stocked at Mouser but flagged End of Life, and every onsemi `KSA1015` reads
  Obsolete on DigiKey, available only through Rochester Electronics' last-time-buy channel. The
  2SA733 is in current production, shares the E-C-B pin order exactly so it drops straight in, and is
  a better part for a video buffer: f_T 190 MHz typ against the 2SA1015's 80 MHz, C_ob 2–3 pF, P_C
  750 mW, with the same V_CEO −50 V / I_C −150 mA / V_EBO −5 V — so R2 still guards the base-emitter
  junction exactly as before. Buy the UTC `2SA733L-P-T92-B` from LCSC (**C5310429**, ~$0.035).
  Rank P is hFE 200–400, which matches the ~46 µA base current measured on the bench, so the bias
  point does not move. DigiKey's Renesas 2SA733 is Rochester stock at $1.90 — same trap, different part.
- **Why not a 2N3906 or BC557?** Not for the reason you might assume. Electrically the 2N3906 is
  perfectly happy here — V_CEO −40 V, I_C −200 mA, f_T 250 MHz, V_EBO −5 V, hFE 100–300 at 10 mA,
  every figure with huge margin against a 5 V rail at ~9.3 mA. The problem is the middle pin. Per
  UTC's ordering tables, the 2N3906 is **E-B-C** and the 2SA733 is **E-C-B**: the 3906 puts *base* in
  the centre where this board wants *collector*. Turning the part around gives C-B-E — base is still
  in the middle, so no orientation fixes it and you would have to cross two leads. On a v3 layout the
  pin order is free and the 2N3906 becomes a fine choice; on this board it is not. Pin order is a
  manufacturer's choice rather than a standard, so check the datasheet of the exact brand you buy.
- R1 (220 Ω): Q1's emitter load. One end goes to +5 V and the other to the Q1 emitter /
  C2 node; both ends on +5 V is wrong. v2 dropped R1 from 300 Ω to 220 Ω for more
  drive current. Assuming ~1.3 V at the base, 300–330 Ω gives only ~6.2 mA at peak
  white, and the 150 Ω load needs ~6.7 mA. If you measure something other than ~1.3 V
  DC at J4 pin 1, recalculate R1.
- R2 (330 Ω): series resistor in the video input line, between J4 pin 1 and Q1's base. See [Video input biasing](#video-input-biasing).
- **Trim all through-hole leads flush.** The board sits in the RF module slot with
  shielding directly underneath, and long leads on the bottom side will short to the
  can. On the prototype, this caused an intermittent supply trip that only happened
  when the board moved.
- C2 (470 µF): not 100 µF. Into the 150 Ω load, 100 µF gives τ=15 ms against a
  16.7 ms field period, so the picture tilts from top to bottom. 470 µF gives τ=70 ms.
- F1 (polyfuse): it's fine for it to sit slightly off the PCB. That's normal for
  radial-lead parts, not a defect.

  **KiCad has no footprint for the Littelfuse RHEF series.** F1 borrows
  `Fuse:Fuse_Bourns_MF-RG300`: pads 5.24 mm center-to-center, with 1.01 mm drills. The
  RHEF200's 0.51 mm leads at 5.05 ±0.75 mm spacing fit easily. But the Bourns part is
  rated 3.0 A/5.1 A and the silkscreen outline shows *its* body, so treat the outline
  as a rough guide, not a clearance boundary. A proper RHEF200 footprint moves pad 2 by
  ~1.2 mm and needs a reroute, so that's a v3 change rather than a patch.

  **F1 stays a Littelfuse RHEF200 and is deliberately not an LCSC part.** It's
  through-hole, so it isn't on the SMD assembly BOM that PCBWay sources anyway, and
  the LCSC alternatives are worse where it matters:
  - Jinrui JK30-200 (C369104): I_max drops to 40 A, and the part is 15.2 mm tall.
  - JKSEMI JK16-200T (C5183874): LCSC lists it as through-hole, but its datasheet is
    titled *"JK16 Series Surface Mount PTC Devices"* and shows no land pattern, so its
    package is unconfirmed.

  If you need to reorder F1, get it from DigiKey or Mouser along with the Switchcraft
  RCA jacks, which LCSC can't supply either.
- USB-C1: GCT USB4125-GF-A-0190, SMD receptacle. Power-only, 6P, no data lines,
  48 V / 3 A, 20,000 mating cycles.

  **As of v2, this part replaces the GCT USB4970-00-A**, which LCSC doesn't stock (a
  search for that MPN turns up nothing). The USB4125 is a different GCT line that LCSC
  *does* stock (C5246813). The board already used its land pattern, so this is a
  sourcing change only, not a layout change.

  The footprint is `Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x-0190`. Its copper,
  silk, fab, courtyard and drills are byte-identical to the plain `USB4125-xx-x`
  variant the board used before; only the name, the descr field and the 3D model
  differ.

  Use the **-0190** variant. Its 1.90 mm shell stake pokes 0.30 mm through this 1.6 mm
  board and gives a fillet on the bottom side. The 1.00 mm stake (plain
  `USB4125-GF-A`, C3151650) doesn't make it through. LCSC stocks fewer of these than
  of the generic Chinese 6P parts, so order spares.
- U1 (TPS2553, SOT-23-6): pin 1 (marked by the dot on the package) is IN. The pins run
  IN, GND, EN down one side and OUT, ILIM, FAULT up the other. Order the plain
  TPS2553DBVR. The `-1` suffix is the latch-off variant, which needs a power cycle
  after every trip; the plain part retries automatically.
- C3 (100 nF, 0805): TI wants C3 as close to U1 pin 1 as the layout allows. It sits
  immediately to the left of U1.
- R6 (22k, 0805): sets the current limit. Check the table in
  [Power path](#power-path) before you change it.

## Certification

This project is **OSHWA-certified open source hardware**, UID **[US002842](https://certification.oshwa.org/us002842.html)**.

The certification confirms that the design files, schematics, PCB layout, bill of
materials and documentation in this repository:

- Are published under an OSI/FSF-approved open license
- Are complete enough for someone else to study, modify, manufacture and distribute
  the hardware

See the [OSHWA certification directory entry](https://certification.oshwa.org/us002842.html)
for the registered details.

The certification mark above,
[`certification-mark-US002842-stacked.svg`](./certification-mark-US002842-stacked.svg),
was issued by OSHWA for this UID. It applies only to this design and doesn't transfer
to derivatives; each derivative needs its own certification.

## License

Licensed under [CERN-OHL-S v2](./LICENSE.txt) (strongly reciprocal open hardware license). See [LICENSE](./LICENSE.txt).

**The PCBWay community copy is GPL v3.** PCBWay's project form doesn't offer
CERN-OHL-S, so the copy
[on their community site](https://www.pcbway.com/project/shareproject/Link_to_video_7f1f9279.html)
is licensed GPL v3. Same design, same files, two license grants: use whichever one
you received the design under. Both licenses are copyleft and both are on the
approved list, so the certification holds either way.

The practical difference is the physical board. CERN-OHL-S covers the *making* of
hardware: if someone builds and sells a board, the complete source has to go with
it. GPL v3's copyleft kicks in when someone distributes the design files, so it
doesn't reach a board fabricated from them. Both licenses keep the design files
reciprocal; only CERN-OHL-S extends that to manufactured hardware.

## Photos

<!-- Add build photos here -->

## Acknowledgments

- **[PCBWay](https://www.pcbway.com/)** — for sponsoring the fabrication of the
  latest revision of this board, and for hosting the project on their community
  site: [Link to Video](https://www.pcbway.com/project/shareproject/Link_to_video_7f1f9279.html).
- **Tim Worthington** — for the [NESRGB](https://etim.net.au/nesrgb/), whose
  8-pin mini-DIN pinout J5 on this board feeds.
- **OSHWA** — for the open hardware certification programme
  ([US002842](https://certification.oshwa.org/us002842.html)).

<!-- Optional: credit anyone who helped with debugging, Discord community, etc. -->
