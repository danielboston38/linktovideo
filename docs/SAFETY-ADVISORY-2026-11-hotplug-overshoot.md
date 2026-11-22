# Safety Advisory: plugging in a live charger can overvolt U1

**Advisory date:** 2026-11-22
**Severity:** Medium. It depends on the charger, and a single plug-in can do it.
**Status:** Fixed in source by adding C5. Existing boards are affected. They can be reworked, or you can use a USB-C charger.
**Evidence:** Circuit simulation. The bench has not confirmed it yet. TI warns about this effect in the TPS2553 datasheet, section 10.2.1.2.4.

---

## Am I affected?

**Your board is affected** if it was built from this repository before C5 was added.
That covers every board fabricated so far: v1 (*Kirby's New Dream*) and v2 (*Link to Video*).

**Your setup is at risk** only when the USB cable is **already live** before it touches the board. For example:

- a USB-A charger or USB-A power bank with an A-to-C cable
- any adapter or "dumb" cable that keeps 5 V on the plug all the time

**A USB-C charger or power bank with a C-to-C cable is safe.** A USB-C source keeps the
plug at 0 V until it detects the board. Then it turns the 5 V on with a slow ramp.
There is no sudden step, so nothing rings.

---

## What is wrong

U1 (TPS2553) is the electronic fuse that protects the NES. Its **IN pin has an absolute maximum of 7.0 V.**

When a live cable touches the board, the voltage at the board jumps from 0 V to 5 V in well under a microsecond.
The cable has inductance, about 0.5–2 µH. The only capacitor on U1's input is C3, 100 nF.
Together they form a resonant circuit, and almost nothing damps it. The voltage overshoots to nearly twice the supply:

| Cable | Peak voltage at U1 IN |
|---|---|
| 0.5 µH, 100 mΩ | 9.4 V |
| 1.0 µH, 150 mΩ | 9.5 V |
| 2.0 µH, 250 mΩ | 9.5 V |

The spike lasts a few microseconds. That is 2–3 V over the absolute maximum, on every plug-in.

How fast the contact closes matters. A rise time under 1 µs, which is typical for a plug going in, gives the full overshoot.
Over about 2 µs, the overshoot mostly goes away.

D1 (1.5KE6.8A) does not help. It is on U1's **output**, not its input.

### What can happen

A part that is driven over its absolute maximum can fail at once, or it can weaken over many plug-ins. If U1 fails:

- **Open:** the NES gets no power. This is safe but annoying.
- **Short:** the NES still works, but nothing limits its current any more.
  F1 (2 A hold, 3.8 A trip) is then the only protection.

This is not a fire risk on its own. It is a way to lose the current limit without noticing.

---

## The fix

**C5: 100 µF aluminium electrolytic, 16 V or more, 5 mm diameter, 2.0 mm pitch,** from `/fused_5v` to GND.
It sits between F1 and R4. Its + pad connects to F1's output pad on the bottom layer.

At this size, the cable's resistance and F1's resistance damp the circuit, and the overshoot goes away:

| C5 type | Typical cable (150 mΩ) | Short thick cable (30 mΩ), 2 µH |
|---|---|---|
| **Standard aluminium electrolytic** | **4.8 V** | **5.0 V** |
| Low-ESR aluminium | 4.8 V | 5.3 V |
| Polymer (almost no ESR) | 5.0 V | 6.2 V |

**Use a standard electrolytic.** Its internal resistance (ESR) adds damping. A polymer or low-ESR part
still stays under 7 V, but with much less margin.

C5 does not change how the board starts. U1 still ramps the NES up in its current limit. Its die stays at 60 °C or below,
even with 4700 µF on the NES side.

---

## What you should do

### Option 1: use a USB-C source (no soldering)

Power the board from a USB-C charger or power bank, with a C-to-C cable. That source does not drive 5 V until it
detects the board, so the spike never happens.

Do **not** use a USB-A charger with an A-to-C cable.

### Option 2: add the capacitor (about 10 minutes)

Solder a 100 µF, 16 V (or more) standard electrolytic between U1's input net and ground:

1. **+ lead** (the long lead, away from the stripe) goes to **F1's output pin**. That is the F1 pin that connects to
   U1 pin 1, not the pin from the USB-C connector. Check it with a continuity meter.
2. **− lead** (the stripe side) goes to any ground point. On v2, **C1's − pin** is close by.
3. Keep the leads short, and insulate them so they cannot touch anything else.

---

## How this was found

A simulation of the full power path, USB-C → F1 → U1 → NES, run on 2026-11-22.
It looked at startup, voltage drop and fault behaviour. The hot-plug case was added because the TPS2553 datasheet
warns about input overshoot with long, inductive cables.

The simulation is in [`sim/power-path/`](../sim/power-path/). It includes the model, its assumptions
and the command to reproduce every number above.
