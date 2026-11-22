# Power path: simulation harness

Reproduces every figure in
[`docs/SAFETY-ADVISORY-2026-11-hotplug-overshoot.md`](../../docs/SAFETY-ADVISORY-2026-11-hotplug-overshoot.md).

It models the path USB-C → F1 → U1 (TPS2553) → `/5V` → NES. The NES has its 7805 removed,
so the board feeds the NES's 5 V rail directly.

## Run it

```bash
brew install ngspice          # or: apt install ngspice
python3 run_all.py            # all four sections, about 4 minutes
python3 run_all.py hotplug    # one section: hotplug, fix, startup or steady
```

Python 3.9+, standard library only. ngspice must be on `PATH`.
Every deck is kept in `./power_sim_decks/` (change it with `--decks DIR`). That directory is gitignored.

## What it reports

1. **Hot plug, board as fabbed.** A live cable touches the board. Cable inductance rings against C3 (100 nF),
   and U1's input goes to 9–10 V. Its absolute maximum is 7 V.
2. **Hot plug with C5.** The same event with 100 µF on `/fused_5v`. Three ESR values, two cables.
3. **Startup with C5.** A USB-C source ramps VBUS, and the NES bulk capacitance is swept from 47 µF to 4700 µF.
   It checks for thermal-shutdown cycling. The source peak current is above U1's limit because C5 charges before U1.
4. **Steady state at 0.9 A.** The voltage that reaches the NES, for different supply voltages and cable resistances.

## The model

U1 has no vendor ngspice model, so it is **behavioural**, built from TI's datasheet (SLVS841F):

| Feature | Value used | Source |
|---|---|---|
| Switch resistance | 95 mΩ cool, 135 mΩ hot | rDS(on), DBV package |
| Soft start | output follows a 4 V/ms gate ramp | tr, 1.1–1.5 ms |
| Current limit, RILIM = 22 kΩ | 1.091 / 1.169 / 1.257 A | equation 1, min / nom / max |
| Thermal | 182.6 °C/W, off at 135 °C, on at 125 °C | RθJA and thermal sense |
| UVLO | 2.45 V | UVLO rising |

## Assumptions worth challenging

- **Cable:** 0.5–2 µH and 30–400 mΩ round trip. These values are typical, not measured.
- **Contact rise time:** 0.2 µs. Section 1 shows the overshoot is mostly gone above 2 µs.
- **F1 resistance:** 80 mΩ. The RHEF200 datasheet gives a range. Higher resistance damps more.
- **NES load:** a fixed resistor that draws 0.9 A at 5 V, which matches the bench reading.
  The NES's own bulk capacitance is not known, so it is swept.
- **Copper and harness:** 90 mΩ from U1 to the NES, mostly the 0.2 mm `/5V` run.

The hot-plug result does not depend much on these values: every combination in section 1 exceeds 7 V.
The steady-state voltage at the NES depends strongly on the cable, so measure it on the bench.
