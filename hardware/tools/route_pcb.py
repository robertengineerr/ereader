"""Grid router for e_reader_v0.1.kicad_pcb (KiCad 9 pcbnew API + numpy).

Two signal layers (F.Cu / B.Cu); In1.Cu = GND plane, In2.Cu = +3V3 plane.
 1. GND / +3V3 SMD pads get a short stub to a via that drops into their plane.
 2. Every other net is routed with A* on a 0.1 mm grid (8 directions + vias), pad by pad as a tree.
 3. Rip-up and reroute: a connection that cannot be routed is searched again with other nets'
    copper allowed at a high cost; the nets it would cross are ripped up, the blocked net is
    routed first, then the ripped nets are rerouted. Repeats until everything routes or gives up.
KiCad's DRC is the judge of the result; this router only has to be good enough to pass it.

usage: /usr/bin/python3 route_pcb.py in.kicad_pcb out.kicad_pcb
"""
import sys, math, heapq, time, random
from collections import deque
import numpy as np
import pcbnew as P

SRC, DST = sys.argv[1], sys.argv[2]
G = 0.1                                   # grid pitch, mm
CLR = 0.15                                # copper clearance (all net classes)
W_SIG, W_PWR = 0.20, 0.30                 # track widths
VIA = (0.6, 0.3)                          # via (diameter, drill)
VIA_COST, BOTTOM_COST = 18.0, 1.15        # via cost (grid steps) / bottom-layer step multiplier
SOFT_COST = 40.0                          # cost to cross another net's copper in a blocker search
PLANE_NETS = {'GND', '+3V3'}
POWER_NETS = {'GND', '+3V3', 'VBUS', 'VBAT', '/VBAT_RAW', '/VHI', 'Net-(Q4-D)'}
MARG = 0.05                               # safety margin for grid discretisation
HOLE_CLR, HOLE2HOLE = 0.25, 0.5           # copper-to-hole and drill-to-drill rules
BASE = W_SIG / 2 + CLR + MARG             # every copper item is inflated by this
MAX_RIPUP_ROUNDS = 40

board = P.LoadBoard(SRC)
mm = P.ToMM
def iu(v): return P.FromMM(float(v))
bb = board.GetBoardEdgesBoundingBox()
X0, Y0, X1, Y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
NX, NY = int(round((X1 - X0) / G)) + 1, int(round((Y1 - Y0) / G)) + 1
LAYERS = [P.F_Cu, P.B_Cu]
xs = X0 + np.arange(NX) * G
ys = Y0 + np.arange(NY) * G
YY, XX = np.meshgrid(ys, xs, indexing='ij')

own = np.zeros((2, NY, NX), np.int32)     # 0 free, >0 net owning the inflated copper, -1 blocked for all
core = np.zeros((2, NY, NX), np.int32)    # net code of real copper
padcore = np.zeros((NY, NX), bool)        # pad copper on any layer (no vias here)
viablock = np.zeros((NY, NX), bool)       # too close to an existing drill

def cell(x, y): return int(round((y - Y0) / G)), int(round((x - X0) / G))
def window(xa, ya, xb, yb):
    i0, j0 = cell(xa, ya); i1, j1 = cell(xb, yb)
    return max(i0, 0), min(i1, NY - 1) + 1, max(j0, 0), min(j1, NX - 1) + 1

def claim(l, win, ring, cor, net, record=None):
    """ring/cor are window-sized masks. Ring cells become owned by net (conflicts -> -1)."""
    i0, i1, j0, j1 = win
    o = own[l, i0:i1, j0:j1]
    free = ring & ((o == 0) | (o == net))
    o[ring & ~free] = -1
    o[free] = net if net > 0 else -1
    if net > 0:
        o[cor] = net; core[l, i0:i1, j0:j1][cor] = net
    else:
        o[cor] = -1
    if record is not None:
        a, b = np.nonzero(ring | cor)
        record.update(zip([l] * len(a), ((a + i0) * NX + (b + j0)).tolist()))

# ---------------------------------------------------------------- static obstacles
m = 0.3 + BASE
edge = (XX < X0 + m) | (XX > X1 - m) | (YY < Y0 + m) | (YY > Y1 - m)
RC = 2.0
for cx, cy in ((X0 + RC, Y0 + RC), (X1 - RC, Y0 + RC), (X0 + RC, Y1 - RC), (X1 - RC, Y1 - RC)):
    sx = 1 if cx > (X0 + X1) / 2 else -1; sy = 1 if cy > (Y0 + Y1) / 2 else -1
    edge |= ((XX - cx) * sx > 0) & ((YY - cy) * sy > 0) & (np.hypot(XX - cx, YY - cy) > RC - m)
keep = np.zeros((NY, NX), bool)
for fp in board.GetFootprints():
    for z in fp.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
            zb = z.GetBoundingBox()
            i0, i1, j0, j1 = window(mm(zb.GetLeft()) - BASE, mm(zb.GetTop()) - BASE, mm(zb.GetRight()) + BASE, mm(zb.GetBottom()) + BASE)
            keep[i0:i1, j0:j1] = True
for l in (0, 1): own[l][edge | keep] = -1

pads_by_net = {}
for fp in board.GetFootprints():
    for pad in fp.Pads():
        net = pad.GetNetCode(); npth = pad.GetAttribute() == P.PAD_ATTRIB_NPTH
        r = W_PWR / 2 + HOLE_CLR + MARG if npth else BASE
        pb = pad.GetBoundingBox()
        win = window(mm(pb.GetLeft()) - r - G, mm(pb.GetTop()) - r - G, mm(pb.GetRight()) + r + G, mm(pb.GetBottom()) + r + G)
        i0, i1, j0, j1 = win
        for li, L in enumerate(LAYERS):
            if not pad.IsOnLayer(L) and not pad.HasHole(): continue
            shape = pad.GetEffectiveShape(L)
            ring = np.zeros((i1 - i0, j1 - j0), bool); cor = np.zeros_like(ring)
            for a in range(i0, i1):
                for b in range(j0, j1):
                    pt = P.VECTOR2I(iu(xs[b]), iu(ys[a]))
                    if shape.Collide(pt, 0): cor[a - i0, b - j0] = True
                    elif shape.Collide(pt, iu(r)): ring[a - i0, b - j0] = True
            claim(li, win, ring | cor, cor, -1 if npth else net)
            padcore[i0:i1, j0:j1] |= cor
        if pad.HasHole():
            hx, hy = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
            rr = mm(max(pad.GetDrillSize().x, pad.GetDrillSize().y)) / 2 + VIA[1] / 2 + HOLE2HOLE + G
            a0, a1, b0, b1 = window(hx - rr, hy - rr, hx + rr, hy + rr)
            viablock[a0:a1, b0:b1] |= np.hypot(XX[a0:a1, b0:b1] - hx, YY[a0:a1, b0:b1] - hy) <= rr
        if net > 0 and not npth:
            pads_by_net.setdefault(net, []).append(pad)
netname = {n: board.FindNet(n).GetNetname() for n in pads_by_net}

# ---------------------------------------------------------------- geometry helpers
def disk(r):
    k = int(math.ceil(r / G))
    return [(dy, dx) for dy in range(-k, k + 1) for dx in range(-k, k + 1) if math.hypot(dy, dx) * G <= r + 1e-9]
def erode(mask, r):
    if r <= 1e-9: return mask.copy()
    out = mask.copy(); k = int(math.ceil(r / G))
    p = np.pad(mask, k, constant_values=False)
    for dy, dx in disk(r):
        out &= p[k + dy:k + dy + mask.shape[0], k + dx:k + dx + mask.shape[1]]
    return out
def dilate(mask, r): return ~erode(~mask, r)
PAD_NOVIA = dilate(padcore, VIA[0] / 2 + 0.1)

def mark_track(li, a, b, halfw, net, record=None):
    (xa, ya), (xb, yb) = a, b
    r = halfw + CLR + W_SIG / 2 + MARG
    win = window(min(xa, xb) - r - G, min(ya, yb) - r - G, max(xa, xb) + r + G, max(ya, yb) + r + G)
    i0, i1, j0, j1 = win
    X = XX[i0:i1, j0:j1]; Y = YY[i0:i1, j0:j1]
    dx, dy = xb - xa, yb - ya; L2 = dx * dx + dy * dy
    t = np.clip(((X - xa) * dx + (Y - ya) * dy) / L2, 0, 1) if L2 > 0 else np.zeros_like(X)
    d = np.hypot(X - (xa + t * dx), Y - (ya + t * dy))
    claim(li, win, d <= r, d <= max(halfw, G * 0.75), net, record)
def mark_via(x, y, net, record=None):
    for li in (0, 1): mark_track(li, (x, y), (x, y), VIA[0] / 2, net, record)
    rr = VIA[1] + HOLE2HOLE + G
    i0, i1, j0, j1 = window(x - rr, y - rr, x + rr, y + rr)
    viablock[i0:i1, j0:j1] |= np.hypot(XX[i0:i1, j0:j1] - x, YY[i0:i1, j0:j1] - y) <= rr

def width_of(name): return W_PWR if name in POWER_NETS else W_SIG

# routed copper: net -> list of items ('t', li, a, b, w) / ('v', x, y);  netcells: net -> set of (l, flat idx)
routes, netcells = {}, {}
def mark_item(net, it):
    rec = netcells.setdefault(net, set())
    if it[0] == 't': mark_track(it[1], it[2], it[3], it[4] / 2, net, rec)
    else: mark_via(it[1], it[2], net, rec)

def path_items(path, name):
    w = width_of(name); pts = [(l, float(xs[j]), float(ys[i])) for (l, i, j) in path]
    items, runs, cur = [], [], [pts[0]]
    for p in pts[1:]:
        if p[0] != cur[-1][0]: runs.append(cur); items.append(('v', p[1], p[2])); cur = [p]
        else: cur.append(p)
    runs.append(cur)
    for run in runs:
        simp = [run[0]]
        for k in range(1, len(run) - 1):
            a, b, c = simp[-1], run[k], run[k + 1]
            if (b[1] - a[1]) * (c[2] - b[2]) - (b[2] - a[2]) * (c[1] - b[1]) != 0: simp.append(b)
        if len(run) > 1: simp.append(run[-1])
        for a, b in zip(simp, simp[1:]): items.append(('t', run[0][0], (a[1], a[2]), (b[1], b[2]), w))
    return items

def pad_cells(pad, net):
    cells = []; pb = pad.GetBoundingBox()
    i0, i1, j0, j1 = window(mm(pb.GetLeft()), mm(pb.GetTop()), mm(pb.GetRight()), mm(pb.GetBottom()))
    for li, L in enumerate(LAYERS):
        if not pad.IsOnLayer(L): continue
        a, b = np.nonzero(core[li, i0:i1, j0:j1] == net)
        cells += [(li, x + i0, y + j0) for x, y in zip(a, b)]
    return cells

# ---------------------------------------------------------------- A*
SQ2 = math.sqrt(2)
NB = [(0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0), (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2), (-1, -1, SQ2)]
def masks(net, name, soft):
    w = width_of(name)
    src = base_own if soft else own
    ok0 = (src[0] == 0) | (src[0] == net); ok1 = (src[1] == 0) | (src[1] == net)
    extra = (w / 2 + CLR) - (W_SIG / 2 + CLR + MARG)
    if extra > 0: extra += G
    t0, t1 = erode(ok0, extra), erode(ok1, extra)
    vr = VIA[0] / 2 - W_SIG / 2 + G
    v = erode(ok0, vr) & erode(ok1, vr) & ~PAD_NOVIA & ~keep & ~(base_viablock if soft else viablock)
    pen = None
    if soft:   # cells where today's copper of another net sits cost extra
        pen = [((own[l] != 0) & (own[l] != net)).ravel().tolist() for l in (0, 1)]
    return [t0.ravel().tolist(), t1.ravel().tolist()], v.ravel().tolist(), pen

def astar(net, name, sources, targets, tgt, soft=False, maxexp=4_000_000):
    T, V, PEN = masks(net, name, soft)
    tset = set(targets); ty, tx = tgt
    def h(i, j): return math.hypot(i - ty, j - tx)
    openh, g, came = [], {}, {}
    for s in sources:
        g[s] = 0.0; came[s] = None; heapq.heappush(openh, (h(s[1], s[2]), 0.0, s))
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
        l, i, j = s; mult = BOTTOM_COST if l else 1.0; Tl = T[l]
        for di, dj, c in NB:
            a, b = i + di, j + dj
            if a < 0 or b < 0 or a >= NY or b >= NX: continue
            idx = a * NX + b
            if not Tl[idx]: continue
            if di and dj and (not Tl[i * NX + b] or not Tl[a * NX + j]): continue
            ng = gc + c * mult + (SOFT_COST if PEN and PEN[l][idx] else 0.0)
            ns = (l, a, b)
            if ng < g.get(ns, 1e18): g[ns] = ng; came[ns] = s; heapq.heappush(openh, (ng + h(a, b), ng, ns))
        idx = i * NX + j
        if V[idx] and T[1 - l][idx]:
            ns = (1 - l, i, j); ng = gc + VIA_COST + (SOFT_COST if PEN and PEN[1 - l][idx] else 0.0)
            if ng < g.get(ns, 1e18): g[ns] = ng; came[ns] = s; heapq.heappush(openh, (ng + h(i, j), ng, ns))
    return None

# ---------------------------------------------------------------- 1. plane stubs (fixed, part of the base)
t_start = time.time(); stub_items = []; stub_fail = []
for net, pads in pads_by_net.items():
    name = netname[net]
    if name not in PLANE_NETS: continue
    for pad in pads:
        if pad.HasHole() or not pad.IsOnLayer(P.F_Cu): continue
        (t0, _), V, _ = masks(net, name, False)
        V = np.array(V, bool).reshape(NY, NX); t0 = np.array(t0, bool).reshape(NY, NX)
        src = [(c[1], c[2]) for c in pad_cells(pad, net) if c[0] == 0]
        if not src: continue
        q = deque(src); seen = {s: None for s in src}; hit = None
        while q:
            i, j = q.popleft()
            if V[i, j]: hit = (i, j); break
            for di, dj, _ in NB:
                a, b = i + di, j + dj
                if 0 <= a < NY and 0 <= b < NX and (a, b) not in seen and t0[a, b] and len(seen) < 40000:
                    seen[(a, b)] = (i, j); q.append((a, b))
        if not hit: stub_fail.append(f'{name}:{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}'); continue
        path = []; c = hit
        while c is not None: path.append((0, c[0], c[1])); c = seen[c]
        items = (path_items(path[::-1], name) if len(path) > 1 else []) + [('v', float(xs[hit[1]]), float(ys[hit[0]]))]
        for it in items: mark_item(net, it)
        stub_items += [(net, it) for it in items]
base_own, base_core, base_viablock = own.copy(), core.copy(), viablock.copy()
netcells.clear()
print(f'plane stubs: {len(stub_items)} items in {time.time() - t_start:.1f}s; failed: {stub_fail or "none"}')

def rebuild():
    global own, core, viablock
    own, core, viablock = base_own.copy(), base_core.copy(), base_viablock.copy()
    netcells.clear()
    for net, items in routes.items():
        for it in items: mark_item(net, it)

# ---------------------------------------------------------------- 2. net routing
def route_net(net):
    """route all pads of net as a tree; returns list of unconnected pads."""
    name = netname[net]; pads = pads_by_net[net]
    items = []; connected = [pads[0]]; todo = pads[1:]; failed = []
    tree = set(pad_cells(pads[0], net))
    while todo:
        cx = sum(mm(p.GetPosition().x) for p in connected) / len(connected)
        cy = sum(mm(p.GetPosition().y) for p in connected) / len(connected)
        todo.sort(key=lambda p: math.hypot(mm(p.GetPosition().x) - cx, mm(p.GetPosition().y) - cy))
        tgt = todo.pop(0); tcells = pad_cells(tgt, net)
        if set(tcells) & tree: connected.append(tgt); tree |= set(tcells); continue
        path = astar(net, name, list(tree), tcells, cell(mm(tgt.GetPosition().x), mm(tgt.GetPosition().y)))
        if not path: failed.append(tgt); continue
        new = path_items(path, name)
        for it in new: mark_item(net, it)
        items += new; tree |= set(path) | set(tcells); connected.append(tgt)
    routes[net] = items
    return failed

def blockers_for(net, pad):
    """nets whose copper a soft-cost path from the net's tree to `pad` would cross."""
    name = netname[net]
    tree = set()
    for p in pads_by_net[net]:
        if p is not pad: tree |= set(pad_cells(p, net))
    for it in routes.get(net, []):
        pass
    tree |= {(l, i // NX, i % NX) for (l, i) in netcells.get(net, set()) if core[l].ravel()[i] == net}
    path = astar(net, name, list(tree), pad_cells(pad, net), cell(mm(pad.GetPosition().x), mm(pad.GetPosition().y)), soft=True)
    if not path: return None
    hit = set()
    cells = {(l, i * NX + j) for (l, i, j) in path}
    for k in range(len(path) - 1):
        if path[k][0] != path[k + 1][0]: cells |= {(0, path[k][1] * NX + path[k][2]), (1, path[k][1] * NX + path[k][2])}
    for n, cs in netcells.items():
        if n != net and cs & cells: hit.add(n)
    return hit

def bbox_hp(pads):
    x = [mm(p.GetPosition().x) for p in pads]; y = [mm(p.GetPosition().y) for p in pads]
    return (max(x) - min(x)) + (max(y) - min(y))
order = [n for n in pads_by_net if netname[n] not in PLANE_NETS and len(pads_by_net[n]) > 1]
order.sort(key=lambda n: (0 if netname[n] in POWER_NETS else 1, bbox_hp(pads_by_net[n])))
fails = {}
for net in order:
    f = route_net(net)
    if f: fails[net] = f
print(f'first pass: {sum(len(v) for v in fails.values())} unrouted pads on {len(fails)} nets ({time.time() - t_start:.0f}s)')

# ---------------------------------------------------------------- 3. rip-up and reroute
random.seed(1); history = {}
for rnd in range(MAX_RIPUP_ROUNDS):
    if not fails: break
    net = min(fails, key=lambda n: history.get(n, 0)); pad = fails[net][0]
    history[net] = history.get(net, 0) + 1
    bl = blockers_for(net, pad)
    if bl is None:
        print(f'  round {rnd}: {netname[net]} has no path even through other copper'); fails.pop(net); continue
    victims = sorted(bl, key=lambda n: random.random())
    for v in victims: routes.pop(v, None)
    routes.pop(net, None)
    rebuild()
    queue = [net] + victims
    fails.pop(net, None)
    for v in victims: fails.pop(v, None)
    for n in queue:
        f = route_net(n)
        if f: fails[n] = f
    left = sum(len(v) for v in fails.values())
    print(f'  round {rnd}: {netname[net]} ripped {len(victims)} ({", ".join(netname[v] for v in victims)}) -> {left} unrouted')
print(f'rip-up done ({time.time() - t_start:.0f}s)')
nfail = sum(len(v) for v in fails.values())
for n, pl in fails.items():
    for p in pl: print(f'  UNROUTED {netname[n]}: {p.GetParentFootprint().GetReference()}.{p.GetNumber()}')
print('NFAIL:', nfail)

# ---------------------------------------------------------------- 4. write copper + GND pours, fill zones
ntr = nvia = 0
for net, it in stub_items + [(n, it) for n, items in routes.items() for it in items]:
    if it[0] == 't':
        t = P.PCB_TRACK(board); t.SetLayer(LAYERS[it[1]]); t.SetWidth(iu(it[4])); t.SetNetCode(net)
        t.SetStart(P.VECTOR2I(iu(it[2][0]), iu(it[2][1]))); t.SetEnd(P.VECTOR2I(iu(it[3][0]), iu(it[3][1]))); board.Add(t); ntr += 1
    else:
        v = P.PCB_VIA(board); v.SetPosition(P.VECTOR2I(iu(it[1]), iu(it[2]))); v.SetWidth(iu(VIA[0])); v.SetDrill(iu(VIA[1]))
        v.SetViaType(P.VIATYPE_THROUGH); v.SetLayerPair(P.F_Cu, P.B_Cu); v.SetNetCode(net); board.Add(v); nvia += 1
for L in (P.F_Cu, P.B_Cu):
    z = P.ZONE(board); z.SetLayer(L); z.SetNet(board.FindNet('GND')); z.SetLocalClearance(iu(0.25))
    z.SetMinThickness(iu(0.2)); z.SetPadConnection(P.ZONE_CONNECTION_FULL); z.SetAssignedPriority(0)
    o = z.Outline(); o.NewOutline()
    for (px, py) in ((X0 + 0.3, Y0 + 0.3), (X1 - 0.3, Y0 + 0.3), (X1 - 0.3, Y1 - 0.3), (X0 + 0.3, Y1 - 0.3)):
        o.Append(iu(px), iu(py))
    board.Add(z)
P.ZONE_FILLER(board).Fill(board.Zones())
P.SaveBoard(DST, board)
print(f'saved {DST}: {ntr} tracks, {nvia} vias ({time.time() - t_start:.0f}s)')
