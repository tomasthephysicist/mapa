"""Model hradu Litice: doplní popis a kód do prep.py / render.html a zapíše assets/dominanty.json + assets/hrad.json.

Popis podle obrysů OpenStreetMap, ortofota ČÚZK, fotek a článku o obnově hradu (Lacina, 2023). Spouští se před prep.py.
python hrad.py            příprava
python hrad.py --vystup   po renderu: oprava klikací vrstvy a výřez summer do logu
"""
import base64, io, json, os, sys

PALAC_ID, SMAZAT = '8f998cf4-a7d8-478f-abac-db68e9795201', '8140c07a-27fa-4e90-b46b-a1e257056b04'
NAZEV = 'Hrad Litice'
PALAC = [(-1325.8, 97.7), (-1300.0, 118.0), (-1308.1, 128.1), (-1333.9, 107.8)]   # hlavní obdélník paláce (m v mapě)
VEZ = (-1311.35, 126.06)
ZDI = [  # (tloušťka, [(x, y, výška), ...])
    (1.9, [(-1362.4, 144.4, 8), (-1352, 151, 12), (-1343, 156.7, 11), (-1333.8, 162.5, 6)]),    # čelní zeď severního paláce
    (1.3, [(-1353.4, 147.8, 6), (-1349.8, 141.3, 3)]),                                          # příčky severního paláce
    (1.3, [(-1341.2, 154.0, 6), (-1337.8, 148.0, 3)]),
    (2.2, [(-1360.4, 134.9, 3), (-1354, 129.2, 10), (-1349, 124.7, 8), (-1342.3, 118.6, 2)]),    # zub hradby u nádvoří
    (2.0, [(-1316.7, 126.7, 13), (-1322.3, 133.7, 2.5)]),                                        # klínový zbytek zdi u věže
    (1.8, [(-1374.9, 141.1, 5), (-1377.4, 136.7, 5), (-1373.9, 133.7, 4)]),                      # brána
]
OBVOD = [(-1387.6, 170.9), (-1377.8, 168.1), (-1369.6, 177.3), (-1360.7, 181.6), (-1356.1, 190.8), (-1333.6, 192.6), (-1322.0, 193.9), (-1298.3, 155.3),
         (-1294.7, 146.1), (-1286.5, 140.3), (-1287.9, 133.4), (-1293.2, 130.8), (-1293.2, 117.5), (-1302.6, 114.3), (-1306.8, 106.4), (-1308.5, 94.8),
         (-1314.8, 85.4), (-1319.7, 85.1), (-1336.7, 92.5), (-1365.8, 120.8), (-1370.7, 115.6), (-1381.0, 124.9), (-1400.3, 140.2), (-1406.0, 146.6),
         (-1400.6, 158.8), (-1393.4, 162.0), (-1392.1, 171.5), (-1387.6, 170.9)]
ZDI.append((1.0, [(x, y, 2.6) for x, y in OBVOD]))                                               # vnější opevnění
PASEKY = [(-1335.0, 128.0, 22.0), (-1316.0, 113.0, 21.0), (-1350.0, 148.0, 14.0)]               # bez stromů (nádvoří, palác, ruiny)

KAMEN, SINDEL, TMAVY = [186, 176, 158], [122, 104, 84], [146, 124, 92]

PREP_A = "bld = bld[bld.sources.map(lambda s: s is not None and any(x['dataset'] == 'OpenStreetMap' for x in s))].reset_index(drop=True)\n"
PREP_A2 = PREP_A + """_hr = json.load(open('assets/hrad.json', encoding='utf-8'))
bld = bld[bld.id != _hr['smazat']].reset_index(drop=True)
for i, r in bld.iterrows():
    if r.id == _hr['palac_id']: bld.at[i, 'geom'] = Polygon([tuple(float(v) for v in to_local(lo, la)) for la, lo in _hr['palac']])
"""
PREP_B = "    if at == 'pt': return d['xy'][0], d['xy'][1], 0.0\n"
PREP_B2 = "    if at == 'pt': return d['xy'][0], d['xy'][1], sp.get('pt_a', 0.0)\n"
PREP_C = "# hráze nádrží: kamenná zeď s korunou (v datech polygon), budova bez oken\n"
PREP_C2 = """_hw = []
for _t, _pts in _hr['zdi']:
    _q = [tuple(float(v) for v in to_local(lo, la)) + (h,) for la, lo, h in _pts]
    for (x0, y0, h0), (x1, y1, h1) in zip(_q, _q[1:]):
        L = math.hypot(x1 - x0, y1 - y0); n = max(1, round(L / 2.4)); ang = math.atan2(y1 - y0, x1 - x0)
        for k in range(n):
            t = (k + 0.5) / n; x = x0 + (x1 - x0) * t; y = y0 + (y1 - y0) * t
            if not EXT_P.contains(Point(x, y)): continue
            g = float(ground(x, y)); hh = max(0.8, (h0 + (h1 - h0) * t) * (0.86 + 0.28 * h01(f'hw{x:.1f}{y:.1f}')))
            _hw.append([round(x, 2), round(y, 2), round(ang, 4), round(L / n + 0.15, 2), _t, round(g - 1.0, 2), round(g + hh, 2)])
            nd.ellipse([*P([(x - 4, y + 4)])[0], *P([(x + 4, y - 4)])[0]], fill=255)
for la, lo, r_ in _hr['paseky']:
    x, y = (float(v) for v in to_local(lo, la))
    if EXT_P.contains(Point(x, y)): nd.ellipse([*P([(x - r_, y + r_)])[0], *P([(x + r_, y - r_)])[0]], fill=255)
if _hw:
    x, y = _hw[0][:2]; g = float(ground(x, y))
    buildings.append({'p': [[x - 0.1, y - 0.1], [x + 0.1, y - 0.1], [x + 0.1, y + 0.1]], 'b': round(g - 0.6, 2), 'g': round(g, 2), 'e': round(g, 2), 'r': 'flat', 'rh': 0.0, 'parts': [],
                      'wc': (150, 146, 136), 'rc': (150, 146, 136), 's': 4, 'id': len(buildings), 'lm': 'dom', 'dn': _hr['nazev'] + ' ruiny', 'only': 1, 'tw': [], 'hw': _hw})
""" + PREP_C
REND_A = "const pitch = church ? deg(55) : chapel ?"
REND_A2 = "const pitch = church || b.dn === 'Hrad Litice' ? deg(55) : chapel ?"
REND_B = "if (t.top === 'spire') {"
REND_B2 = """if (t.top === 'litice') {                                                // věž hradu Litice: tmavé dřevěné patro s okny, šindelový jehlan
        ring(X, f, R0 * 1.03, R0 * 1.03, t.h, t.h + 3.0, 4, [0.17, 0.12, 0.10], [0, 1, 1, 0], rot);
        ring(X, f, R0 * 1.05, R0 * 1.05, t.h + 1.2, t.h + 2.0, 4, [0.58, 0.56, 0.46], [0, 1, 1, 0], rot);
        ring(R, f, R0 * 1.24, 0, t.h + 3.0, t.to, 4, tc, [0, 0, 0, 0], rot);
      } else if (t.top === 'spire') {"""
REND_C = "const ring = (B, f, r0, r1, z0, z1, n, col, aw, rot = 0) => {"
REND_C2 = """for (const b of scene.buildings) for (const [x, y, a, L, th, z0, z1] of b.hw || []) {             // ruiny hradu: kamenné zdi s nerovnou korunou
    pushBox(X, frameAt(x, y, 0, a), -L / 2, L / 2, -th / 2, th / 2, z0, z1, C255([176, 166, 148]), [0, 1, 1, 0], C255([150, 150, 118]));
  }
  """ + REND_C


def nahrad(soubor, dvojice):
    t = open(soubor, encoding='utf-8').read()
    for a, b in dvojice:
        if t.count(a) != 1: sys.exit(f'{soubor}: očekávané místo nalezeno {t.count(a)}×: {a[:50]}')
        t = t.replace(a, b)
    open(soubor, 'w', encoding='utf-8').write(t)


def priprav():
    import geo
    def ll(x, y):
        a, b = geo.to_lonlat(x, y); return float(b), float(a)
    la, lo = ll(*VEZ)
    os.makedirs('assets', exist_ok=True)
    json.dump([{'name': NAZEV, 'lat': la, 'lon': lo, 'text': 'Podle obrysů, ortofota a fotek hradu.', 'spec': {
        'wc': KAMEN, 'rc': SINDEL, 'r': 'hipped', 'h': 11.5, 'rh': 8.5, 'win': 4, 'pt_a': 0.666,
        'towers': [{'at': 'pt', 'w': 7.6, 'h': 22.0, 'to': 31.0, 'top': 'litice', 'tc': TMAVY}]}}],
        open('assets/dominanty.json', 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'nazev': NAZEV, 'palac_id': PALAC_ID, 'smazat': SMAZAT, 'palac': [ll(x, y) for x, y in PALAC],
               'zdi': [[t, [ll(x, y) + (h,) for x, y, h in q]] for t, q in ZDI], 'paseky': [ll(x, y) + (r,) for x, y, r in PASEKY]},
              open('assets/hrad.json', 'w', encoding='utf-8'), ensure_ascii=False)
    nahrad('prep.py', [(PREP_A, PREP_A2), (PREP_B, PREP_B2), (PREP_C, PREP_C2)])
    nahrad('render.html', [(REND_A, REND_A2), (REND_B, REND_B2), (REND_C, REND_C2)])
    print('hrad připraven', la, lo)


def vystup():
    import geo
    from PIL import Image
    f = 'site/overlay/c-1_0.json'; d = json.load(open(f, encoding='utf-8')); n0 = len(d['buildings'])
    d['buildings'] = [b for b in d['buildings'] if b.get('oid') != SMAZAT]
    for b in d['buildings']:
        if b.get('oid') == PALAC_ID: b['name'] = NAZEV; b['cls'] = 'hrad'; print('klikací palác upraven')
    json.dump(d, open(f, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False); print('budov', n0, '->', len(d['buildings']))
    D = 'build/c-1_0/tiles_summer'; info = json.load(open(f'{D}/info.json'))
    scene = json.load(open('build/c-1_0/scene.json'))
    g = next(b['g'] for b in scene['buildings'] if b.get('dn') == NAZEV); print('terén hradu', g)
    ix, iy, _ = geo.Image2D(info).px(-1330.0, 128.0, g + 6)
    w, h = 1300, 1000; x0, y0 = int(ix - w / 2), int(iy - h / 2); T = info['tile']
    im = Image.new('RGB', (w, h), (27, 33, 48))
    for i in range(x0 // T, (x0 + w) // T + 1):
        for j in range(y0 // T, (y0 + h) // T + 1):
            p = f'{D}/{i}_{j}.png'
            if os.path.exists(p):
                t = Image.open(p).convert('RGBA'); im.paste(t, (i * T - x0, j * T - y0), t)
    b_ = io.BytesIO(); im.save(b_, 'JPEG', quality=80); s = base64.b64encode(b_.getvalue()).decode()
    print('VYREZ', len(s))
    for i in range(0, len(s), 4000): print('B64H', s[i:i + 4000])


if __name__ == '__main__':
    vystup() if '--vystup' in sys.argv else priprav()
