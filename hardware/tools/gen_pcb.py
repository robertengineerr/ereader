"""Generate e_reader_v0.1.kicad_pcb from the schematic netlist: footprints, nets, placement, rules, planes.
Run with the system python that has pcbnew:  /usr/bin/python3 gen_pcb.py <netlist.xml> <out.kicad_pcb>
"""
import sys, math, xml.etree.ElementTree as ET
import pcbnew as P

NETLIST, OUT = sys.argv[1], sys.argv[2]
PROJ = '/home/user/ereader/hardware/e_reader_v0.1'
MM = P.FromMM
X0, Y0, W, H = 100.0, 100.0, 68.0, 50.0          # board outline (mm)
EDGE = 0.6                                         # keep courtyards this far inside the edge
GAP = 0.45                                         # min gap between courtyards

board = P.CreateEmptyBoard()
board.SetCopperLayerCount(4)
board.SetLayerType(P.In1_Cu, P.LT_POWER)
board.SetLayerType(P.In2_Cu, P.LT_POWER)

# ---------------------------------------------------------------- design rules (JLCPCB 4-layer safe)
ds = board.GetDesignSettings()
ds.m_TrackMinWidth = MM(0.15); ds.m_ViasMinSize = MM(0.6); ds.m_MinThroughDrill = MM(0.2)
ds.m_MinClearance = MM(0.15); ds.m_CopperEdgeClearance = MM(0.3); ds.m_HoleToHoleMin = MM(0.5)
ns = ds.m_NetSettings
dflt = ns.GetDefaultNetclass()
dflt.SetClearance(MM(0.15)); dflt.SetTrackWidth(MM(0.2)); dflt.SetViaDiameter(MM(0.6)); dflt.SetViaDrill(MM(0.3))
pwr = P.NETCLASS('Power')
pwr.SetClearance(MM(0.15)); pwr.SetTrackWidth(MM(0.3)); pwr.SetViaDiameter(MM(0.6)); pwr.SetViaDrill(MM(0.3))
ns.SetNetclass('Power', pwr)
POWER_NETS = ['GND', '+3V3', 'VBUS', 'VBAT', '/VBAT_RAW', '/VHI', 'Net-(Q4-D)']
for n in POWER_NETS: ns.SetNetclassPatternAssignment(n, 'Power')

# ---------------------------------------------------------------- netlist
root = ET.parse(NETLIST).getroot()
comps = {}
for c in root.find('components'):
    comps[c.get('ref')] = dict(value=c.findtext('value'), fp=c.findtext('footprint'),
                               uuid=(c.findtext('tstamps') or '').split()[0] if c.findtext('tstamps') else '',
                               fields={f.get('name'): (f.text or '') for f in c.find('fields') or []})
pinnet = {}
for n in root.find('nets'):
    for node in n: pinnet[(node.get('ref'), node.get('pin'))] = n.get('name')
nets = {}
def kname(name):
    # KiCad escapes '/' inside auto-generated net names (only sheet-path slashes stay literal)
    for pre in ('Net-(', 'unconnected-('):
        if name.startswith(pre): return pre + name[len(pre):].replace('/', '{slash}')
    return name
def net(name):
    name = kname(name)
    if name not in nets:
        ni = P.NETINFO_ITEM(board, name); board.Add(ni); nets[name] = ni
    return nets[name]

fps = {}
for ref, c in comps.items():
    lib, name = c['fp'].split(':')
    path = f'{PROJ}/ereader.pretty' if lib == 'ereader' else f'/usr/share/kicad/footprints/{lib}.pretty'
    m = P.FootprintLoad(path, name)
    m.SetFPID(P.LIB_ID(lib, name))
    m.SetReference(ref); m.SetValue(c['value'])
    if c['uuid']: m.SetPath(P.KIID_PATH('/' + c['uuid']))
    m.SetSheetname('/'); m.SetSheetfile('e_reader_v0.1.kicad_sch')
    for k in ('MPN', 'LCSC'):
        if c['fields'].get(k):
            m.SetField(k, c['fields'][k]); m.GetFieldByName(k).SetVisible(False)
    m.Value().SetVisible(False)
    for pad in m.Pads():
        nn = pinnet.get((ref, pad.GetNumber()))
        if nn: pad.SetNet(net(nn))
    board.Add(m); fps[ref] = m
    m.SetPosition(P.VECTOR2I(MM(-50), MM(-50)))   # parked until placed

# ---------------------------------------------------------------- board outline (rounded rectangle)
R = 2.0
def seg(a, b):
    s = P.PCB_SHAPE(board); s.SetShape(P.SHAPE_T_SEGMENT); s.SetLayer(P.Edge_Cuts); s.SetWidth(MM(0.1))
    s.SetStart(P.VECTOR2I(MM(a[0]), MM(a[1]))); s.SetEnd(P.VECTOR2I(MM(b[0]), MM(b[1]))); board.Add(s)
def arc(c, start, ang):
    s = P.PCB_SHAPE(board); s.SetShape(P.SHAPE_T_ARC); s.SetLayer(P.Edge_Cuts); s.SetWidth(MM(0.1))
    s.SetCenter(P.VECTOR2I(MM(c[0]), MM(c[1]))); s.SetStart(P.VECTOR2I(MM(start[0]), MM(start[1])))
    s.SetArcAngleAndEnd(P.EDA_ANGLE(ang, P.DEGREES_T)); board.Add(s)
x1, y1, x2, y2 = X0, Y0, X0 + W, Y0 + H
seg((x1 + R, y1), (x2 - R, y1)); seg((x2, y1 + R), (x2, y2 - R)); seg((x2 - R, y2), (x1 + R, y2)); seg((x1, y2 - R), (x1, y1 + R))
arc((x2 - R, y1 + R), (x2 - R, y1), 90); arc((x2 - R, y2 - R), (x2, y2 - R), 90)
arc((x1 + R, y2 - R), (x1 + R, y2), 90); arc((x1 + R, y1 + R), (x1, y1 + R), 90)

# ---------------------------------------------------------------- placement helpers
placed = []   # list of (x1,y1,x2,y2) obstacles in mm
def bbox_of(m):
    cy = m.GetCourtyard(P.F_CrtYd)
    b = cy.BBox() if cy.OutlineCount() else m.GetBoundingBox(False, False)
    return (P.ToMM(b.GetLeft()), P.ToMM(b.GetTop()), P.ToMM(b.GetRight()), P.ToMM(b.GetBottom()))
def collide(b, gap=GAP):
    for o in placed:
        if b[0] < o[2] + gap and b[2] > o[0] - gap and b[1] < o[3] + gap and b[3] > o[1] - gap: return True
    return False
def inside(b, allow_overhang=None):
    lo_x, lo_y, hi_x, hi_y = x1 + EDGE, y1 + EDGE, x2 - EDGE, y2 - EDGE
    if allow_overhang == 'top': lo_y = -1e9
    if allow_overhang == 'bottom': hi_y = 1e9
    if allow_overhang == 'left': lo_x = -1e9
    if allow_overhang == 'right': hi_x = 1e9
    return b[0] >= lo_x and b[1] >= lo_y and b[2] <= hi_x and b[3] <= hi_y
def put(ref, x, y, rot=0, overhang=None, force=False):
    m = fps[ref]; m.SetOrientationDegrees(rot); m.SetPosition(P.VECTOR2I(MM(x), MM(y)))
    b = bbox_of(m)
    if not force:
        assert inside(b, overhang), (ref, b)
        assert not collide(b), (ref, b)
    placed.append(b)
    return b
def try_put(ref, x, y, rot):
    m = fps[ref]; m.SetOrientationDegrees(rot); m.SetPosition(P.VECTOR2I(MM(x), MM(y)))
    b = bbox_of(m)
    return b if inside(b) and not collide(b) else None
def pack(ref, tx, ty, rots=(0, 90)):
    """place `ref` at the free grid spot nearest (tx, ty)."""
    best = None
    for r in range(0, 120):
        rr = r * 0.25
        pts = [(tx, ty)] if r == 0 else [(tx + rr * math.cos(a), ty + rr * math.sin(a))
                                          for a in [i * 2 * math.pi / max(8, int(rr * 6)) for i in range(max(8, int(rr * 6)))]]
        for (x, y) in pts:
            x, y = round(x / 0.25) * 0.25, round(y / 0.25) * 0.25
            for rot in rots:
                b = try_put(ref, x, y, rot)
                if b: best = (x, y, rot, b); break
            if best: break
        if best: break
    assert best, ref
    x, y, rot, b = best
    fps[ref].SetOrientationDegrees(rot); fps[ref].SetPosition(P.VECTOR2I(MM(x), MM(y)))
    placed.append(b)
def pad_xy(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == num: return P.ToMM(p.GetPosition().x), P.ToMM(p.GetPosition().y)
    raise KeyError((ref, num))
def near_net(ref, anchors):
    """target = centroid of the anchor pads (ref, pad) this part should sit next to."""
    pts = [pad_xy(r, n) for r, n in anchors]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

# ---------------------------------------------------------------- fixed placements
# ESP32 module: antenna against the top edge; its keep-out rule area overhangs the board.
put('U1', 113.5, 112.75, 0, force=True)
placed[-1] = (104.1, 100.0, 124.0, 126.8)          # obstacle = module body only (keep-out handled below)
placed.append((x1, y1, 139.5, 106.0))              # antenna keep-out band inside the board (from footprint zone)
put('J2', 155.0, 104.6, 0)
_p2 = pad_xy('U1', '2')
put('C10', 102.2, _p2[1] + 0.2, 90)                 # 100nF beside pin 2
put('C1', 102.4, _p2[1] + 3.4, 90)                  # 10uF just below it                         # display header, top-right
put('SW8', 163.4, 113.5, 90)                       # SET (right edge)
put('SW3', 162.6, 125.4, 0)                        # 5-way joystick (right edge)
put('SW9', 163.4, 137.3, 90)                       # RST (right edge)
put('X3', 134.0, 146.2, 0, overhang='bottom')      # USB-C, mouth on the bottom edge
put('SW10', 149.0, 147.0, 0, overhang='bottom')    # power slider on the bottom edge
put('X1', 120.5, 145.0, 0, overhang='bottom')      # battery JST
put('J1', 108.4, 142.2, 270, overhang='left')      # microSD, slot facing the left edge
HOLES = ((164.5, 146.5), (140.0, 112.0), (103.6, 130.2))
for hx, hy in HOLES: placed.append((hx - 3.0, hy - 3.0, hx + 3.0, hy + 3.0))

# power devices (packed near the intended spot)
pack('U3', 126.0, 133.0, rots=(0, 90))
pack('Q3', 133.5, 128.5, rots=(0, 90))
pack('D2', 140.5, 128.5, rots=(0, 90))
pack('U2', 140.0, 134.5, rots=(0, 90))
pack('Q4', 120.5, 136.5, rots=(0, 90))
pack('F1', 113.5, 133.0, rots=(90, 180))
pack('D1', 134.0, 139.6, rots=(0, 90))
pack('D3', 126.5, 140.0, rots=(0, 90))
pack('SW1', 128.0, 112.0, rots=(90, 180))
pack('SW2', 128.0, 120.5, rots=(90, 180))

# ---------------------------------------------------------------- passives packed next to what they serve
groups = [
    
    ('R6', [('U1', '3')]), ('C4', [('U1', '3')]),
    ('C21', [('X1', '2')]), ('C20', [('X1', '2')]), ('F1', [('X1', '2'), ('Q4', '3')]),
    ('C22', [('U3', '4')]), ('C19', [('U3', '3')]), ('C3', [('U3', '3')]), ('R4', [('U3', '5')]),
    ('CHG0', [('U3', '1')]), ('R3', [('U3', '1')]),
    ('R12', [('Q3', '1')]), ('C6', [('U2', '1')]), ('R7', [('U2', '3')]),
    ('C8', [('U2', '5')]), ('C2', [('U2', '5')]), ('C18', [('U2', '5')]),
    ('R5', [('X3', 'B5')]), ('R8', [('X3', 'A5')]),
    ('R17', [('U1', '39')]), ('R18', [('U1', '39')]), ('C23', [('U1', '39')]),
    ('C7', [('J1', '4')]), ('C17', [('J1', '4')]),
    ('R1', [('J1', '1')]), ('R2', [('J1', '8')]), ('R19', [('J1', '7')]), ('R20', [('J1', '2')]),
    ('R21', [('J1', '3')]), ('R22', [('J1', '9')]),
    ('C9', [('J2', '8')]),
    ('R14', [('SW3', '2')]), ('C14', [('SW3', '2')]),
    ('R9', [('SW3', '1')]), ('C5', [('SW3', '1')]), ('R13', [('SW3', '6')]), ('C13', [('SW3', '6')]),
    ('R10', [('SW3', '3')]), ('C11', [('SW3', '3')]), ('R11', [('SW3', '4')]), ('C12', [('SW3', '4')]),
    ('R15', [('SW8', '2')]), ('C15', [('SW8', '2')]), ('R16', [('SW9', '2')]), ('C16', [('SW9', '2')]),
]
for ref, anchors in groups:
    tx, ty = near_net(ref, anchors)
    pack(ref, tx, ty)
# test pads: along free space near the bottom/middle
for ref, (tx, ty) in zip(['TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'TP6'],
                         [(114, 128), (146, 129), (146, 136), (116, 129), (121, 128), (121, 124)]):
    pack(ref, tx, ty, rots=(0,))
missing = [r for r, m in fps.items() if P.ToMM(m.GetPosition().x) < 0]
assert not missing, missing

# ---------------------------------------------------------------- mounting holes (M2.5) in free corners
for i, (hx, hy) in enumerate(HOLES):
    mh = P.FootprintLoad('/usr/share/kicad/footprints/MountingHole.pretty', 'MountingHole_2.7mm_M2.5')
    mh.SetReference(f'H{i + 1}'); mh.SetPosition(P.VECTOR2I(MM(hx), MM(hy)))
    mh.SetAttributes(mh.GetAttributes() | P.FP_BOARD_ONLY | P.FP_EXCLUDE_FROM_BOM | P.FP_EXCLUDE_FROM_POS_FILES)
    board.Add(mh)

# ---------------------------------------------------------------- fiducials (3, for SMT assembly)
for i, (fx, fy) in enumerate(((143.0, 103.0), (103.0, 147.5), (166.0, 120.0))):
    fid = P.FootprintLoad('/usr/share/kicad/footprints/Fiducial.pretty', 'Fiducial_1mm_Mask2mm')
    fid.SetReference(f'FID{i + 1}'); fid.Reference().SetVisible(False); fid.Value().SetVisible(False)
    fid.SetAttributes(fid.GetAttributes() | P.FP_BOARD_ONLY | P.FP_EXCLUDE_FROM_BOM | P.FP_EXCLUDE_FROM_POS_FILES)
    board.Add(fid); fps[f'FID{i + 1}'] = fid
    pack(f'FID{i + 1}', fx, fy, rots=(0,))
tb = board.GetTitleBlock(); tb.SetTitle('EReader'); tb.SetRevision('0.2.0'); tb.SetDate('2026-11-05'); tb.SetCompany('robertengineer.com')

# ---------------------------------------------------------------- planes: In1 = GND, In2 = +3V3, top/bottom GND pour
def zone(layer, netname, prio=0):
    z = P.ZONE(board); z.SetLayer(layer); z.SetNet(net(netname)); z.SetAssignedPriority(prio)
    z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2))
    z.SetPadConnection(P.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    o = z.Outline(); o.NewOutline()
    for (px, py) in ((x1 + 0.3, y1 + 0.3), (x2 - 0.3, y1 + 0.3), (x2 - 0.3, y2 - 0.3), (x1 + 0.3, y2 - 0.3)):
        o.Append(MM(px), MM(py))
    board.Add(z); return z
zone(P.In1_Cu, 'GND'); zone(P.In2_Cu, '+3V3')

# ---------------------------------------------------------------- silkscreen: put each reference where it fits
def tb(t):
    b = t.GetBoundingBox(); return (P.ToMM(b.GetLeft()), P.ToMM(b.GetTop()), P.ToMM(b.GetRight()), P.ToMM(b.GetBottom()))
def ov(a, b, g=0.15): return a[0] < b[2] + g and a[2] > b[0] - g and a[1] < b[3] + g and a[3] > b[1] - g
pads = []
for m in fps.values():
    for pd in m.Pads():
        b = pd.GetBoundingBox(); pads.append((P.ToMM(b.GetLeft()), P.ToMM(b.GetTop()), P.ToMM(b.GetRight()), P.ToMM(b.GetBottom())))
texts, hidden = [], []
order = sorted(fps.values(), key=lambda m: -abs(bbox_of(m)[2] - bbox_of(m)[0]) * abs(bbox_of(m)[3] - bbox_of(m)[1]))
for m in order:
    if m.GetReference().startswith('FID'): continue
    t = m.Reference(); t.SetLayer(P.F_SilkS); t.SetTextSize(P.VECTOR2I(MM(0.8), MM(0.8))); t.SetTextThickness(MM(0.12))
    t.SetKeepUpright(True); t.SetTextAngleDegrees(0)
    cb = bbox_of(m); cx, cy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
    cands = [(cx, cb[1] - 0.7), (cx, cb[3] + 0.7), (cb[0] - 0.4 - 0.45 * len(m.GetReference()), cy), (cb[2] + 0.4 + 0.45 * len(m.GetReference()), cy)]
    ok = False
    for (tx, ty) in cands:
        t.SetPosition(P.VECTOR2I(MM(tx), MM(ty))); b = tb(t)
        if b[0] < x1 + 0.3 or b[2] > x2 - 0.3 or b[1] < y1 + 0.3 or b[3] > y2 - 0.3: continue
        if any(ov(b, p) for p in pads) or any(ov(b, o) for o in texts): continue
        if m.GetReference() != 'U1' and ov(b, (100.6, 100.0, 120.5, 126.8), 0): continue
        texts.append(b); ok = True; break
    if not ok: t.SetVisible(False); hidden.append(m.GetReference())
print('silk refs hidden (no room):', ' '.join(sorted(hidden)) or 'none')

P.SaveBoard(OUT, board)
print('placed', len(fps), 'footprints,', len(nets), 'nets')
