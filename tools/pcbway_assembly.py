#!/usr/bin/env python3
"""Turn a prefab-gate fab package into PCBWay SMD-assembly-only upload files.

The gate exports a whole-board BOM and CPL. PCBWay assembling only the SMD
side needs the opposite: the four reflow parts on their own, in PCBWay's
turnkey column order, with the through-hole parts held back for hand
assembly. Mount type comes from the board's own `(attr smd|through_hole)`
rather than a hand-kept list, so a part that changes mounting cannot silently
keep its old side of the split.

    python3 tools/pcbway_assembly.py <board.kicad_pcb> <package-dir>

Writes assembly_bom_smd.csv and assembly_cpl_smd.csv into the package dir.
"""
import csv, os, re, sys

def find_blocks(src, tag):
    out = []
    for m in re.finditer(r'\(' + re.escape(tag) + r'\s', src):
        i, depth, j, in_str = m.start(), 0, m.start(), False
        while j < len(src):
            c = src[j]
            if in_str:
                if c == '\\':
                    j += 2
                    continue
                if c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    out.append((i, j + 1))
                    break
            j += 1
    return out

# Footprint name -> the package name a human assembler recognises.
PACKAGE_RULES = [
    (r'_(\d{4})_\d{4}Metric', lambda m: m.group(1)),
    (r'(SOT-\d+-\d+)', lambda m: m.group(1)),
    (r'(SOT-\d+)', lambda m: m.group(1)),
    (r'(QFN|DFN|SOIC|TSSOP|MSOP|LQFP|TQFP)[-_]?(\d+)', lambda m: f'{m.group(1)}-{m.group(2)}'),
    (r'USB_C_Receptacle.*?(\d+)P', lambda m: f'USB-C receptacle {m.group(1)}P'),
]

def package_of(footprint):
    bare = footprint.split(':')[-1]
    for pat, fn in PACKAGE_RULES:
        m = re.search(pat, bare)
        if m:
            return fn(m)
    return bare

def read_board(board_path):
    """{ref: {'kind','side','props'}} straight from the board."""
    src = open(board_path).read()
    out = {}
    for s, e in find_blocks(src, 'footprint'):
        b = src[s:e]
        fields = {}
        for ps, pe in find_blocks(b, 'property'):
            m = re.match(r'\(property\s+"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"', b[ps:pe])
            if m:
                fields[m.group(1)] = m.group(2).replace('\\"', '"')
        ref = fields.get('Reference')
        if not ref:
            continue
        attr = re.search(r'\n\t\t\(attr ([^)]*)\)', b)
        words = attr.group(1).split() if attr else []
        kind = 'smd' if 'smd' in words else 'through_hole' if 'through_hole' in words else 'other'
        layer = re.search(r'\n\t\t\(layer "([^"]+)"', b)

        # A footprint KiCad calls SMD can still carry through-hole pads — the
        # shell stakes on a Type-C receptacle, say. When those stakes are on a
        # paste layer they reflow with everything else (pin-in-paste) and the
        # part is Hybrid, not SMD; an assembler told "SMD" may leave them dry.
        pads = []
        for ps, pe in find_blocks(b, 'pad'):
            pb = b[ps:pe]
            m = re.match(r'\(pad\s+"([^"]*)"\s+(\S+)', pb)
            layers = re.search(r'\(layers ([^)]*)\)', pb)
            pads.append((m.group(2) if m else '?',
                         'Paste' in (layers.group(1) if layers else '')))
        thru = [t for t in pads if t[0] == 'thru_hole']
        out[ref] = {
            'kind': kind,
            'side': 'bottom' if layer and layer.group(1).startswith('B.') else 'top',
            'props': fields,
            'pads': pads,
            'thru_pads': len(thru),
            'thru_pasted': sum(1 for t in thru if t[1]),
        }
    return out


def describe(fields, value):
    """What PCBWay's sourcing desk needs to buy the right part.

    `Spec` states the orderable requirement (tolerance, voltage, dielectric);
    the stock symbol `Description` is often just "Resistor". Prefer the former.
    """
    for key in ('Spec', 'Description'):
        text = (fields.get(key) or '').strip()
        if text and text.lower() not in ('resistor', 'unpolarized capacitor',
                                         'polarized capacitor'):
            return text
    return value

def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    board, pkg = sys.argv[1], sys.argv[2]
    fp = read_board(board)

    bom = list(csv.DictReader(open(os.path.join(pkg, 'bom.csv'))))
    cpl = list(csv.DictReader(open(os.path.join(pkg, 'cpl.csv'))))

    smd = [r for r in bom if fp.get(r['Reference'], {}).get('kind') == 'smd']
    tht = [r for r in bom if fp.get(r['Reference'], {}).get('kind') != 'smd']
    if not smd:
        sys.exit('no SMD parts found on the board — nothing to assemble')

    missing = [r['Reference'] for r in smd if not r.get('MPN')]
    if missing:
        sys.exit(f'SMD parts without an MPN, which PCBWay sources by: {", ".join(missing)}')

    # Group by MPN — PCBWay wants one line per distinct part.
    lines, order = {}, []
    for r in smd:
        key = r['MPN']
        if key not in lines:
            lines[key] = {'refs': [], 'row': r}
            order.append(key)
        lines[key]['refs'].append(r['Reference'])

    bom_out = os.path.join(pkg, 'assembly_bom_smd.csv')
    with open(bom_out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Line#', 'Qty', 'Designator', 'MPN', 'Manufacturer',
                    'Description', 'Package', 'Type', 'LCSC', 'Datasheet'])
        for n, key in enumerate(order, 1):
            g = lines[key]
            r = g['row']
            w.writerow([n, len(g['refs']), ','.join(g['refs']), r['MPN'],
                        r.get('Manufacturer', ''),
                        describe(fp[r['Reference']]['props'], r.get('Value', '')),
                        package_of(r['Footprint']),
                        'Hybrid' if fp[r['Reference']]['thru_pads'] else 'SMD',
                        r.get('LCSC', ''), r.get('Datasheet', '')])

    keep = {r['Reference'] for r in smd}
    cpl_out = os.path.join(pkg, 'assembly_cpl_smd.csv')
    with open(cpl_out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        for r in cpl:
            if r['Ref'] not in keep:
                continue
            w.writerow([r['Ref'], f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm",
                        f"{float(r['Rot']):.1f}", r['Side'].capitalize()])

    sides = {fp[r['Reference']]['side'] for r in smd}
    print(f'SMD lines : {len(order)} ({len(smd)} placements) -> {bom_out}')
    print(f'CPL rows  : {len(smd)} -> {cpl_out}')
    print(f'SMD sides : {", ".join(sorted(sides))}'
          + ('  (single-sided reflow)' if len(sides) == 1 else '  (DOUBLE-SIDED reflow)'))
    print(f'Hand-fit  : {len(tht)} through-hole parts held back — '
          + ', '.join(r['Reference'] for r in tht))
    for r in smd:
        d = fp[r['Reference']]
        if d['thru_pads']:
            how = ('pin-in-paste, reflows with the SMD pass'
                   if d['thru_pasted'] == d['thru_pads']
                   else 'NOT on a paste layer — needs hand-soldering')
            print(f"Hybrid    : {r['Reference']} has {d['thru_pads']} through-hole "
                  f"pad(s) among {len(d['pads'])} — {how}")

if __name__ == '__main__':
    main()
