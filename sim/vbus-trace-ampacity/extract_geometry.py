#!/usr/bin/env python3
"""Extract routed trace geometry, by connectivity, from KiCad PCBs and Gerbers.

Two independent sources:
  from_kicad()  - reads .kicad_pcb segments, walks the net graph between pads
  from_gerber() - reads an F_Cu .gbr, walks the draw-command graph

The Gerber path is what the advisory quotes, because it describes the boards as
actually manufactured. Walking connectivity matters: a bounding-box measurement
of the same corridor under-reports the run, because the route leaves the box.
"""
import math
import re
from collections import defaultdict


def _walk(adj, src, dst):
    """Breadth-first path between two nodes; returns [(width, length), ...]."""
    prev = {src: None}
    q = [src]
    while q:
        c = q.pop(0)
        if c == dst:
            break
        for nb, w in adj[c]:
            if nb not in prev:
                prev[nb] = (c, w)
                q.append(nb)
    if dst not in prev:
        return None
    out, c = [], dst
    while prev[c]:
        p, w = prev[c]
        out.append((w, math.hypot(c[0] - p[0], c[1] - p[1])))
        c = p
    return out[::-1]


def _nearest(adj, pt):
    return min(adj, key=lambda q: math.hypot(q[0] - pt[0], q[1] - pt[1]))


def kicad_pads(path):
    """{ 'REF.PAD': (x, y, net) } in board coordinates."""
    s = open(path).read()
    res = {}
    for fp in re.finditer(
            r'\(footprint(.*?)\n\t\)\n(?=\t\(footprint|\t\(gr_|\t\(segment|\t\(zone|\t\(via)',
            s, re.S):
        blk = fp.group(1)
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        at = re.search(r'^\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', blk, re.M)
        if not ref or not at:
            continue
        ox, oy, rot = float(at.group(1)), float(at.group(2)), float(at.group(3) or 0)
        for pm in re.finditer(
                r'\(pad "([^"]*)"[^\n]*\n\t\t\t\(at ([-\d.]+) ([-\d.]+)(?: [-\d.]+)?\)(.*?)\(net "([^"]*)"\)',
                blk, re.S):
            pn, px, py, _, net = pm.groups()
            a = math.radians(-rot)
            px, py = float(px), float(py)
            res[f"{ref.group(1)}.{pn}"] = (
                round(ox + px * math.cos(a) - py * math.sin(a), 3),
                round(oy + px * math.sin(a) + py * math.cos(a), 3), net)
    return res


def from_kicad(path, net, pad_a, pad_b):
    """Ordered [(width_mm, length_mm), ...] from pad_a to pad_b along `net`."""
    s = open(path).read()
    adj = defaultdict(list)
    for m in re.finditer(
            r'\(segment\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)'
            r'\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)\s*(?:\(locked yes\)\s*)?\(net "([^"]*)"\)', s):
        x1, y1, x2, y2, w, _, n = m.groups()
        if n != net:
            continue
        a = (round(float(x1), 3), round(float(y1), 3))
        b = (round(float(x2), 3), round(float(y2), 3))
        adj[a].append((b, float(w)))
        adj[b].append((a, float(w)))
    pads = kicad_pads(path)
    return _walk(adj, _nearest(adj, pads[pad_a][:2]), _nearest(adj, pads[pad_b][:2]))


def from_gerber(path, pt_a, pt_b):
    """Ordered [(width_mm, length_mm), ...] between two points in an F_Cu Gerber.

    Points are (x_mm, y_mm) in Gerber coordinates (y negative, KiCad export).
    """
    s = open(path).read()
    ap = {m.group(1): float(m.group(2))
          for m in re.finditer(r'%ADD(\d+)C,([\d.]+)\*%', s)}
    adj = defaultdict(list)
    cur = None
    x = y = 0.0
    for line in s.splitlines():
        m = re.match(r'D(\d+)\*$', line)
        if m and m.group(1) in ap:
            cur = ap[m.group(1)]
            continue
        m = re.match(r'X(-?\d+)Y(-?\d+)D0([123])\*', line)
        if not m:
            continue
        nx, ny = int(m.group(1)) / 1e6, int(m.group(2)) / 1e6
        if m.group(3) == '1' and cur is not None:
            a = (round(x, 3), round(y, 3))
            b = (round(nx, 3), round(ny, 3))
            adj[a].append((b, cur))
            adj[b].append((a, cur))
        x, y = nx, ny
    return _walk(adj, _nearest(adj, pt_a), _nearest(adj, pt_b))


def summarise(path):
    """Collapse a walked path into totals per width."""
    by = defaultdict(float)
    for w, l in path:
        by[w] += l
    return dict(sorted(by.items()))


def net_widths(path, nets=None):
    """{net: {width: total_mm}} for every routed segment in a .kicad_pcb."""
    s = open(path).read()
    d = defaultdict(lambda: defaultdict(float))
    for m in re.finditer(
            r'\(segment\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)'
            r'\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)\s*(?:\(locked yes\)\s*)?\(net "([^"]*)"\)', s):
        x1, y1, x2, y2, w, _, n = m.groups()
        if nets and n not in nets:
            continue
        d[n][float(w)] += math.hypot(float(x2) - float(x1), float(y2) - float(y1))
    return {k: dict(sorted(v.items())) for k, v in d.items()}
