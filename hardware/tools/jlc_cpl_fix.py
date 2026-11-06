"""Compute JLCPCB placement corrections by fitting each part's JLCPCB/EasyEDA footprint onto the KiCad board pads.

For every assembled part: take JLCPCB's footprint pads (from the EasyEDA API JSON, cached per LCSC number),
try 0/90/180/270 degrees, translate to match our board pads (by pad number when the numbering agrees, otherwise
purely by geometry), and keep the best fit. The best fit is exactly where/how JLCPCB must place its part,
so it becomes the corrected CPL row.

usage: /usr/bin/python3 jlc_cpl_fix.py board.kicad_pcb jlcpcb_bom.csv lcsc_json_dir out_cpl.csv
"""
import sys, csv, json, math, os
import pcbnew as P

BOARD, BOM, JDIR, OUT = sys.argv[1:5]
b = P.LoadBoard(BOARD)
mm = P.ToMM

def jlc_pads(lcsc):
    d = json.load(open(os.path.join(JDIR, lcsc + '.json')))['result']
    ds = d['packageDetail']['dataStr']; hx, hy = float(ds['head']['x']), float(ds['head']['y'])
    pads = []
    for s in ds['shape']:
        if s.startswith('PAD'):
            f = s.split('~')
            pads.append((f[8], (float(f[2]) - hx) * 0.254, (float(f[3]) - hy) * 0.254))
    return pads, d['packageDetail']['title']

def rot(x, y, deg):   # KiCad/JLC visual CCW rotation in a y-down frame
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return x * c + y * s, -x * s + y * c

def fit(ours, theirs):
    """ours: {num: [(x,y)...]} world; theirs: [(num,x,y)] local. returns (err, X, Y, deg, method)."""
    best = None
    names_ok = {n for n, _, _ in theirs} <= set(ours) and len(theirs) >= 2
    O = [p for v in ours.values() for p in v]
    for deg in (0, 90, 180, 270):
        T = [(n,) + rot(x, y, deg) for n, x, y in theirs]
        if names_ok:   # translation = mean offset between same-numbered pads (nearest same-number pad)
            pairs = []
            for n, x, y in T:
                pairs.append((n, x, y))
            # initial guess from centroids, then refine with nearest same-number pad
            cx = sum(p[0] for p in O) / len(O) - sum(t[1] for t in T) / len(T)
            cy = sum(p[1] for p in O) / len(O) - sum(t[2] for t in T) / len(T)
            for _ in range(3):
                dx = dy = 0.0; err = 0.0
                for n, x, y in T:
                    tx, ty = x + cx, y + cy
                    ox, oy = min(ours[n], key=lambda p: (p[0] - tx) ** 2 + (p[1] - ty) ** 2)
                    dx += ox - tx; dy += oy - ty; err += math.hypot(ox - tx, oy - ty)
                cx += dx / len(T); cy += dy / len(T)
            err = sum(min(math.hypot(o[0] - (x + cx), o[1] - (y + cy)) for o in ours[n]) for n, x, y in T) / len(T)
            method = 'pad numbers'
        else:          # geometry only: align centroids, nearest-neighbour residual
            cx = sum(p[0] for p in O) / len(O) - sum(t[1] for t in T) / len(T)
            cy = sum(p[1] for p in O) / len(O) - sum(t[2] for t in T) / len(T)
            err = sum(min(math.hypot(o[0] - (x + cx), o[1] - (y + cy)) for o in O) for _, x, y in T) / len(T)
            method = 'geometry'
        if best is None or err < best[0] - 1e-6: best = (err, cx, cy, deg, method)
    return best

# JLCPCB pad numbering that differs from ours (checked against each part's JLCPCB symbol pin names)
PADMAP = {'C160478': {'1': '2', '2': '1'},   # LED: JLC 1=A,2=C ; ours 1=K,2=A
          'C22452':  {'1': '2', '2': '1'}}   # SS54: JLC 1=A,2=K ; ours 1=K,2=A
ONLY = {'C585350': set('12345678')}          # microSD: fit on the 8 signal pads (detect/shield numbered differently)
GEOM = {'C72443'}                            # KMR2 buttons: symmetric 4-pad part, fit by geometry
bom = list(csv.DictReader(open(BOM)))
rows, report = [], []
for r in bom:
    lcsc = r['LCSC Part #']
    theirs, title = jlc_pads(lcsc)
    if lcsc in PADMAP: theirs = [(PADMAP[lcsc].get(n, n), x, y) for n, x, y in theirs]
    if lcsc in ONLY: theirs = [t for t in theirs if t[0] in ONLY[lcsc]]
    if lcsc in GEOM: theirs = [('?', x, y) for _, x, y in theirs]
    for ref in r['Designator'].split(','):
        fp = b.FindFootprintByReference(ref)
        ours = {}
        for p in fp.Pads():
            if p.GetAttribute() == P.PAD_ATTRIB_NPTH: continue
            ours.setdefault(p.GetNumber(), []).append((mm(p.GetPosition().x), mm(p.GetPosition().y)))
        th = [t for t in theirs if t[0] in ours] if {t[0] for t in theirs} & set(ours) else theirs
        if lcsc in GEOM: th = theirs
        err, X, Y, deg, method = fit(ours, th)
        kx, ky, kr = mm(fp.GetPosition().x), mm(fp.GetPosition().y), fp.GetOrientationDegrees() % 360
        dpos = math.hypot(X - kx, Y - ky); drot = (deg - kr) % 360
        rows.append([ref, f'{X:.4f}mm', f'{-Y:.4f}mm', 'Top', f'{deg:.1f}'])
        flag = 'OK' if dpos < 0.05 and drot == 0 else 'CORRECTED'
        if err > 0.15: flag = 'CHECK (poor fit)'
        report.append((ref, lcsc, title, method, round(err, 3), round(X - kx, 2), round(Y - ky, 2), kr, deg, flag))

with open(OUT, 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation']); w.writerows(rows)
print(f"{'ref':5} {'flag':17} {'fit err':>7} {'dX':>6} {'dY':>6} {'KiCad rot':>9} {'JLC rot':>7}  method / JLC footprint")
for ref, lcsc, title, method, err, dx, dy, kr, deg, flag in sorted(report, key=lambda t: (t[-1] == 'OK', t[0])):
    if flag != 'OK' or ref in ('U1', 'X3', 'J1'):
        print(f'{ref:5} {flag:17} {err:7.3f} {dx:6.2f} {dy:6.2f} {kr:9.0f} {deg:7.0f}  {method} / {title}')
print('parts OK as exported:', sum(1 for t in report if t[-1] == 'OK'), 'of', len(report))
