"""E-reader enclosure (v0.1 fit prototype) - CadQuery.  All dimensions in mm.

Layout (front view, portrait): Waveshare 7.5" panel on the left, the PCB in a strip on the right, rotated 90 deg
so that the joystick + SET/RST buttons are a row at the top of the PCB, USB-C and the power slider sit in a recess
in the right side wall, and the microSD slot faces the bottom wall.

Parts written to this folder (STEP for Onshape, STL for the slicer):
  back_shell, front_cover, j2_hood, joystick_cap, button_plunger (print 2)
  ereader_assembly.step = everything plus mock-ups of the PCB, display and battery (for viewing only)

Run:  python enclosure.py            (needs cadquery; reads board_positions.json exported from the KiCad board)
"""
import json, os
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
POS = json.load(open(os.path.join(HERE, 'board_positions.json')))

# ----------------------------------------------------------------------------- parameters (edit me)
WALL, FLOOR = 2.0, 2.0
COVER_T = 2.4                       # front cover thickness
DISP_W, DISP_H, DISP_T = 111.2, 170.2, 1.2      # Waveshare 7.5" V2 raw panel outline (portrait)
DISP_CLR = 0.3                      # gap around the panel
AA_W, AA_H = 97.92, 163.2           # active area
AA_LEFT, AA_BOTTOM = 3.6, 3.5       # panel edge -> active area (left / bottom); VERIFY against your panel
WIN_MARGIN = 0.5                    # window is this much larger than the active area on each side
PCB_GAP = 1.5                       # between panel edge and PCB edge
PCB_T = 1.6
PCB_TOP_CLR = 6.5                   # PCB top -> underside of the cover (tallest part: battery JST ~6 mm)
PLUG_ZONE = 7.5                     # room beside the PCB for the battery plug (right side)
H_INNER = 13.0                      # floor -> underside of cover (HAT with 40-pin header needs ~12)
JOY_STEM_H, JOY_STEM_D, JOY_BODY_H = 5.0, 3.2, 1.85   # Alps SKRHABE010 above the PCB; VERIFY stem size
BTN_H = 1.9                         # KMR2 height above the PCB
SCREW_PILOT, SCREW_CLEAR = 2.1, 2.9  # M2.5 self-tapping into plastic / clearance
DUPONT_H = 16.5                     # top of the display jumper housings above the PCB when plugged on J2

# ----------------------------------------------------------------------------- derived layout
Z_COVER = FLOOR + H_INNER                 # underside of the cover (= top of the walls)
Z_TOP = Z_COVER + COVER_T                 # front surface
Z_PCB_TOP = Z_COVER - PCB_TOP_CLR
Z_PCB_BOT = Z_PCB_TOP - PCB_T
DX0, DY0 = WALL + DISP_CLR, WALL + DISP_CLR                       # panel lower-left corner
POCK_X1, POCK_Y1 = WALL + DISP_W + 2 * DISP_CLR, WALL + DISP_H + 2 * DISP_CLR
BX0, BY0, BX1, BY1 = POS['_board']
PCB_W, PCB_L = BY1 - BY0, BX1 - BX0       # in the case the board is rotated: 50.1 wide, 68.1 tall
PX0 = POCK_X1 + PCB_GAP                   # case X of the board's top edge (antenna side, next to the panel)
PY0 = WALL + 0.4                          # case Y of the board's left edge (microSD side, at the bottom wall)
PX1, PY1 = PX0 + PCB_W, PY0 + PCB_L
W = PX1 + PLUG_ZONE + WALL                # outer width
H = POCK_Y1 + WALL                        # outer height

def bx(x, y): return PX0 + (y - BY0), PY0 + (x - BX0)            # board (x, y) -> case (X, Y)
def bbox(ref):
    l, t, r, b = POS[ref]['box']; (xa, ya), (xb, yb) = bx(l, t), bx(r, b)
    return min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)
def at(ref): return bx(POS[ref]['x'], POS[ref]['y'])

USB_X, USB_Y = at('X3'); SLD_X, SLD_Y = at('SW10'); SD_X, SD_Y = at('J1')
NOTCH_Y0 = min(USB_Y - 6.5, SLD_Y - 6.5)          # recess in the right wall for USB-C + power slider
NOTCH_Y1 = max(USB_Y + 6.5, SLD_Y + 6.5) + 1.0
NOTCH_X = PX1 + 0.4 + WALL                        # outer face of the recessed wall
OUTLINE = [(0, 0), (W, 0), (W, NOTCH_Y0 - WALL), (NOTCH_X, NOTCH_Y0 - WALL), (NOTCH_X, NOTCH_Y1 + WALL),
           (W, NOTCH_Y1 + WALL), (W, H), (0, H)]

def box(x0, y0, z0, x1, y1, z1): return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))
def cyl(x, y, z0, z1, d): return cq.Workplane('XY').circle(d / 2).extrude(z1 - z0).translate((x, y, z0))
def prism(z0, z1, inset=0.0):
    w = cq.Workplane('XY').polyline(OUTLINE).close()
    if inset: w = w.offset2D(-inset)
    return w.extrude(z1 - z0).translate((0, 0, z0))
def rounded(solid):
    try: return solid.edges('|Z').fillet(1.5)
    except Exception: return solid

BOSSES = [(W - WALL - 3.5, 7.0), (W - WALL - 3.5, NOTCH_Y1 + WALL + 5.5), (W - WALL - 3.5, H - 6.0),
          (PX0 + 3.7, H - 6.0), (W - WALL - 3.5, 115.0), (PX0 + 3.7, 115.0)]
SNAPS_Y = [25.0, H / 2, H - 25.0]                 # snap tabs along the left wall
BAT = (PX0 + 8.0, PY1 + 9.0, PX0 + 8.0 + 42.0, PY1 + 9.0 + 69.0)       # battery pocket (fits ~40 x 65 x 8)

# ----------------------------------------------------------------------------- back shell
def back_shell():
    s = rounded(prism(0, Z_COVER)).cut(prism(FLOOR, Z_COVER + 1, WALL))
    for ref in ('H1', 'H2', 'H3'):                                       # PCB standoffs
        x, y = at(ref)
        s = s.union(cyl(x, y, FLOOR, Z_PCB_BOT, 6.5)).cut(cyl(x, y, FLOOR + 0.6, Z_PCB_BOT + 1, SCREW_PILOT))
    for x, y in BOSSES:                                                  # cover screw bosses
        s = s.union(cyl(x, y, FLOOR, Z_COVER, 6.4)).cut(cyl(x, y, FLOOR + 3, Z_COVER + 1, SCREW_PILOT))
    for x, y in ((9, 9), (9, H - 9), (POCK_X1 - 9, H - 9), (POCK_X1 - 9, 9), (9, H / 2)):   # panel rests on these (+1 mm foam)
        s = s.union(box(x - 3, y - 3, FLOOR, x + 3, y + 3, Z_COVER - 1.0))
    x0, y0, x1, y1 = BAT                                                 # battery corner ribs
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        s = s.union(box(min(cx, cx + sx * 10), min(cy, cy + sy * 1.2), FLOOR, max(cx, cx + sx * 10), max(cy, cy + sy * 1.2), FLOOR + 5))
        s = s.union(box(min(cx, cx + sx * 1.2), min(cy, cy + sy * 10), FLOOR, max(cx, cx + sx * 1.2), max(cy, cy + sy * 10), FLOOR + 5))
    zc = Z_PCB_TOP + 1.65                                                # USB-C centre height
    s = s.cut(box(NOTCH_X - WALL - 1, USB_Y - 6.6, zc - 3.6, NOTCH_X + 1, USB_Y + 6.6, zc + 3.6))      # USB-C plug opening
    s = s.cut(box(NOTCH_X - WALL - 1, SLD_Y - 5.0, Z_PCB_TOP - 0.4, NOTCH_X + 1, SLD_Y + 5.0, Z_PCB_TOP + 3.2))  # power slider
    s = s.cut(box(SD_X - 8.0, -1, Z_PCB_TOP - 1.2, SD_X + 8.0, WALL + 1, Z_PCB_TOP + 3.6))             # microSD window
    for y in SNAPS_Y:                                                    # snap ridges on the outside of the left wall
        r = cq.Workplane('XZ').polyline([(0, 11.0), (-0.45, 10.55), (-0.45, 9.5), (0, 9.5)]).close().extrude(7, both=True)
        s = s.union(r.translate((0, y, 0)))
    return s

# ----------------------------------------------------------------------------- front cover
J2B = bbox('J2')
HOOD_OPEN = (J2B[0] - 1.4, J2B[1] - 8.5, J2B[2] + 1.4, J2B[3] + 1.4)    # J2 + a channel for the wires to come back down
def front_cover():
    c = rounded(prism(Z_COVER, Z_TOP))
    c = c.cut(box(WALL, WALL, Z_COVER - 1, POCK_X1, POCK_Y1, Z_COVER + DISP_T + 0.05))              # panel pocket
    wx, wy = DX0 + AA_LEFT - WIN_MARGIN, DY0 + AA_BOTTOM - WIN_MARGIN
    c = c.cut(box(wx, wy, Z_COVER - 1, wx + AA_W + 2 * WIN_MARGIN, wy + AA_H + 2 * WIN_MARGIN, Z_TOP + 1))   # window
    x, y = at('SW3'); c = c.cut(cyl(x, y, Z_COVER - 1, Z_TOP + 1, 8.8))                             # joystick cap
    for ref in ('SW8', 'SW9'):
        x, y = at(ref); c = c.cut(cyl(x, y, Z_COVER - 1, Z_TOP + 1, 4.4))                           # SET / RST plungers
    for ref in ('SW1', 'SW2'):
        x, y = at(ref); c = c.cut(cyl(x, y, Z_COVER - 1, Z_TOP + 1, 2.6))                           # BOOT / RESET pinholes
    x, y = at('CHG0'); c = c.cut(cyl(x, y, Z_COVER - 1, Z_TOP + 1, 2.0))                            # charge LED
    for x, y in BOSSES: c = c.cut(cyl(x, y, Z_COVER - 1, Z_TOP + 1, SCREW_CLEAR))
    x0, y0, x1, y1 = HOOD_OPEN; c = c.cut(box(x0, y0, Z_COVER - 1, x1, y1, Z_TOP + 1))              # J2 connector opening
    for y in SNAPS_Y:                                                                              # snap tabs (left edge)
        c = c.union(box(-1.5, y - 8, Z_COVER, 0.5, y + 8, Z_TOP))
        c = c.union(box(-1.5, y - 8, 8.4, -0.15, y + 8, Z_COVER)).cut(box(-2, y - 7.3, 9.4, 0, y + 7.3, 11.3))
    return c

def j2_hood():
    x0, y0, x1, y1 = HOOD_OPEN; t = 1.2
    top = Z_PCB_TOP + DUPONT_H + 4.0                                     # inner ceiling: plugs + wire bend
    h = box(x0 - t, y0 - t, Z_TOP, x1 + t, y1 + t, top + t).cut(box(x0, y0, Z_TOP - 1, x1, y1, top))
    lip = box(x0 + 0.2, y0 + 0.2, Z_TOP - 2.0, x1 - 0.2, y1 - 0.2, Z_TOP).cut(box(x0 + 1.2, y0 + 1.2, Z_TOP - 3, x1 - 1.2, y1 - 1.2, Z_TOP + 1))
    return h.union(lip)

def joystick_cap():
    x, y = at('SW3'); zb = Z_PCB_TOP + JOY_BODY_H + 0.9; zs = Z_PCB_TOP + JOY_STEM_H
    c = cyl(x, y, zb, Z_COVER - 1.4, 6.0).union(cyl(x, y, Z_COVER - 1.4, Z_COVER - 0.4, 12.0)).union(cyl(x, y, Z_COVER - 0.4, Z_TOP + 1.6, 8.0))
    try: c = c.faces('>Z').edges().fillet(0.8)
    except Exception: pass
    return c.cut(cyl(x, y, zb - 1, zs, JOY_STEM_D + 0.4))               # socket sits on top of the stem

def button_plunger(ref):
    x, y = at(ref); zb = Z_PCB_TOP + BTN_H + 0.1
    return cyl(x, y, zb, Z_TOP + 1.0, 3.8).union(cyl(x, y, Z_COVER - 1.4, Z_COVER - 0.4, 6.5))

# ----------------------------------------------------------------------------- mock-ups (viewing / clash check only)
HEIGHTS = {'X3': 3.3, 'X1': 6.0, 'J1': 1.6, 'J2': 8.5, 'SW3': JOY_BODY_H, 'SW10': 1.4, 'D2': 2.4, 'D3': 2.4}
def pcb_mock():
    p = box(PX0, PY0, Z_PCB_BOT, PX1, PY1, Z_PCB_TOP)
    for ref in ('H1', 'H2', 'H3'):
        x, y = at(ref); p = p.cut(cyl(x, y, Z_PCB_BOT - 1, Z_PCB_TOP + 1, 2.7))
    parts = box(*bx(104.5, 100.0), Z_PCB_TOP, *bx(122.5, 125.5), Z_PCB_TOP + 3.2)                   # ESP32 module body
    for ref, v in POS.items():
        if ref[0] == '_' or ref in ('U1',) or ref[:1] == 'H' or ref[:2] in ('TP', 'FI'): continue
        h = HEIGHTS.get(ref, BTN_H if ref in ('SW1', 'SW2', 'SW8', 'SW9') else 1.2)
        x0, y0, x1, y1 = bbox(ref)
        parts = parts.union(box(x0 + 0.25, y0 + 0.25, Z_PCB_TOP, x1 - 0.25, y1 - 0.25, Z_PCB_TOP + h))
    x, y = at('SW3'); parts = parts.union(cyl(x, y, Z_PCB_TOP, Z_PCB_TOP + JOY_STEM_H, JOY_STEM_D))
    return p, parts
def dupont_mock():
    x0, y0, x1, y1 = bbox('J2'); xc = (x0 + x1) / 2
    return box(xc - 1.3, y0 + 0.6, Z_PCB_TOP + 2.5, xc + 1.3, y1 - 0.6, Z_PCB_TOP + DUPONT_H)

if __name__ == '__main__':
    parts = {'back_shell': back_shell(), 'front_cover': front_cover(), 'j2_hood': j2_hood(), 'joystick_cap': joystick_cap(),
             'button_plunger': button_plunger('SW8')}
    plunger2 = button_plunger('SW9')
    board, comps = pcb_mock()
    display = box(DX0, DY0, Z_COVER + 0.05, DX0 + DISP_W, DY0 + DISP_H, Z_COVER + 0.05 + DISP_T)
    battery = box(BAT[0] + 1.5, BAT[1] + 2, FLOOR, BAT[0] + 40.5, BAT[1] + 67, FLOOR + 8)
    dupont = dupont_mock()
    for name, p in parts.items():
        cq.exporters.export(p, os.path.join(HERE, name + '.step'))
        cq.exporters.export(p, os.path.join(HERE, name + '.stl'), tolerance=0.05, angularTolerance=0.2)
    a = cq.Assembly(name='ereader_enclosure')
    col = {'back_shell': (0.25, 0.27, 0.3), 'front_cover': (0.85, 0.85, 0.82), 'j2_hood': (0.85, 0.85, 0.82),
           'joystick_cap': (0.9, 0.45, 0.1), 'button_plunger': (0.9, 0.45, 0.1)}
    for name, p in parts.items(): a.add(p, name=name, color=cq.Color(*col[name]))
    a.add(plunger2, name='button_plunger_2', color=cq.Color(0.9, 0.45, 0.1))
    a.add(board, name='mock_pcb', color=cq.Color(0.1, 0.4, 0.2)); a.add(comps, name='mock_components', color=cq.Color(0.6, 0.6, 0.6))
    a.add(display, name='mock_display_panel', color=cq.Color(0.95, 0.95, 0.9)); a.add(battery, name='mock_battery', color=cq.Color(0.3, 0.4, 0.8))
    a.add(dupont, name='mock_display_plugs', color=cq.Color(0.1, 0.1, 0.1))
    a.export(os.path.join(HERE, 'ereader_assembly.step'))
    # preview drawings (hidden-line SVG)
    opt = dict(width=1100, height=850, marginLeft=20, marginTop=20, showAxes=False, projectionDir=(-0.55, -0.75, 0.9), strokeWidth=0.35, showHidden=False)
    inside = parts['back_shell'].union(board).union(comps).union(battery).union(dupont)
    cq.exporters.export(inside, os.path.join(HERE, 'preview_inside.svg'), opt=opt)
    closed = parts['back_shell'].union(parts['front_cover']).union(parts['j2_hood']).union(parts['joystick_cap']).union(parts['button_plunger']).union(plunger2)
    cq.exporters.export(closed, os.path.join(HERE, 'preview_closed.svg'), opt=opt)
    cq.exporters.export(closed, os.path.join(HERE, 'preview_right_side.svg'), opt=dict(opt, projectionDir=(1.0, -0.35, 0.45)))

    # ---- report: size + clash check between printed parts and the mock-ups
    def vol(s):
        try: return s.val().Volume()
        except Exception: return 0.0
    bb = parts['back_shell'].union(parts['front_cover']).val().BoundingBox()
    print(f'outer size {bb.xlen:.1f} x {bb.ylen:.1f} x {Z_TOP:.1f} mm (hood adds {Z_PCB_TOP + DUPONT_H + 5.2 - Z_TOP:.1f}); A1 mini bed 180 x 180')
    print(f'PCB top at z={Z_PCB_TOP:.1f}, cover underside z={Z_COVER:.1f}, front z={Z_TOP:.1f}')
    mocks = {'pcb': board, 'components': comps, 'display': display, 'battery': battery, 'display plugs': dupont}
    printed = dict(parts, button_plunger_2=plunger2)
    clash = False
    for pn, p in printed.items():
        for mn, m in mocks.items():
            v = vol(p.intersect(m))
            if v > 0.5: clash = True; print(f'  CLASH {pn} x {mn}: {v:.1f} mm3')
    names = list(printed)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = vol(printed[names[i]].intersect(printed[names[j]]))
            if v > 0.5: clash = True; print(f'  CLASH {names[i]} x {names[j]}: {v:.1f} mm3')
    print('clash check:', 'PROBLEMS' if clash else 'clean')
