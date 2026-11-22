#!/usr/bin/env python3
"""Power-path simulation: USB-C -> F1 -> U1 (TPS2553) -> /5V -> NES.

Reproduces every figure in docs/SAFETY-ADVISORY-2026-11-hotplug-overshoot.md.
Needs ngspice on PATH. Python 3.9+, standard library only.

U1 is a behavioural model built from the TPS2553 datasheet (TI SLVS841F):
  - switch on-resistance: 95 mOhm (DBV package, 25 C typ), 135 mOhm (hot max)
  - soft start: the output follows a gate ramp of about 4 V/ms
  - current limit for RILIM = 22 k: 1091 min / 1169 nom / 1257 max mA (eq. 1)
  - thermal: R_thJA 182.6 C/W; shuts down at 135 C while limiting, restarts 10 C lower
The NES has its 7805 removed, so its 5 V rail sits directly on /5V. It is
modelled as a resistor that draws 0.9 A at 5 V, plus a bulk capacitance that
is not known, so it is swept.
"""
import argparse
import os
import subprocess
import sys

ILIM = {"min": 1.091, "nom": 1.169, "max": 1.257}
DECKS = "power_sim_decks"

C5_STANDARD = "C5 fin c5e 100u\nRc5 c5e 0 0.3"  # 100 uF aluminium electrolytic, standard ESR


def deck(name, outfile, *, c_nes, ilim, rds=0.095, r_f1=0.08, r_cable=0.15, l_cable=0.0,
         vsrc=5.1, src_rise=5e-3, src_delay=1e-3, tstop=60e-3, step=2e-6, extra=""):
    cable = f"Lc cl vbus {l_cable}" if l_cable else "Rlx cl vbus 1u"
    return f"""* {name}
.option method=gear reltol=1e-4
* --- USB supply and cable (round trip) ---
Vs  src 0 PWL(0 0 {src_delay} 0 {src_delay + src_rise} {vsrc})
Rc  src cl {r_cable}
{cable}
* --- F1 polyfuse, plus /raw_5v and /fused_5v copper (0.8 mm, about 10 mOhm) ---
Rf1 vbus fin {r_f1 + 0.010}
C3  fin 0 100n
{extra}
* --- U1 TPS2553, behavioural ---
* Gate ramp: slews toward Vin at 4 V/ms while enabled; falls fast when disabled or in UVLO.
Cg  g 0 1u
Bg  0 g I = (V(en) > 0.5 ? max(min((V(fin)-V(g))*1, 4e-3), -4e-3) : max(min(-V(g)*10, 0), -20e-3)) * (V(fin) > 2.45 ? 1 : 0) - (V(fin) > 2.45 ? 0 : V(g)*1e-2)
Bsw fin out I = min({ilim}, max(0, (min(V(fin), V(g)) - V(out)) / {rds}))
* Junction temperature: node tj, in volts = degrees C.
Cth tj 0 2m
Rth tj amb 182.6
Vamb amb 0 25
Bp  0 tj I = min({ilim}, max(0, (min(V(fin), V(g)) - V(out)) / {rds})) * max(V(fin)-V(out), 0)
* Thermal shutdown at 135 C, restart at 125 C (switch with hysteresis).
Bctl ctl 0 V = 200 - V(tj)
S1  one en ctl 0 tsd
.model tsd sw vt=70 vh=5 ron=1 roff=1e9
V1  one 0 1
Ren en 0 1e6
* --- /5V: C1, C4, then 0.2 mm x 20.5 mm copper (about 50 mOhm) and harness (about 40 mOhm) ---
C1  out 0 100u
C4  out 0 100n
Rtr out nes 0.090
* --- NES: 0.9 A at 5 V, bulk capacitance swept ---
Rnes nes 0 5.556
Cnes nes 0 {c_nes}
.tran {step} {tstop} 0 {step}
.control
run
wrdata {outfile} v(fin) v(out) v(nes) i(Vs) v(tj)
quit
.endc
.end
"""


def run(name, **kw):
    os.makedirs(DECKS, exist_ok=True)
    cir, out = os.path.join(DECKS, f"{name}.cir"), os.path.join(DECKS, f"{name}.txt")
    with open(cir, "w") as f:
        f.write(deck(name, out, **kw))
    r = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit(f"ngspice failed on {cir}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    rows = []
    with open(out) as f:
        for line in f:
            v = line.split()
            if len(v) >= 10:
                rows.append(dict(t=float(v[0]), fin=float(v[1]), out=float(v[3]),
                                 nes=float(v[5]), isrc=-float(v[7]), tj=float(v[9])))
    return rows


def summarize(rows, t_from=0.0):
    r = [x for x in rows if x["t"] >= t_from]
    end = r[-1]
    t95 = next((x["t"] for x in r if x["nes"] >= 0.95 * end["nes"]), end["t"])
    trips = sum(1 for a, b in zip(r, r[1:]) if a["tj"] < 134 <= b["tj"])
    return dict(vnes_end=end["nes"], vfin_end=end["fin"], t95=t95,
                ipk=max(x["isrc"] for x in r), tj_max=max(x["tj"] for x in r),
                vfin_max=max(x["fin"] for x in r), trips=trips)


def hotplug(name, l, rc, extra="", tstop=1e-3):
    """VBUS already live; the plug makes contact in 0.2 us."""
    return summarize(run(name, c_nes=220e-6, ilim=ILIM["nom"], l_cable=l, r_cable=rc,
                         src_rise=0.2e-6, src_delay=10e-6, tstop=tstop, step=5e-9, extra=extra))


def section_hotplug():
    print("1. HOT PLUG, BOARD AS FABBED (only C3, 100 nF, on U1 IN). U1 IN absolute max = 7.0 V")
    for l in (0.5e-6, 1e-6, 2e-6):
        for rc in (0.10, 0.25):
            s = hotplug(f"hp_asfab_L{l*1e6:g}u_R{rc*1e3:g}m", l, rc, tstop=200e-6)
            flag = "  <-- over 7 V" if s["vfin_max"] > 7.0 else ""
            print(f"   cable {l*1e6:.1f} uH, {rc*1e3:3.0f} mOhm: peak {s['vfin_max']:.2f} V{flag}")
    print("\n   Contact rise time (1 uH, 150 mOhm):")
    for rise in (0.2e-6, 1e-6, 2e-6, 5e-6):
        s = summarize(run(f"hp_rise_{rise*1e6:g}us", c_nes=220e-6, ilim=ILIM["nom"], l_cable=1e-6,
                          r_cable=0.15, src_rise=rise, src_delay=10e-6, tstop=300e-6, step=5e-9))
        print(f"   {rise*1e6:4.1f} us: peak {s['vfin_max']:.2f} V")


def section_fix():
    print("\n2. HOT PLUG WITH C5 (100 uF on /fused_5v)")
    for rc, lab in ((0.15, "typical cable, 150 mOhm"), (0.03, "short thick cable, 30 mOhm")):
        print(f"   {lab}:")
        for esr, kind in ((0.0001, "polymer, ~0 ESR"), (0.08, "low-ESR aluminium"), (0.3, "standard aluminium")):
            peaks = [hotplug(f"fix_R{rc*1e3:g}m_esr{esr*1e3:g}m_L{l*1e6:g}u", l, rc,
                             extra=f"C5 fin c5e 100u\nRc5 c5e 0 {esr}")["vfin_max"] for l in (0.5e-6, 2e-6)]
            print(f"     {kind:20s} L 0.5 / 2 uH: {peaks[0]:.2f} / {peaks[1]:.2f} V")


def section_startup():
    print("\n3. STARTUP WITH C5 (USB-C source ramps VBUS over 5 ms)")
    print(f"   {'NES bulk C':>10} {'Ilim':>4} | {'to 95%':>7} {'Ipk':>6} {'Tj max':>7} {'TSD trips':>9}")
    for c in (47e-6, 220e-6, 1000e-6, 4700e-6):
        for k in ("min", "nom"):
            s = summarize(run(f"su_{c*1e6:g}u_{k}", c_nes=c, ilim=ILIM[k], extra=C5_STANDARD))
            print(f"   {c*1e6:8.0f}uF {k:>4} | {(s['t95']-1e-3)*1e3:5.1f}ms {s['ipk']:5.2f}A "
                  f"{s['tj_max']:6.0f}C {s['trips']:>9}")


def section_steady():
    print("\n4. STEADY STATE AT 0.9 A, voltage at the NES")
    for vs in (5.0, 5.1):
        for rc in (0.10, 0.25, 0.40):
            vals = []
            for rds in (0.095, 0.135):
                s = summarize(run(f"ss_{vs}V_R{rc*1e3:g}m_rds{rds*1e3:g}m", c_nes=220e-6, ilim=ILIM["nom"],
                                  r_cable=rc, rds=rds, vsrc=vs, tstop=40e-3, extra=C5_STANDARD), t_from=35e-3)
                vals.append(s["vnes_end"])
            print(f"   supply {vs:.1f} V, cable {rc*1e3:3.0f} mOhm: {vals[0]:.3f} V (U1 cool) / {vals[1]:.3f} V (U1 hot)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Power-path simulation: USB-C -> F1 -> U1 -> NES")
    ap.add_argument("--decks", default=DECKS, help="where to keep the ngspice decks (default: %(default)s)")
    ap.add_argument("sections", nargs="*", default=["hotplug", "fix", "startup", "steady"])
    a = ap.parse_args()
    DECKS = a.decks
    for name in a.sections:
        globals()[f"section_{name}"]()
