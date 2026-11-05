"""Simple grid router for e_reader_v0.1.kicad_pcb (KiCad 9 pcbnew API, numpy).

Two signal layers (F.Cu / B.Cu), In1.Cu = GND plane, In2.Cu = +3V3 plane.
 - GND / +3V3 pads: short stub to a via that drops into the plane.
 - every other net: A* maze routing (8 directions + vias), tree-grown pad by pad.
KiCad's DRC is the judge of the result; this router only has to be good enough to pass it.

usage: /usr/bin/python3 route_pcb.py in.kicad_pcb out.kicad_pcb
"""
import sys, math, heapq, time
import numpy as np
import pcbnew as P

SRC, DST = sys.argv[1], sys.argv[2]
G = 0.1                                   # grid pitch, mm
CLR, CLR_PWR = 0.15, 0.20                 # clearances (must match board rules)
W_SIG, W_PWR = 0.20, 0.40                 # track widths
VIA_SIG, VIA_PWR = (0.6, 0.3), (0.8, 0.4) # (diameter, drill)
VIA_COST, BOTTOM_COST = 18.0, 1.15        # cost of a via (in grid steps) / bottom-layer step multiplier
PLANE_NETS = {'GND': 'In1', '+3V3': 'In2'}
POWER_NETS = {'GND', '+3V3', 'VBUS', 'VBAT', '/VBAT_RAW', '/VHI', 'Net-(Q4-D)'}
BASE = W_SIG / 2 + CLR                    # every copper item is inflated by this

board = P.LoadBoard(SRC)
mm = P.ToMM
def iu(v): return P.FromMM(float(v))
bb = board.GetBoardEdgesBoundingBox()
X0, Y0, X1, Y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
NX, NY = int(round((X1 - X0) / G)) + 1, int(round((Y1 - Y0) / G)) + 1
LAYERS = [P.F_Cu, P.B_Cu]

own = np.zeros((2, NY, NX), np.int32)     # 0 free, >0 net code owning the (inflated) copper, -1 blocked for all
core = np.zeros((2, NY, NX), np.int32)    # net code of real copper (pads + routed)
padcore = np.zeros((NY, NX), bool)        # any pad copper (no vias here)
xs = X0 + np.arange(NX) * G
ys = Y0 + np.arange(NY) * G

def cell(x, y): return int(round((y - Y0) / G)), int(round((x - X0) / G))
def claim(l, mask_ring, mask_core, net):
    """mark ring cells as owned by net (conflicts -> -1), core cells as net copper."""
    o = own[l]
    ring_free = mask_ring & ((o == 0) | (o == net))
    o[mask_ring & ~ring_free] = -1
    o[ring_free] = net if net > 0 else -1
    if net > 0:
        o[mask_core] = net; core[l][mask_core] = net
    else:
        o[mask_core] = -1

def window(xa, ya, xb, yb):
    i0, j0 = cell(xa, ya); i1, j1 = cell(xb, yb)
    i0, j0 = max(i0, 0), max(j0, 0); i1, j1 = min(i1, NY - 1), min(j1, NX - 1)
    return i0, i1 + 1, j0, j1 + 1

# ---------------------------------------------------------------- obstacles: board edge + rounded corners
edge = np.zeros((NY, NX), bool)
m = 0.3 + BASE
YY, XX = np.meshgrid(ys, xs, indexing='ij')
edge |= (XX < X0 + m) | (XX > X1 - m) | (YY < Y0 + m) | (YY > Y1 - m)
RC = 2.0
for cx, cy in ((X0 + RC, Y0 + RC), (X1 - RC, Y0 + RC), (X0 + RC, Y1 - RC), (X1 - RC, Y1 - RC)):
    corner = ((XX - cx) * np.sign(XX - cx) >= 0) & (np.abs(XX - cx) <= RC) & (np.abs(YY - cy) <= RC)
    sx = 1 if cx > (X0 + X1) / 2 else -1; sy = 1 if cy > (Y0 + Y1) / 2 else -1
    quad = ((XX - cx) * sx > 0) & ((YY - cy) * sy > 0)
    edge |= quad & (np.hypot(XX - cx, YY - cy) > RC - m)
for l in (0, 1): own[l][edge] = -1

# keep-out rule areas (ESP32 antenna)
keep = np.zeros((NY, NX), bool)
for fp in board.GetFootprints():
    for z in fp.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
            zb = z.GetBoundingBox()
            i0, i1, j0, j1 = window(mm(zb.GetLeft()) - BASE, mm(zb.GetTop()) - BASE, mm(zb.GetRight()) + BASE, mm(zb.GetBottom()) + BASE)
            keep[i0:i1, j0:j1] = True
for l in (0, 1): own[l][keep] = -1

# ---------------------------------------------------------------- pads
pads_by_net = {}
for fp in board.GetFootprints():
    for pad in fp.Pads():
        net = pad.GetNetCode()
        pb = pad.GetBoundingBox()
        r = BASE + (CLR_PWR - CLR if pad.GetNetname() in POWER_NETS else 0)
        i0, i1, j0, j1 = window(mm(pb.GetLeft()) - r - G, mm(pb.GetTop()) - r - G, mm(pb.GetRight()) + r + G, mm(pb.GetBottom()) + r + G)
        for li, L in enumerate(LAYERS):
            if not pad.IsOnLayer(L) and not pad.HasHole(): continue
            if not pad.IsOnLayer(L) and pad.HasHole():   # NPTH: block the hole on both layers
                pass
            shape = pad.GetEffectiveShape(L)
            ring = np.zeros((i1 - i0, j1 - j0), bool); cor = np.zeros_like(ring)
            for a in range(i0, i1):
                for b in range(j0, j1):
                    pt = P.VECTOR2I(iu(xs[b]), iu(ys[a]))
                    if shape.Collide(pt, 0): cor[a - i0, b - j0] = True
                    elif shape.Collide(pt, iu(r)): ring[a - i0, b - j0] = True
            R = np.zeros((NY, NX), bool); C = np.zeros((NY, NX), bool)
            R[i0:i1, j0:j1] = ring | cor; C[i0:i1, j0:j1] = cor
            claim(li, R, C, net if pad.GetAttribute() != P.PAD_ATTRIB_NPTH else -1)
            if cor.any(): padcore[i0:i1, j0:j1] |= cor
        if net > 0 and pad.GetAttribute() != P.PAD_ATTRIB_NPTH:
            pads_by_net.setdefault(net, []).append(pad)

netname = {n: board.FindNet(n).GetNetname() for n in pads_by_net}

# ---------------------------------------------------------------- helpers
def disk(r):
    k = int(math.ceil(r / G))
    return [(dy, dx) for dy in range(-k, k + 1) for dx in range(-k, k + 1) if math.hypot(dy, dx) * G <= r + 1e-9]
def erode(mask, r):
    if r <= 1e-9: return mask.copy()
    out = mask.copy(); k = int(math.ceil(r / G))
    pad_ = np.pad(mask, k, constant_values=False)
    for dy, dx in disk(r):
        out &= pad_[k + dy:k + dy + mask.shape[0], k + dx:k + dx + mask.shape[1]]
    return out
def dilate(mask, r):
    return ~erode(~mask, r)

def mark_track(li, a, b, halfw, net, clr):
    xa, ya = a; xb, yb = b
    r = halfw + clr + W_SIG / 2
    i0, i1, j0, j1 = window(min(xa, xb) - r - G, min(ya, yb) - r - G, max(xa, xb) + r + G, max(ya, yb) + r + G)
    X = XX[i0:i1, j0:j1]; Y = YY[i0:i1, j0:j1]
    dx, dy = xb - xa, yb - ya; L2 = dx * dx + dy * dy
    t = np.clip(((X - xa) * dx + (Y - ya) * dy) / L2, 0, 1) if L2 > 0 else np.zeros_like(X)
    d = np.hypot(X - (xa + t * dx), Y - (ya + t * dy))
    R = np.zeros((NY, NX), bool); C = np.zeros((NY, NX), bool)
    R[i0:i1, j0:j1] = d <= r; C[i0:i1, j0:j1] = d <= max(halfw, G * 0.75)
    claim(li, R, C, net)
def mark_via(x, y, dia, net, clr):
    for li in (0, 1): mark_track(li, (x, y), (x, y), dia / 2, net, clr)

tracks, vias = [], []
def add_track(li, a, b, w, net):
    t = P.PCB_TRACK(board); t.SetLayer(LAYERS[li]); t.SetWidth(iu(w)); t.SetNetCode(net)
    t.SetStart(P.VECTOR2I(iu(a[0]), iu(a[1]))); t.SetEnd(P.VECTOR2I(iu(b[0]), iu(b[1])))
    board.Add(t); tracks.append(t)
def add_via(x, y, dia, drill, net):
    v = P.PCB_VIA(board); v.SetPosition(P.VECTOR2I(iu(x), iu(y))); v.SetWidth(iu(dia)); v.SetDrill(iu(drill))
    v.SetViaType(P.VIATYPE_THROUGH); v.SetLayerPair(P.F_Cu, P.B_Cu); v.SetNetCode(net); board.Add(v); vias.append(v)

def net_params(name):
    pwr = name in POWER_NETS
    w = W_PWR if pwr else W_SIG; clr = CLR_PWR if pwr else CLR
    via = VIA_PWR if pwr else VIA_SIG
    return w, clr, via

def masks_for(net, name):
    w, clr, via = net_params(name)
    ok0 = (own[0] == 0) | (own[0] == net); ok1 = (own[1] == 0) | (own[1] == net)
    extra = (w / 2 + clr) - BASE                    # extra margin beyond the BASE inflation
    t0, t1 = erode(ok0, extra), erode(ok1, extra)
    vr = (via[0] / 2 + clr) - BASE
    v = erode(ok0, vr) & erode(ok1, vr) & ~dilate(padcore, via[0] / 2 + 0.05) & ~keep
    return t0, t1, v

# ---------------------------------------------------------------- A* search
SQ2 = math.sqrt(2)
NB = [(0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0), (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2), (-1, -1, SQ2)]
def astar(net, name, sources, targets, tgt_xy, maxexp=6_000_000):
    t0, t1, vok = masks_for(net, name)
    T = [t0.ravel().tolist(), t1.ravel().tolist()]
    V = vok.ravel().tolist()
    tset = set(targets)
    ty, tx = tgt_xy
    def h(i, j): return math.hypot(i - ty, j - tx)
    openh, g, came = [], {}, {}
    for s in sources:
        g[s] = 0.0; heapq.heappush(openh, (h(s[1], s[2]), 0.0, s))
        came[s] = None
    exp = 0
    while openh:
        f, gc, s = heapq.heappop(openh)
        if gc > g.get(s, 1e18): continue
        if s in tset:
            path = []
            while s is not None: path.append(s); s = came[s]
            return path[::-1]
        exp += 1
        if exp > maxexp: return None
        l, i, j = s
        mult = BOTTOM_COST if l == 1 else 1.0
        for di, dj, c in NB:
            a, b = i + di, j + dj
            if a < 0 or b < 0 or a >= NY or b >= NX: continue
            idx = a * NX + b
            if not T[l][idx]: continue
            if di and dj:   # no corner cutting
                if not T[l][i * NX + b] or not T[l][a * NX + j]: continue
            ns = (l, a, b); ng = gc + c * mult
            if ng < g.get(ns, 1e18):
                g[ns] = ng; came[ns] = s; heapq.heappush(openh, (ng + h(a, b), ng, ns))
        if V[i * NX + j]:
            ns = (1 - l, i, j); ng = gc + VIA_COST
            if T[1 - l][i * NX + j] and ng < g.get(ns, 1e18):
                g[ns] = ng; came[ns] = s; heapq.heappush(openh, (ng + h(i, j), ng, ns))
    return None

def commit_path(path, net, name):
    w, clr, via = net_params(name)
    pts = [(l, xs[j], ys[i]) for (l, i, j) in path]
    # split into same-layer runs and simplify collinear points
    runs, cur = [], [pts[0]]
    for p in pts[1:]:
        if p[0] != cur[-1][0]:
            runs.append(cur); add_via(p[1], p[2], via[0], via[1], net); mark_via(p[1], p[2], via[0], net, clr); cur = [p]
        else: cur.append(p)
    runs.append(cur)
    for run in runs:
        li = run[0][0]
        simp = [run[0]]
        for k in range(1, len(run) - 1):
            a, b, c = simp[-1], run[k], run[k + 1]
            if (b[1] - a[1]) * (c[2] - b[2]) - (b[2] - a[2]) * (c[1] - b[1]) != 0: simp.append(b)
        if len(run) > 1: simp.append(run[-1])
        for a, b in zip(simp, simp[1:]):
            add_track(li, (a[1], a[2]), (b[1], b[2]), w, net); mark_track(li, (a[1], a[2]), (b[1], b[2]), w / 2, net, clr)

def pad_cells(pad, net):
    cells = []
    pb = pad.GetBoundingBox()
    i0, i1, j0, j1 = window(mm(pb.GetLeft()), mm(pb.GetTop()), mm(pb.GetRight()), mm(pb.GetBottom()))
    for li, L in enumerate(LAYERS):
        if not pad.IsOnLayer(L): continue
        sub = core[li][i0:i1, j0:j1] == net
        for a, b in zip(*np.nonzero(sub)): cells.append((li, a + i0, b + j0))
    return cells

# ---------------------------------------------------------------- 1. plane nets: stub + via per SMD pad
t_start = time.time(); fails = []
for net, pads in pads_by_net.items():
    name = netname[net]
    if name not in PLANE_NETS: continue
    w, clr, via = net_params(name)
    for pad in pads:
        if pad.HasHole(): continue                  # PTH pads (thermal vias, USB shield) reach the plane already
        if not pad.IsOnLayer(P.F_Cu): continue
        _, _, vok = masks_for(net, name)
        t0, _, _ = masks_for(net, name)
        src = pad_cells(pad, net)
        src = [s for s in src if s[0] == 0]
        if not src: continue
        # BFS on F.Cu from the pad to the nearest via-capable cell
        from collections import deque
        q = deque(); seen = {}
        for s in src: q.append((s[1], s[2])); seen[(s[1], s[2])] = None
        hit = None
        while q:
            i, j = q.popleft()
            if vok[i, j]: hit = (i, j); break
            for di, dj, _ in NB:
                a, b = i + di, j + dj
                if 0 <= a < NY and 0 <= b < NX and (a, b) not in seen and t0[a, b] and len(seen) < 40000:
                    seen[(a, b)] = (i, j); q.append((a, b))
        if not hit: fails.append(f'{name}:{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()} (no via spot)'); continue
        path = []; c = hit
        while c is not None: path.append((0, c[0], c[1])); c = seen[c]
        path = path[::-1]
        px, py = xs[hit[1]], ys[hit[0]]
        if len(path) > 1: commit_path(path, net, name)
        add_via(px, py, via[0], via[1], net); mark_via(px, py, via[0], net, clr)
print(f'plane stubs done in {time.time() - t_start:.1f}s, vias={len(vias)}')

# ---------------------------------------------------------------- 2. routed nets
def bbox_hp(pads):
    x = [mm(p.GetPosition().x) for p in pads]; y = [mm(p.GetPosition().y) for p in pads]
    return (max(x) - min(x)) + (max(y) - min(y))
order = [n for n in pads_by_net if netname[n] not in PLANE_NETS and len(pads_by_net[n]) > 1]
import os
PRIO = [x for x in os.environ.get('ROUTE_PRIORITY', '').split('|') if x]
order.sort(key=lambda n: (0 if netname[n] in POWER_NETS else 1, bbox_hp(pads_by_net[n])))
order.sort(key=lambda n: PRIO.index(netname[n]) if netname[n] in PRIO else len(PRIO))
routed = 0; failnets = set()
for net in order:
    name = netname[net]; pads = pads_by_net[net]
    # group pads that are already the same copper (e.g. duplicated pads) by footprint+number
    connected = [pads[0]]; todo = pads[1:]
    tree = set(pad_cells(pads[0], net))
    while todo:
        cx = sum(mm(p.GetPosition().x) for p in connected) / len(connected)
        cy = sum(mm(p.GetPosition().y) for p in connected) / len(connected)
        todo.sort(key=lambda p: math.hypot(mm(p.GetPosition().x) - cx, mm(p.GetPosition().y) - cy))
        tgt = todo.pop(0)
        tcells = pad_cells(tgt, net)
        if set(tcells) & tree: connected.append(tgt); tree |= set(tcells); continue
        ti, tj = cell(mm(tgt.GetPosition().x), mm(tgt.GetPosition().y))
        path = astar(net, name, list(tree), tcells, (ti, tj))
        if not path:
            fails.append(f'{name}: {tgt.GetParentFootprint().GetReference()}.{tgt.GetNumber()}'); failnets.add(name); continue
        commit_path(path, net, name)
        tree |= set(path) | set(tcells); connected.append(tgt); routed += 1
print(f'routed {routed} connections in {time.time() - t_start:.1f}s; tracks={len(tracks)} vias={len(vias)}')
if fails: print('FAILED:', *fails, sep='\n  ')
print('FAILNETS:' + '|'.join(sorted(failnets)))
print('NFAIL:', len(fails))

# ---------------------------------------------------------------- 3. GND pour on F.Cu / B.Cu, then fill all zones
for L in (P.F_Cu, P.B_Cu):
    z = P.ZONE(board); z.SetLayer(L); z.SetNet(board.FindNet('GND')); z.SetLocalClearance(iu(0.25))
    z.SetMinThickness(iu(0.2)); z.SetPadConnection(P.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(iu(0.3)); z.SetThermalReliefSpokeWidth(iu(0.4)); z.SetAssignedPriority(0)
    o = z.Outline(); o.NewOutline()
    for (px, py) in ((X0 + 0.3, Y0 + 0.3), (X1 - 0.3, Y0 + 0.3), (X1 - 0.3, Y1 - 0.3), (X0 + 0.3, Y1 - 0.3)):
        o.Append(iu(px), iu(py))
    board.Add(z)
P.ZONE_FILLER(board).Fill(board.Zones())
P.SaveBoard(DST, board)
print('saved', DST)
