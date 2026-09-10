# Safety Advisory — VBUS input trace is undersized for its own fuse

**Advisory date:** 2026-09-09
**Severity:** Low probability, high consequence. Requires a second fault to manifest.
**Status:** Fixed in source. Existing boards are affected and can be reworked.
**Fixed by:** commit `247334c` — *fix(pcb): reroute /raw_5v out of the 0.2 mm bottleneck past USB-C1* (2026-09-08)

---

## Am I affected?

**Yes, if your board came from either PCBWay fab package:**

| Fab package | 0.2 mm trunk on `/raw_5v` | Affected |
|---|---|---|
| `2026-07-07-13-47-14` | 9.06 mm | **Yes** |
| `2026-07-16-23-35-56` | 9.06 mm | **Yes** |
| Anything built from repo source before `247334c` (2026-09-08) | 7.95–9.06 mm | **Yes** |
| Repo source at or after `247334c` | 0 mm on the trunk | No |

This covers **every board that has ever been fabricated for this project**, including
all boards silkscreened *Kirby's New Dream*. It was verified by walking the copper
connectivity in the shipped Gerber files themselves, not from the KiCad source.

Note that the as-fabbed run (9.06 mm) is slightly **worse** than what the repository
source carried immediately before the fix (7.95 mm), so figures quoted from the repo
history understate what is on a physical board.

**Quick physical check:** look at the front-copper run between the USB-C connector's
VBUS pads and pin 2 of F1 (the polyfuse). On an affected board it is a hairline trace
roughly the same width as a signal trace, about 9 mm long. On a corrected board it is
visibly fat — the same width as the other power traces.

---

## What is wrong

The VBUS input runs from the USB-C receptacle to F1 through **9.06 mm of 0.2 mm-wide
trace on 1 oz copper**. That segment is the trunk: both VBUS pins (A9 and B9) feed
through it, so **100 % of the board's input current crosses it with no parallel path.**

The problem is not the trace on its own. It is the trace *relative to the fuse behind
it*. F1 is a Littelfuse RHEF200: it is guaranteed **never to trip below 2.0 A**, and
guaranteed to trip **only above 3.8 A**.

Electrothermal simulation of the as-fabbed geometry:

| Input current | Peak trace temperature | F1 behaviour |
|---|---|---|
| 1.18 A — normal maximum, set by U1's current limit | 48 °C | fine |
| **2.00 A — max current F1 will hold indefinitely** | **105 °C** | **never trips** |
| 2.50 A | 174 °C | may not trip |
| 3.00 A — max from a compliant USB-C source | 303 °C | may not trip |
| 3.80 A — F1's guaranteed trip current | thermal runaway | trips at last |

Damage thresholds for the as-fabbed trace:

- **2.22 A** — exceeds FR4's glass transition (130 °C)
- **2.83 A** — charring and delamination (250 °C)
- F1 is not guaranteed to trip until **3.8 A**

**So there is a window from roughly 2.2 A to 3.8 A in which the trace is being
destroyed and the fuse is not guaranteed to do anything at all.** Because the board
presents 5.1 kΩ Rd on both CC pins, a compliant USB-C source will happily deliver up
to 3.0 A — landing in the middle of that window. At 3.0 A the trace passes FR4's glass
transition in **0.63 s** and continues heating toward 303 °C while F1 sits below its
trip current, potentially forever.

At higher fault currents the trace simply becomes the fuse. At 10 A — where F1 is
*specified* to trip within 4.3 s — the trace reaches the melting point of copper in
**48 ms**, roughly 90× faster than the device meant to protect it.

The design invariant that was violated is simple:

> The current that damages the narrowest trace must be **higher** than the fuse's trip current.

As fabbed: 2.22 A < 3.8 A ❌  After the fix: 5.64 A > 3.8 A ✅

---

## Root cause: a netclass pattern that never matched

The trace was not routed carelessly. It was routed **exactly as the board's own rules
instructed** — the rules were just wrong.

The board defines two netclasses: `Default` at 0.2 mm track width, and `Power` at
0.8 mm. Nets are assigned to `Power` by name pattern. At fab time those patterns were:

```
Power  <-  /5V*
Power  <-  GND*
Power  <-  VBUS
```

The USB input net is named **`/raw_5v`**. It matches none of those patterns — not
`/5V*`, and not `VBUS`. So the highest-current net on the entire board silently fell
through to **`Default`, 0.2 mm**, and the router faithfully gave it 0.2 mm. The sibling
net `/fused_5v` fell through the same gap.

`/raw_5v` was only added to the `Power` pattern list on 2026-09-07, one day before the
reroute. The fix therefore had two halves: correcting the netclass assignment, and then
**manually rerouting the trace to the 0.8 mm it should have been all along.**

### Why DRC never caught it

Because it isn't a DRC violation. KiCad's design-rule checker enforces the *board-wide*
`min_track_width`, which is set to **0.2 mm** here. It does **not** enforce a netclass's
`track_width`, which is a default for newly routed tracks rather than a constraint.

A 0.2 mm trace on a net whose netclass specifies 0.8 mm is therefore completely legal.
**The affected boards passed DRC with zero errors**, and passed ERC, and passed
`check_nets.py`, which verifies net assignment rather than geometry. Every automated
gate this project had was blind to it in a different way.

This is the general lesson worth taking away from the advisory: **a netclass is only as
good as the pattern that assigns nets to it, and nothing in the standard toolchain will
tell you when a pattern fails to match the net you meant.**

---

## Audit of the other power nets

Because the root cause was a pattern gap rather than a routing mistake, every
current-carrying net was re-checked for the same defect. Results:

| Net | Narrowest copper on its current path | Verdict |
|---|---|---|
| `/raw_5v` (USB-C → F1) | **0.20 mm × 9.06 mm** as fabbed | **The defect. Fixed in `247334c`.** |
| `/fused_5v` (F1 → U1 IN) | 0.60 mm | **OK** — 68 °C at F1's 3.8 A trip; exceeds Tg only at 5.43 A |
| `/5V` (U1 OUT → console) | 0.20 mm | **OK** — see below |
| `GND` | 0.40 mm + pour | OK |

**`/5V` deserves an explanation,** because it also carries 0.2 mm copper and it is the
output rail. It is safe for a specific reason: it sits **downstream of U1's current
limit**, which is hard-capped at 1.26 A worst case by the 22 kΩ on ILIM. A 0.2 mm trace
at 1.26 A settles at about 50 °C. U1 protects it in a way that F1 could never protect
`/raw_5v`.

That contrast is the whole point of this advisory: `/raw_5v` was the **only** high-current
net upstream of the current limit, guarded solely by a fuse whose trip current it could
not survive.

The 0.40 mm copper on `/fused_5v` goes to U1 pin 3 (EN) and C3, not to pin 1 (IN). EN is
a high-impedance input drawing ±0.5 µA, so that branch carries no meaningful current.


---

## How dangerous is this in practice?

**Be reassured about normal use.** Under normal operation the trace runs at 48 °C and
costs 17 mV of rail sag. It is not marginal, it is not degrading, and it will not fail
on its own. A board that works today will keep working. This is a *fault-tolerance*
defect, not a wear-out or reliability defect — which is exactly why it survived bench
testing and shipped.

**The risk requires a second fault first.** Something downstream of the trace but
upstream of U1's current limit has to fail short. Realistic candidates:

- **C3 (100 nF MLCC) cracking short** — the classic ceramic-capacitor failure from
  board flex, and this board gets installed inside a console with cables pulling on it.
- **U1 input failure** — already a known unprotected path: D1 does not clamp below
  U1's 7 V absolute maximum (see *Known Issues*), so a surge can take U1 out.
- A solder bridge or debris across F1's input or U1's input pins.

If that happens, instead of the fuse cleanly interrupting, you get a trace heating
past 300 °C inside a closed plastic shell, with the fuse possibly never tripping.
Nearest neighbouring copper is 0.43 mm (GND) and 0.69 mm (CC2), so sustained charring
could also leave a conductive carbon path toward the CC lines.

Probability is low. Consequence is a hot spot inside a sealed console. That combination
is why this is being published rather than quietly fixed.

---

## What you should do

Pick the level of effort you're comfortable with.

### Option 1 — Bodge wire (recommended, ~15 minutes)

Run a short length of insulated wire, **24 AWG or thicker**, from **F1 pin 2** to the
**USB-C VBUS copper**, paralleling the hairline trace. F1 pin 2 is through-hole and
easy to solder. At the far end, either solder to the connector's VBUS pin or scrape a
window in the soldermask on the wide 0.8 mm section next to the connector and tin it.

24 AWG is 0.205 mm² against the trace's 0.007 mm² — about 29× the cross-section — so
the original trace stops mattering entirely. This restores the correct ordering: the
fuse becomes the weakest element again, which is the whole point of fitting one.

### Option 2 — Reinforce the existing trace (~10 minutes, partial)

Scrape the soldermask off the 9 mm run and flood it with solder. This helps, but less
than it looks: solder's resistivity is roughly 8× copper's, so a generous bead adds
only about 50 % to the effective conductance. Better than nothing, not as good as a wire.

### Option 3 — Accept the risk, with awareness

If the board is powered from a modest supply and you accept the risk profile: do not
leave it powered unattended, and unplug immediately if the USB end of the board ever
becomes warm to the touch or you smell hot resin. Normal operation is genuinely fine —
you are only exposed if something else fails first.

### Option 4 — Rebuild from corrected source

Build a new board from `247334c` or later. Note that current `main` also carries
unrelated v2 changes (new Switchcraft jack footprints), so it is not a drop-in
replacement for a v1 bench board.

### What *not* to do

**Do not fit a lower-rated fuse to close the gap.** To protect a 2.22 A trace you would
need a PPTC tripping below that, which means a hold current under about 1.1 A — below
the board's own 1.18 A operating limit. It would nuisance-trip in normal use. The trace
is what needs fixing, not the fuse.

---

## How this was found and verified

Found incidentally during unrelated bench testing, then characterised by simulation
after the fix, to establish what a board carrying the fault would actually do.

**Method.** A distributed electrothermal model of the route: discretised into 0.25 mm
slices, each with temperature-dependent copper resistance, vertical heat loss through
the FR4, and lateral thermal conduction between slices. Solved in ngspice.

**Validation.** The model reproduces IPC-2221 external-layer ampacity within ±8 % from
0.5–2 A, exact at its calibration point. An independent Onderdonk adiabatic fusing
calculation agrees with the simulated 10 A fusing time to about 8 %.

**Geometry.** Taken by walking copper connectivity in the shipped Gerber files for both
fab packages — the boards as actually manufactured, not the KiCad source.

**Conservatism.** The IPC-2221 calibration takes no credit for the B.Cu ground pour
1.51 mm below the trace, so the temperatures above are pessimistic. A sensitivity sweep
was run scaling thermal resistance down to credit that plane:

| Thermal resistance | Exceeds FR4 Tg | Chars |
|---|---|---|
| calibrated (no plane credit) | 2.22 A | 2.83 A |
| 80 % | 2.44 A | 3.12 A |
| 65 % | 2.67 A | 3.41 A |
| 50 % | 2.93 A | 3.75 A |
| 40 % (very generous) | 2.95 A | 3.76 A |

Even crediting the plane with a 60 % reduction in thermal resistance, the charring
threshold asymptotes at **3.76 A — still below F1's 3.8 A guaranteed trip current**.
**Under every assumption tested, the trace is damaged before the fuse is guaranteed to
act.**

**Limits.** Above roughly 300 °C the model is qualitative only — FR4 decomposes and the
thermal parameters stop being valid. Treat runaway figures as "destructive", not as
temperatures. The carbon-tracking secondary effect is reasoned from clearance geometry,
not simulated, and is the least certain claim here.

---

## Reproducing this yourself

The full simulation harness is published in
[`sim/vbus-trace-ampacity/`](../sim/vbus-trace-ampacity/):

```bash
brew install ngspice        # or: apt install ngspice
python3 sim/vbus-trace-ampacity/run_all.py
```

It regenerates every number quoted above, including the validation checks and the
sensitivity sweep. The harness README documents the model, its provenance, and — more
usefully — a list of the assumptions most worth attacking if you want to falsify this.

Independent review is welcome and actively wanted. Please open an issue if any of it
does not hold up.

---

## Credits

Reported and fixed by the project author. Analysis performed with Claude (Anthropic);
see the Disclosure section of the README. Independently verify before relying on any
of it — including this advisory.
