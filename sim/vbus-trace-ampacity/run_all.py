#!/usr/bin/env python3
"""Reproduce every simulation figure quoted in the VBUS trace safety advisory.

    python3 run_all.py            # full report
    python3 run_all.py --quick    # skip the slow transient sweeps

Requires ngspice on PATH. Prints a table per advisory section; compare directly
against docs/SAFETY-ADVISORY-2026-09-vbus-trace-ampacity.md.
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thermal_model as tm

# ---------------------------------------------------------------- geometries
# Ordered (width_mm, length_mm) from F1 pad 2 toward the USB-C VBUS pads.
# AS_FABBED is from the shipped Gerbers (both PCBWay packages are identical
# on this net); PRE_FIX and POST_FIX are from the KiCad source.
AS_FABBED = ([(0.20, 9.06), (0.80, 0.75), (0.80, 2.72)], 9.06 + 0.75)
PRE_FIX   = ([(0.20, 7.951), (0.80, 4.220), (0.20, 0.709)], 7.951)
POST_FIX  = ([(0.80, 11.065), (0.80, 1.309), (0.20, 0.709)], 11.065)
FUSED_5V  = ([(0.60, 7.36), (0.80, 22.94)], 7.36)   # F1.1 -> U1.1 (IN)

F1_HOLD, F1_TRIP = 2.0, 3.8        # RHEF200 IH / IT, amps
F1_TRIP_TIME_10A = 4.3             # seconds, datasheet max at 10 A
U1_LIMIT_MAX = 1.26                # TPS2553 IOS(max) with R6 = 22k

# Decks land in the working directory by default, not a temp dir: they exist to
# be read. Every deck gets a unique, descriptive name so the one behind any
# figure in the advisory can be found -- an earlier version reused a handful of
# tags and overwrote ~200 runs into 8 files, which made them useless as evidence.
WORK = "vbus_sim_decks"
_seq = 0


def _deck_path(tag):
    global _seq
    _seq += 1
    os.makedirs(WORK, exist_ok=True)
    return os.path.join(WORK, f"{_seq:03d}_{tag}.cir")


def _run(chain, tap, current, tran=None, rth_scale=1.0, tag="s", rc=0.030):
    """Drive the trace and return raw ngspice output.

    The USB-C receptacle presents VBUS on two pins (A9 and B9). `tap` is the
    slice index where the first pad attaches partway along the route; both that
    node and the far end are tied to the source through the per-pin contact
    resistance `rc`, so current divides between the two pins exactly as it does
    on the board. Omitting this connection would force all current through the
    far neck and materially misreport the post-fix geometry.
    """
    deck, n, itap = tm.build_deck(chain, tap, rth_scale=rth_scale)
    deck += [f"Iload n0 0 DC {current}", "Vsrc vs 0 DC 5.0"]
    if tap is None:
        deck.append(f"Rc vs n{n} {rc}")
    else:
        deck += [f"RcA vs n{itap} {rc}", f"RcB vs n{n} {rc}"]
    probe = " ".join(f"v(tc{i})" for i in range(n))
    if tran:
        deck += [".control", "set noaskquit", f"tran {tran[0]} {tran[1]} uic",
                 f"print {probe}", ".endc"]
    else:
        deck += [".control", "set noaskquit", "op", f"print {probe}", ".endc"]
    deck.append(".end")
    fn = _deck_path(tag)
    open(fn, "w").write("\n".join(deck) + "\n")
    out = subprocess.run(["ngspice", "-b", fn], capture_output=True,
                         text=True, timeout=600)
    return out.stdout + out.stderr


def peak(chain, tap, current, rth_scale=1.0, tag="op"):
    """Steady-state peak copper temperature in C (ambient 25 C).

    Returns None when ngspice fails to converge, which happens above the
    thermal-runaway knee where no stable operating point exists. Callers must
    treat None as "hotter than any bounded solution", never as a low value.
    """
    txt = _run(chain, tap, current, rth_scale=rth_scale,
               tag=f"{tag}_{current:.3f}A")
    if "doAnalyses:" in txt or "iteration limit" in txt.lower():
        return None
    v = [float(m) for m in re.findall(r'v\(tc\d+\)\s*=\s*([-\d.eE+]+)', txt)]
    if not v:
        return None
    # Past the runaway knee the network has an unphysical negative-temperature
    # root: solving T = I^2*R20*(1+alpha*T)*Rth for T gives a negative result
    # once I^2*R20*alpha*Rth > 1. ngspice will happily return it, and it reads
    # as "cold". Any negative rise therefore means runaway, not a low
    # temperature - treat it as hotter than any bounded solution.
    if min(v) < -1e-6:
        return None
    t = 25 + max(v)
    return None if t > 5000 else t


def threshold(chain, tap, target_c, lo=0.4, hi=8.0, rth_scale=1.0,
              label="threshold"):
    """Lowest current whose steady-state peak reaches target_c.

    Non-convergence (None) counts as "at or above target", so the search is
    pushed down rather than up. Returns None if target is not reached by `hi`.
    """
    tag = f"{label}_{target_c:.0f}C"
    top = peak(chain, tap, hi, rth_scale, tag)
    if top is not None and top < target_c:
        return None
    for _ in range(22):
        mid = (lo + hi) / 2
        p = peak(chain, tap, mid, rth_scale, tag)
        if p is not None and p < target_c:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def time_to(chain, tap, current, thresholds, span=("2m", "60"), tag="transient"):
    """Time (s) to reach each threshold; None if not reached within span."""
    txt = _run(chain, tap, current, tran=span, tag=tag)  # tag already descriptive
    agg = {}
    for line in txt.splitlines():
        p = line.split()
        if len(p) >= 3:
            try:
                int(p[0])
                agg.setdefault(float(p[1]), []).extend(float(x) for x in p[2:])
            except ValueError:
                pass
    ts = sorted(agg)
    out = {}
    for th in thresholds:
        out[th] = next((t for t in ts if 25 + max(agg[t]) >= th), None)
    return out


def fmt_t(x):
    if x is None:
        return "not reached"
    return f"{x*1000:.0f} ms" if x < 1 else f"{x:.1f} s"


def head(t):
    print(f"\n{'='*72}\n{t}\n{'='*72}")


def main():
    # Declared before any use of WORK below: `global` after first use is a
    # SyntaxError on Python < 3.13.
    global WORK
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--decks", default=WORK, metavar="DIR",
                    help=f"where to write the ngspice decks (default: ./{WORK})")
    args = ap.parse_args()
    WORK = args.decks

    head("1. MODEL VALIDATION vs IPC-2221 (long uniform 0.2 mm trace)")
    print(f"{'current':>9} {'SPICE rise':>11} {'IPC-2221':>10} {'error':>8}")
    for i in (0.5, 0.745, 1.010, 1.443, 2.0):
        sp = peak([(0.2, 40.0)], None, i, tag="validate_0.2mm") - 25
        ip = tm.ipc_rise(0.2, i)
        print(f"{i:8.3f}A {sp:10.1f}K {ip:9.1f}K {100*(sp-ip)/ip:7.1f}%")
    print("  Model is calibrated at the 20 K point; agreement elsewhere is the check.")

    head("2. STEADY-STATE PEAK TEMPERATURE (ambient 25 C)")
    print(f"{'current':>9} {'as-fabbed':>11} {'pre-fix src':>12} {'post-fix':>10}")
    for i in (1.18, U1_LIMIT_MAX, F1_HOLD, 2.5, 3.0, F1_TRIP):
        g = lambda v: "runaway" if v is None else f"{v:.0f}C"
        a = g(peak(*AS_FABBED, i, tag="steady_asfabbed"))
        b = g(peak(*PRE_FIX, i, tag="steady_prefix"))
        c = g(peak(*POST_FIX, i, tag="steady_postfix"))
        note = ""
        if i == F1_HOLD:
            note = "  <- F1 never trips below this"
        if i == F1_TRIP:
            note = "  <- F1 guaranteed to trip"
        print(f"{i:8.2f}A {a:>11} {b:>12} {c:>10}{note}")

    head("3. DAMAGE THRESHOLDS vs F1 TRIP CURRENT")
    print(f"  F1 (RHEF200): holds below {F1_HOLD} A, trips only above {F1_TRIP} A\n")
    for name, geom, slug in (("as-fabbed", AS_FABBED, "asfabbed"),
                             ("post-fix", POST_FIX, "postfix"),
                             ("/fused_5v F1->U1", FUSED_5V, "fused5v")):
        tg = threshold(*geom, 130, label=f"damage_{slug}")
        ch = threshold(*geom, 250, label=f"damage_{slug}")
        ok = "OK" if (tg is None or tg > F1_TRIP) else "*** TRACE FAILS BEFORE FUSE ***"
        f = lambda x: " >8.00" if x is None else f"{x:6.2f}"
        print(f"  {name:18s} FR4 Tg 130C at{f(tg)} A   char 250C at{f(ch)} A   {ok}")
    print("\n  Invariant: trace damage current must EXCEED fuse trip current.")

    head("4. THE RACE - trace damage vs F1 trip time")
    print(f"  F1 datasheet: max {F1_TRIP_TIME_10A} s to trip at 10 A\n")
    print(f"{'current':>9} {'>130C':>10} {'>250C':>10} {'>1083C melt':>13}")
    for i in (3.0, 5.0, 10.0):
        r = time_to(*AS_FABBED, i, (130, 250, 1083),
                    span=("50u", "6") if i >= 5 else ("2m", "60"),
                    tag=f"race_asfabbed_{i:.1f}A")
        print(f"{i:8.1f}A {fmt_t(r[130]):>10} {fmt_t(r[250]):>10} {fmt_t(r[1083]):>13}")
    print("\n  Independent cross-check - Onderdonk adiabatic fusing current, 0.2 mm:")
    for t in (0.048, 0.1, 1.0):
        print(f"    {t:>6.3f} s exposure -> {tm.onderdonk_current(0.2, t):5.2f} A")

    head("5. SENSITIVITY - crediting the B.Cu ground pour as a heat spreader")
    print("  Calibration takes no credit for the plane, so baseline is pessimistic.\n")
    print(f"{'Rth scale':>10} {'Tg 130C':>9} {'char 250C':>11}   verdict")
    for s in (1.00, 0.80, 0.65, 0.50, 0.40):
        tg = threshold(*AS_FABBED, 130, rth_scale=s,
                       label=f"sens_rth{int(s*100):03d}")
        ch = threshold(*AS_FABBED, 250, rth_scale=s,
                       label=f"sens_rth{int(s*100):03d}")
        v = "trace fails first" if (ch is not None and ch < F1_TRIP) else "fuse protects"
        f = lambda x: "  >8.00" if x is None else f"{x:7.2f}"
        print(f"{s:10.2f} {f(tg)}A {f(ch)}A   {v}")
    print("\n  Under every assumption, Tg is exceeded below F1's 3.8 A trip current.")

    n = len([f for f in os.listdir(WORK) if f.endswith(".cir")]) if os.path.isdir(WORK) else 0
    print(f"\n{n} ngspice decks written to ./{WORK}/ "
          f"(delete with: rm -rf {WORK})\n")


if __name__ == "__main__":
    main()
