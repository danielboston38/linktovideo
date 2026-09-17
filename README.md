# Link to Video

A replacement for the RF modulator in the original Nintendo Entertainment System (NES-001). Drops into the stock RF module slot inside the shell and provides composite video and USB-C power in place of a part that fails by design.

<a href="https://certification.oshwa.org/us002842.html">
  <img src="./certification-mark-US002842-stacked.svg" alt="OSHWA Certified Open Source Hardware UID US002842" width="140" align="right">
</a>

> [!CAUTION]
> **Safety advisory for boards built before 2026-09-08.**
> On every board fabricated so far, the USB-C VBUS input goes to F1 through 9.06 mm of
> 0.2 mm-wide trace. This trace becomes damaged at a current well below the guaranteed
> trip current of F1. If a fault occurs downstream, **F1 cannot protect the input
> trace on the board**.
> The defect has no effect on normal operation (48 °C, 17 mV drop). It is a
> fault-tolerance defect, not a wear-out defect. A board that works now will continue to work.
> Commit [`247334c`](../../commit/247334c) corrects the layout. The rework of an affected
> board takes approximately 15 minutes.
>
> **→ Read the full advisory: [docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md](docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md)**

> **Renamed.** The first revision of this project had the name **Kirby's New Dream**.
> From v2, the name is **Link to Video**. Items with the old name are the same project:
> the v1 board silkscreen, the 2026-07-16 PCBWay fab package, and older commits.
> The GitHub repository also has the new name. The old `kirbysnewdream` URL still
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
- All resistor and capacitor values printed on the silkscreen. On the v1 board, four identical axial footprints with no labels held four different values. This caused three wrong-resistor build errors.
- 2-layer PCB, designed in KiCad

## Power path

```
USB-C  ──  F1 polyfuse  ──  U1 TPS2553 eFuse  ──  +5V rail  ──  J4.3 → NES
  VBUS      2.0A hold        ~1.18A limit          C1 100µF
            3.8A trip        soft-start            D1 TVS
            (backup)         thermal shutdown
```

F1 alone trips at 3.8 A. The console draws approximately 0.5–0.7 A, so F1 alone
does not protect it. U1 gives the real protection. F1 is a backup if the eFuse
fails as a short circuit.

R6 on U1's ILIM pin sets the current limit. The relationship is
**inverse**: a larger resistor gives a *lower* limit.

| R6 | Limit (typ) |
|---|---|
| 15 kΩ | 1700 mA |
| 20 kΩ | 1295 mA |
| **22 kΩ (fitted)** | **~1180 mA** |
| 49.9 kΩ | 520 mA |
| 210 kΩ | 130 mA |

Approximately, I_OS(A) ≈ 25.9 / R6(kΩ). This equation is valid in the range that
TI recommends, 15 kΩ–232 kΩ.

U1's EN (pin 3) is active-high. It connects to U1's own input, so the switch is
always on. FAULT (pin 4) is an open-drain output with no connection. A closed NES
shell has no indicator for FAULT to drive. If you want a fault indicator, FAULT can
sink 25 mA directly.

**Useful side effect: a reversed D1.** D1 is a unidirectional TVS. If you install
D1 backwards, it puts a forward-biased diode across the 5 V rail. Before the board
had U1, this error made almost a short circuit. The only protection was the
polyfuse, which needs seconds to react. Now the eFuse limits the current to
~1.18 A and then does a thermal shutdown, so the error limits itself and does
not destroy parts.

## Test points (v2)

The board has four through-hole test points (2.0 mm pad, 1.0 mm drill) for bring-up.
Each test point accepts a 0.64 mm square header pin. You can solder pins into them
and attach scope grabbers.

The silkscreen shows only the signal name: `VIDEO`, `GND`, `+5V`, `AUDIO`, so
you can read the board without this table. The reference designator is on F.Fab,
for the fab drawings.

The first pass of v2 had this backwards. The signal names were on F.Fab, which does
not go onto the physical board. As a result, the silkscreen showed only `TP1`–`TP4`.

| TP  | Net          | Location (mm) | Notes |
|-----|--------------|---------------|-------|
| TP1 | `/VIDEO_OUT` | 62.0, 60.0    | Jack-side video: after C2 and the 75 Ω series resistor R5. This is the signal that the TV gets. A high-impedance probe reads approximately double the terminated amplitude. |
| TP2 | `GND`        | 58.5, 60.0    | Connects directly to the B.Cu ground pour. |
| TP3 | `/5V`        | 52.0, 43.1    | On the protected 5 V trunk, downstream of F1 and the TPS2553. |
| TP4 | `/AUDIO_OUT` | 65.9, 28.35   | Audio pass-through between J4 pin 2 and J2. |

The whole back layer is a ground pour, so TP2's position is for
convenience only. You can clip a ground lead to any B.Cu feature.

To probe the buffer and not its output, probe Q1's emitter leg directly.
`Net-(Q1-E)` has no test point.

## RGB output (v2)

This board can feed the RGB connector of the [NESRGB](https://etim.net.au/nesrgb/)
board. That connector uses the 8-pin mini-DIN standard of the Micomsoft XRGB-mini
Framemeister.

The connector is **not** on this board. The NESRGB kit supplies it as a panel-mount
jack. The jack attaches with epoxy in a 12 mm hole in the shell. This board only
feeds the jack. R/G/B go directly from the NESRGB to the connector. **J5** on this
board supplies the other three pins:

| J5 pin | Net          | mini-DIN pin | |
|--------|--------------|--------------|---|
| 1 | `/RGB_VIDEO` | 3 | Composite video / sync, 75 Ω terminated |
| 2 | `GND`        | 4 | |
| 3 | `/5V`        | 5 | Downstream of the TPS2553, so it is current-limited |

Mini-DIN pins 1 and 2 have no connection. Pins 6, 7 and 8 are Blue, Green and Red
from the NESRGB. The standard does not carry audio. Audio stays on the RCA jack.
Tim Worthington made this choice deliberately, because it keeps video noise out of
the audio.

**Why R7 exists.** The output of the video buffer (`/VIDEO_BUF`, Q1's emitter
through C2) now feeds two outputs. Each output needs its own 75 Ω source
termination: R5 for the RCA jack, R7 for the mini-DIN. One shared resistor puts two
75 Ω loads in parallel when both cables are connected, and cuts the amplitude by half.

**One output at a time.** Composite and RGB are alternatives. The design does not
target the use of both at the same time. The connected cable gets a correct 75 Ω
source. The unused branch is a stub with no load.

If both cables are connected at the same time, R7 still gives each output a
correctly terminated 75 Ω source. The amplitude does not decrease by half. In that
case, Q1's drive is the limit. For this reason, **R1 is 220 Ω from v2**, not
the original 330 Ω.

An ngspice simulation used 2 Vpp at the tap, with both outputs terminated. At
330 Ω, the follower clips the positive (white) peaks by 33 %. At 220 Ω, it clips
them by 11 %. With one output loaded (the supported mode), 220 Ω is clean and
symmetric (+0.439 / −0.447 V at the jack). These results come from simulation, not
from measurement on hardware. Two connected outputs are still not a supported mode.

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

  The wiring is different in each revision. In the pre-v1.1 source in this
  repository, R1 had *both* ends on `/5V`. On the boards fabricated from the
  2026-07-16 gerbers, R1 pad 1 is on `/5V`. R1 pad 2 is on a separate net with only C1.

  Root cause: an edit on 2026-07-04 deleted an R2 (110 Ω) from the schematic. KiCad
  then merged the two remaining collinear wire stubs into one wire. That wire
  connected the emitter node to `/5V`. The source has the fix from v1.1. For the
  rework of an existing board, see
  [Q1 emitter rework (v1 boards)](#q1-emitter-rework-v1-boards).
- The mounting holes of the video/audio RCA jack are slightly asymmetric. This problem
  is cosmetic only. It has no effect on the fit in the NES shell.
- The v1 silkscreen has no component value labels and no pin markers (E/C/B) for Q1.
  **Values are on the silkscreen from v2.** R1/R3/R4/R5/R7 use one footprint with four
  values. On v1, this caused three wrong-resistor errors in R1: a 5.1 kΩ and an 820 Ω
  were both installed before the correct value. The silkscreen does not have Q1 pin
  markers yet.
- **VBUS input trace is undersized for its own fuse (all fabbed boards).** `/raw_5v`
  goes to F1 through 9.06 mm of 0.2 mm trace. At 2.22 A, the trace exceeds the glass
  transition of FR4. At 2.83 A, the trace chars. F1 (RHEF200) is guaranteed not to
  trip below 2.0 A. It is guaranteed to trip only above 3.8 A. In the 2.2–3.8 A
  window, the trace is destroyed and the fuse possibly never operates.

  Root cause: a gap in the netclass patterns. The patterns `/5V*`, `GND*` and `VBUS`
  assigned the `Power` class (0.8 mm). None of these patterns matched the actual net
  name `/raw_5v`, so the net got the `Default` class (0.2 mm). DRC cannot find this
  defect, because DRC enforces the board `min_track_width` (0.2 mm), not the netclass
  width. Commit `247334c` corrects the pattern and changes the route to 0.8 mm.
  **Existing boards need a rework.** See
  [the safety advisory](docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md).

- **D1 does not protect U1.** The installed TVS is a Littelfuse 1.5KE6.8A: stand-off
  5.80 V, breakdown 6.45–7.14 V at 10 mA, clamping 10.5 V at 144.8 A. The absolute
  maximum of the TPS2553 on IN and OUT is 7 V. At the voltage where the eFuse goes out
  of specification, the TVS barely conducts. In a real surge, the TVS lets the rail
  reach 10.5 V. D1 protects the console downstream, but it does not protect U1.

  A different position for D1 does not help, because both U1 pins have the same 7 V
  rating. Also, no avalanche TVS clamps below 7 V and also stands off the 5.5 V worst
  case of USB-C. Correct protection needs a switch with an integrated overvoltage
  cutoff. That fix is for v3. v2 ships with this gap.
- D1's symbol (`Diode:1.5KExxA`) names the two pins A1/A2 and shows no cathode.
  KiCad uses the same pin names for the unidirectional and bidirectional variants of
  this part. Only the silkscreen band of the footprint shows the polarity. The band is
  at the pad-1 (+5 V) end, which is correct. Look at this band when you assemble by hand.

### Q1 emitter rework (v1 boards)

This procedure applies to the boards fabricated from the 2026-07-16 gerbers. The IPC
netlist of these boards reads:

- `/5V = J4.3, F1.1, R1.1, Q1.1, C2.1, D1.1`
- `Net-(C1-Pad1) = R1.2, C1.1`

That revision has two defects:

- The rail clamps Q1's emitter.
- C1 connects to the rail only through R1, so the bulk capacitor does not decouple
  the rail.

This procedure corrects the two defects together.

> [!CAUTION]
> **Do not apply power with Q1 installed before you complete the cut.** The short destroys transistors.
> The rail clamps the emitter at +5 V, and the base is at the video level of the NES.
> The B-E junction has a forward bias of 3–4 V. Q1 saturates, with its collector
> connected directly to ground. Nothing limits the current. Q1 is a 150 mA part, and F1
> does not trip until the current reaches 3.8 A. Each power-up in that condition can
> destroy another transistor. The first transistor probably failed this way.

**Confirm the diagnosis before you cut.**

1. Disconnect the power.
2. Make sure that the capacitors are discharged.
3. Put one meter lead on +5 V, at J4 pin 3 or at D1's K-marked lead.
4. Do the two measurements in the table. The results on a defective board and on a
   correct board are opposites:

| Measurement | Defective board | Correctly wired |
|---|---|---|
| Q1 emitter → +5 V | **~0 Ω** | ~330 Ω (R1) |
| C1 **+** terminal → +5 V | **~330 Ω** (stranded behind R1) | ~0 Ω |

After the rework, the two results change places.

To identify Q1's legs without the TO-92 orientation, measure each leg:

- 0 Ω to GND: collector
- Continuity to J4 pin 1: base
- The remaining leg: emitter

These two tests look useful, but they are not:

- **Emitter → J3 tip.** C2 blocks DC, so this test reads open on every board.
- **C1 + → Q1 emitter.** This test reads ~330 Ω on a good board *and* on a bad board.
  R1 is between these two points in both wirings, so the test cannot identify the
  defect.

With power on, the fastest check is the DC voltage at Q1's emitter. A correct
board shows approximately 1.5–3 V. A shorted board shows exactly the rail voltage.

**R1's left pad is a star point.** Three connections meet there:

- F1 (the source)
- The D1 + J4.3 branch (the load)
- Q1's emitter

The two rail traces that come in are *collinear*, so one cut severs both.
For this reason, the rework needs **two** jumpers, not one.

1. **Cut** the 0.8 mm trace that goes from R1's left pad toward the **upper
   left**. Make the cut approximately 5–8 mm from the pad.

   Do not cut the trace that comes in from the upper right. That trace is Q1's emitter
   and must stay.

   Make the cut below the level of the D1 cathode. Above that point, only one of the
   two overlapping traces is present. You must cut both traces.

2. **Install two jumpers.** Remove R1 before you install the jumpers. The right pad of
   R1 is much easier to solder when it is empty.

   After the cut, there are three islands. Connect all three islands into one rail:

   | Island | Pads |
   |---|---|
   | A | C1's **+** pad, R1's **right** pad |
   | B | F1 pad 1 (left pad, trace toward D1 — not the USB-C side) |
   | C | D1's cathode (K), J4 pin 3 |

   Any two wires that connect all three islands are correct. This example puts one
   wire on each pad:
   - **C1+ → F1 pad 1** (~14 mm)
   - **R1's right pad → D1 cathode** (~25 mm)

3. **Install R1 = 300–330 Ω.** Before you install the part, make sure that it is
   correct. R1, R3, R4, R5 (and R7 on v2) use the same `R_Axial_DIN0207` footprint
   with four different values. The v1 silkscreen shows no values.

   At least one board got a 5.1 kΩ resistor from the R3/R4 pile in the R1 position.
   With that resistor, the standing current is ~0.6 mA, not ~9 mA. The board looks
   plausible but gives no usable video.

4. **Make sure that R5 (75 Ω) is installed.** Measure across R5's pads. The
   result must be ~75 Ω. R5 has no parallel path in the circuit: C2 blocks DC on one
   side, and the jack is open on the other side, so this measurement is also a
   check of the meter.

5. **Install the transistor last.** If you apply power before you complete the cut,
   Q1 saturates. Current flows from the rail directly to ground with no limit. See the
   caution above.

Before you apply power, do these checks with a meter:

- R1 left pad to D1 cathode: **open**
- R1 left pad to F1 pad 1: **~330 Ω**, through R1
- R1 left pad to Q1's emitter and to C2 pin 1: continuity
- D1 cathode to J4 pin 3 *and* to F1 pad 1: **~0 Ω**

With power on, the correct voltage at Q1's emitter is approximately 1.5–3 V. If
the emitter reads 5 V, the cut did not separate the traces.

## Video input biasing

Q1's base is DC-coupled directly to the NES video line. This board has no bias
network. That design is deliberate. A long bench session was necessary to find out
why it works.

**The NES mainboard supplies a 1 kΩ pulldown on its video output pin.** The
in-circuit measurement is 0.999 kΩ, and it is the same with the meter leads in both
directions, so the pulldown is a real resistor, not a semiconductor junction. Q1's
base sources approximately 46 µA. That 1 kΩ resistor absorbs this current with
approximately 46 mV. The base cannot float up, and Q1 cannot cut off.

For the same reason, the original Nintendo modulator also has no base pulldown. It
also matches the load Nintendo presented on that pin: a 330 Ω series resistor into a
5.6 kΩ / 330 Ω divider, approximately 500 Ω in total. The NES is designed to drive a
few hundred ohms.

**So this board has no base pulldown and no input coupling capacitor.** If you
adapt this design for a device other than an NES-001, measure that pin to ground
first. If the pin reads open, add a pulldown (~47 kΩ). This board does not have one.

**R2 (330 Ω) is not a bias resistor.** R2 is in series between J4 pin 1 and Q1's base.
Nintendo puts a 330 Ω resistor in the same position. Q1's base input impedance
is ~21 kΩ, so R2 has almost no effect on the signal. R2 limits the fault
current into the base-emitter junction. The reverse rating of that junction is only
5 V.

## Design checks

This project uses three more checks in addition to ERC and DRC. The first two checks
find faults that this board actually shipped with. The third check covers the gap
between the check of a board and its fabrication.

### `tools/check_nets.py`

```
python3 tools/check_nets.py
```

This script does these steps:

1. It exports the schematic netlist.
2. It reads the pad nets from the PCB.
3. It makes sure that the two agree.
4. It asserts a set of invariants.

The most important invariant is that **Q1's emitter is not on any power net**.
That was the v1 fault. The output of the emitter follower connected to +5 V, with
J4.3, D1.1 and F1.1, so Q1 saturated into a grounded collector, and nothing limited
the current. Each power-up destroyed a transistor.

**ERC and DRC both passed on that board with no errors.** Neither check can see that a
net is *wrong*. They can see only that a net is internally consistent. This script
exists for that reason.

Run this script before you generate a fab package. Gerbers contain no net
information. After you generate them, the mistake is invisible.

### `nes_power_video.kicad_dru`

Custom DRC rules for the geometric half of the problem:

- More clearance between the supply rails and the emitter and base nodes
- More clearance between the two USB-C configuration channels

These rules find the same mistakes when they occur as adjacent copper in the layout.
They cannot find an incorrect net assignment, because DRC has no information about
design intent. The script above does that check.

### `prefab-gate`

```
export KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
prefab_gate package nes_power_video.kicad_pcb --out pcbway_production
```

**prefab-gate is now in its own repository:
[danielboston38/prefab-gate](https://github.com/danielboston38/prefab-gate).**
prefab-gate is a general-purpose KiCad tool. It has its own users and its own MIT
license, so it is no longer part of a hardware project.

To install prefab-gate, use one of these methods:

- Install it as a KiCad plugin through the Plugin and Content Manager.
- Install it as a Claude Code plugin: `/plugin marketplace add danielboston38/prefab-gate`
- Clone the repository and run `scripts/prefab_gate.py` directly.

The gate refuses to write a fab package for a board that did not pass DRC with zone
refill *and* schematic parity. After the refill, the gate calculates a hash of the
board and the schematic. Before it publishes the package, it checks them again,
so the package always describes the board that the gate actually verified.
`manifest.json` records this result with every finding, including the cosmetic
findings that the gate waived.

To get the verdict without writing files, run `check` instead of `package`.

Git does not track `pcbway_production/`, because you can make the packages again from
the board. The first two fab packages are still in the git history, at the 2026-07-07
and 2026-07-16 commits. The 2026-08-26 package for the sponsored run is not in a
commit. But a check found that its copper and outline gerbers are byte-identical to
the board at [`f672f8d`](../../commit/f672f8d), and all 49 drill hits match.

When you order, generate a new fab package. Do not use an old directory. The gate then
verifies again the board that you will pay for.

## Assembly

<!-- Add step-by-step or reference photos here once you've got a documented build process -->

See BOM.csv for the exact part values and footprints. Each component has its sourcing
data in two places, and the two places agree:

- The `Manufacturer`, `MPN`, `LCSC`, `Supplier Link` and `Datasheet` fields on the
  schematic symbol
- The matching columns in `BOM.csv`

Generic passives have no manufacturer part number, by design. They have a `Spec` field
instead (tolerance, rating, package). Any part that meets that specification is
correct. To get the fields directly from the schematic, run this command:

```
kicad-cli sch export bom --group-by '' \
    --fields 'Reference,Value,Manufacturer,MPN,LCSC,Datasheet,Supplier Link,Spec' \
    -o bom.csv nes_power_video.kicad_sch
```

The `Mount` column in `BOM.csv` marks each line `SMD` or `THT`. The value comes from
the attributes of the footprint on the board.

### Having PCBWay fit the SMD parts

Only four parts need reflow: C3, R6, U1 and USB-C1. All four are on the top side,
so PCBWay can do single-sided SMT, and you solder the 15 through-hole parts. Then
you do not solder the two most difficult joints on the board (the SOT-23-6 and the
Type-C receptacle). You also do not pay for full assembly.

`tools/pcbway_assembly.py` makes the SMD-only upload pair from a fab package that the
gate generated. The script gets the SMD/THT split from the board, not from a manual
list:

```
python3 tools/pcbway_assembly.py nes_power_video.kicad_pcb pcbway_production/<timestamp>
```

Before you order, read these two items:

- **U1 is out of stock at both DigiKey and Mouser** (112-day factory lead). LCSC has
  44,000. Tell PCBWay to get U1 from LCSC.
- **USB-C1 is Hybrid, not SMD.** Its four shell stakes are through-hole pads on the
  paste layer. They must reflow pin-in-paste with the other parts. Do not leave them dry.

From v2, all four SMD lines (C3, R6, U1, USB-C1) are LCSC parts, so PCBWay can get
the full assembly BOM from LCSC. For full details, including what to upload and what
not to upload, see **[docs/pcbway-smd-assembly.md](./docs/pcbway-smd-assembly.md)**.

Key notes:
- D1 (zener/TVS): put the cathode (banded end) toward the VBUS/+5V side. From v2, the
  silkscreen shows the installed value, `1.5KE6.8A`. Before v2, the silkscreen showed
  the generic KiCad symbol name `1.5KExxA`. You cannot order a part with that name.
- Q1 (**2SA733**, PNP): hold the part with the flat side toward you and the leads down.
  The pins are then Emitter-Collector-Base, from left to right.
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
- R1 (220 Ω): the emitter load for Q1. One end connects to +5 V, and the other end
  connects to the Q1 emitter / C2 node. Both ends on +5 V is incorrect. v2 changed R1
  from 300 Ω to 220 Ω to increase the drive current. With the assumed base voltage of
  ~1.3 V, 300–330 Ω gives only ~6.2 mA at peak white. The 150 Ω load needs ~6.7 mA. If
  the measured DC at J4 pin 1 is not ~1.3 V, calculate R1 again.
- R2 (330 Ω): series resistor in the video input line, between J4 pin 1 and Q1's base. See [Video input biasing](#video-input-biasing).
- **Trim all through-hole leads flush.** The board is in the RF module slot, with
  shielding immediately below it. Long leads on the bottom side will touch the can and
  cause a short circuit. On the prototype, this short caused an intermittent supply
  trip. The trip occurred only when the board moved.
- C2 (470 µF): do not use 100 µF. Into the 150 Ω load, 100 µF gives τ=15 ms, but the
  field period is 16.7 ms. As a result, the picture tilts from top to bottom. 470 µF
  gives τ=70 ms.
- F1 (polyfuse): a small standoff above the PCB is correct. This standoff is normal for
  radial-lead parts and is not a defect.

  **KiCad has no footprint for the Littelfuse RHEF series.** F1 borrows
  `Fuse:Fuse_Bourns_MF-RG300`: pads 5.24 mm center-to-center, with 1.01 mm drills. The
  RHEF200 has 0.51 mm leads at 5.05 ±0.75 mm spacing, and these leads fit easily. But
  the Bourns device has a rating of 3.0 A/5.1 A, and the silkscreen outline shows *its*
  body. Use the outline only as an approximate guide, not as a clearance boundary. A
  correct RHEF200 footprint moves pad 2 by ~1.2 mm and makes a new route necessary,
  so that change is for v3, not a patch.

  **F1 stays a Littelfuse RHEF200 and is deliberately not an LCSC part.** F1 is
  through-hole, so it is not on the SMD assembly BOM that PCBWay sources. Also, the
  LCSC alternatives are worse in the important specifications:
  - Jinrui JK30-200 (C369104): I_max decreases to 40 A, and the part is 15.2 mm tall.
  - JKSEMI JK16-200T (C5183874): LCSC lists it as through-hole. But its datasheet has
    the title *"JK16 Series Surface Mount PTC Devices"* and shows no land pattern.
    Its package is unconfirmed.

  If you must order F1 again, buy it from DigiKey or Mouser with the Switchcraft RCA
  jacks. LCSC cannot supply those jacks either.
- USB-C1: GCT USB4125-GF-A-0190, SMD receptacle. Power-only, 6P, no data lines,
  48 V / 3 A, 20,000 mating cycles.

  **From v2, this part replaces the GCT USB4970-00-A.** LCSC does not stock the
  USB4970-00-A. A search for that MPN on LCSC always gives no results. The USB4125 is a
  different GCT line number, and LCSC *does* stock it (C5246813). The board layout
  already used its land pattern, so this change affects sourcing only, not the layout.

  The footprint is `Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x-0190`. Its copper,
  silk, fab, courtyard and drills are byte-identical to the plain `USB4125-xx-x`
  variant that the board used before. Only the name, the descr field and the 3D model
  are different.

  Use the **-0190** variant. It has the 1.90 mm shell stake, which extends 0.30 mm
  through this 1.6 mm board and gives a fillet on the bottom side. The 1.00 mm stake
  (plain `USB4125-GF-A`, C3151650) does not go through the board. LCSC has less stock
  of this part than of the generic Chinese 6P parts. Order spares.
- U1 (TPS2553, SOT-23-6): pin 1 is IN. The dot on the package marks pin 1. The pin order
  is IN, GND, EN down one side, and OUT, ILIM, FAULT up the other side. Order the plain
  TPS2553DBVR. The `-1` suffix is the latch-off variant. After each trip, that variant
  needs a power cycle. The plain part tries again automatically.
- C3 (100 nF, 0805): TI requires C3 as near to U1 pin 1 as the layout permits. C3 is
  immediately to the left of U1.
- R6 (22k, 0805): sets the current limit. Before you use a different value, see the
  table in Power path.

## Certification

This project is **OSHWA-certified open source hardware**, UID **[US002842](https://certification.oshwa.org/us002842.html)**.

The certification confirms two facts about the design files, schematics, PCB layout,
bill of materials and documentation in this repository:

- They are published under an OSI/FSF-approved open license.
- They are complete enough for another person to study, modify, manufacture and
  distribute the hardware.

See the [OSHWA certification directory entry](https://certification.oshwa.org/us002842.html)
for the registered details.

The certification mark above is
[`certification-mark-US002842-stacked.svg`](./certification-mark-US002842-stacked.svg).
OSHWA issued it for this UID. The mark applies only to this design. You cannot
transfer it to derivative designs. Each derivative needs its own certification.

## License

Licensed under [CERN-OHL-S v2](./LICENSE.txt) (strongly reciprocal open hardware license). See [LICENSE](./LICENSE.txt).

**The PCBWay community copy is GPL v3.** The project form on PCBWay does not offer
CERN-OHL-S, so the copy
[on their community site](https://www.pcbway.com/project/shareproject/Link_to_video_7f1f9279.html)
has a GPL v3 license. The design and the files are the same, with two license grants.
Use the grant under which you got the design. Both licenses are copyleft, and both are
on the approved list, so the certification holds with either license.

The practical difference is the physical board. CERN-OHL-S applies to the *making* of
hardware. If a person builds and sells a board, CERN-OHL-S requires the complete source
to go with that board. The copyleft of GPL v3 starts when a person distributes the
design files, so it does not apply to a board fabricated from those files. Both
licenses keep reciprocity for the design files. Only CERN-OHL-S gives reciprocity for
manufactured hardware.

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
