# VBUS trace ampacity — simulation harness

Reproduces every simulation figure quoted in
[`docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md`](../../docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md).

Published so the advisory's claims can be checked independently rather than taken on
trust. If you are reviewing this — including with another AI — the useful thing to
attack is the **model**, not the arithmetic; see *Assumptions worth challenging* below.

## Run it

```bash
brew install ngspice          # or: apt install ngspice
python3 run_all.py
```

Python 3.10+, standard library only. Runtime is about two minutes; ngspice must be on
`PATH`. Output is five sections matching the advisory.

Every ngspice deck is kept, under `./vbus_sim_decks/` (override with `--decks DIR`).
There are ~394 of them, about 7 MB. They are named so the deck behind any published
figure can be found directly — `012_steady_asfabbed_2.000A.cir` is the 105 °C headline,
and the `damage_asfabbed_130C_*.cir` series shows the search converging on 2.22 A. The
directory is gitignored; delete it with `rm -rf vbus_sim_decks`.

## What's here

| File | Purpose |
|---|---|
| `thermal_model.py` | The electrothermal model and its IPC-2221 calibration |
| `extract_geometry.py` | Pulls trace geometry by connectivity from `.kicad_pcb` **and** from Gerbers |
| `run_all.py` | Runs every scenario and prints the report |

## The model

The trace is discretised along its length into 0.25 mm slices. Each slice has:

- **Electrical** — a behavioural resistor `R(T) = ρ·dx/(w·t) · (1 + α(T−20))`
- **Thermal** — copper node → *spreading resistance* → near-FR4 node → *bulk* → ambient
- **Lateral** — copper-to-copper thermal conduction to its neighbouring slices

The lateral term is not optional. It is what makes a short neck flanked by wide copper
survivable, and it is the entire mechanism the fix relies on. A lumped single-node model
cannot tell the pre-fix trace (one long uniform narrow run) apart from the post-fix trace
(a short neck beside wide copper) and would wrongly condemn both.

Vertical thermal resistance is calibrated so a long uniform trace reproduces IPC-2221
external-layer ampacity at its 20 K point.

## Validation

Three independent checks, all run by `run_all.py`:

1. **Against IPC-2221** — a long uniform 0.2 mm trace reproduces the standard's
   allowable current within ±8 % from 0.5–2 A, exact at the calibration point.
2. **Against Onderdonk** — the adiabatic fusing calculation gives 9.22 A for a 48 ms
   exposure; the SPICE model melts the trace in 48 ms at 10 A. ~8 % agreement from
   completely different physics.
3. **Sensitivity sweep** — thermal resistance scaled down to credit the B.Cu ground
   pour, to confirm the conclusion is not an artefact of the calibration.

## Assumptions worth challenging

Listed because they are where the analysis is weakest, not to pre-empt criticism.

- **Calibration takes no credit for the B.Cu ground pour** 1.51 mm below the trace.
  IPC-2221's external-layer curve assumes no adjacent plane, so absolute temperatures
  are pessimistic. The sensitivity sweep scales thermal resistance to 40 % of the
  calibrated value; the conclusion survives, but a reviewer could reasonably argue the
  real figure sits somewhere in that range.
- **Above ~300 °C the model is qualitative only.** FR4 decomposes, copper oxidises, and
  the thermal parameters stop being valid. Treat runaway figures as "destructive", not
  as temperatures.
- **Past the runaway knee the network has an unphysical negative-temperature root.**
  Solving `T = I²·R20·(1+αT)·Rth` gives a negative `T` once `I²·R20·α·Rth > 1`. ngspice
  returns it without complaint and it reads as *cold*. `peak()` treats any negative rise
  as runaway. A reviewer re-implementing this should reproduce that guard or they will
  get thresholds that are silently far too high.
- **1 oz copper is taken as 35 µm.** Real finished outer-layer copper after plating
  varies; thinner copper makes the result worse, not better.
- **Ambient is 25 °C.** Inside a closed NES shell it is nearer 45 °C, which lowers every
  threshold by roughly 9 %.
- **Participating FR4 volume** in the near-node heat capacity is estimated from thermal
  diffusion length, not measured. It affects transient timing, not steady-state
  temperature or any threshold.
- **The carbon-tracking secondary effect** mentioned in the advisory is reasoned from
  clearance geometry and is *not* simulated. It is the least certain claim made.

## Geometry provenance

Geometry is obtained by **walking copper connectivity**, not by measuring a bounding box.
This matters: a bounding-box measurement of the same corridor reports only 1.52 mm of
0.2 mm copper, because the route leaves the box. The connectivity walk finds the true
9.06 mm run. An early draft of this analysis made exactly that error.

The advisory quotes the **Gerber** figures, because those describe the boards as actually
manufactured. Both fabbed packages live in git history:

```
git cat-file -p 3cca8216c29fc129d4af6e3149339d9ec40d9122 > jul07.zip   # 2026-07-07
git cat-file -p 46ed2ff15eafcf9bbca26537807e6c839aaac4bc > jul16.zip   # 2026-07-16
```

Both carry an identical 9.06 mm × 0.2 mm trunk from F1 pad 2 to the USB-C VBUS pads.

## Key inputs, and where they come from

| Quantity | Value | Source |
|---|---|---|
| F1 hold current `IH` | 2.0 A | Littelfuse RHEF200 datasheet |
| F1 trip current `IT` | 3.8 A | same |
| F1 max time-to-trip | 4.3 s at 10 A | same |
| U1 current limit | 1.18 A typ, 1.26 A max | TPS2553 datasheet, `IOS` equations, R6 = 22 kΩ |
| U1 `rDS(on)` | 115 mΩ max at 25 °C | TPS2553 datasheet |
| Copper thickness | 35 µm (1 oz) | board stackup |
| Substrate | 1.51 mm FR4, 2 layer | board stackup |
