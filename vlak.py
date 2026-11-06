"""Přidá do hotové mapy vlaky linky V2 bez nového renderu: site/mhd.json + kód vlaku v site/index.html.

Spouští se z kořene repozitáře, když je ve složce site/ hotová mapa (workflow pridat-vlak.yml):  python vlak.py
Jízdní řád je opsaný z výpisu zastávek Bohousová a Litice nad Orlicí, dopravce České dráhy, a.s.
Mimo zastávky se poloha dopočítává z rychlosti mezi nimi, skutečná poloha vlaku se nesleduje.
"""
import heapq, json, math, os, sys, time, urllib.parse, urllib.request

LITICE, BOHOUSOVA = 'Litice nad Orlicí', 'Bohousová'
LET, HK, TY, DO = 'Letohrad', 'Hradec Králové hl.n.', 'Týniště nad Orlicí', 'Doudleby nad Orlicí'
OD, DO_DNE = 20251214, 20261212   # platnost jízdního řádu

# vlak, cíl, služba, Litice příjezd, Litice odjezd, Bohousová příjezd, Bohousová odjezd
# Směr poznáme z času: nahoru (Letohrad) je dřív v Liticích, dolů (Hradec, Týniště, Doudleby) dřív v Bohousové.
VLAKY = [
    (5151, LET, 'W', '4.49', '4.50', '4.53', '4.53'), (1822, HK, 'W', '4.46', '4.53', '4.43', '4.43'),
    (1824, HK, 'D', '5.49', '5.50', '5.46', '5.47'), (1821, LET, 'D', '6.07', '6.07', '6.10', '6.10'),
    (1826, HK, 'W', '6.52', '6.53', '6.49', '6.50'), (1823, LET, 'W', '7.08', '7.09', '7.11', '7.12'),
    (1828, HK, 'D', '7.53', '7.54', '7.50', '7.50'), (1825, LET, 'D', '8.11', '8.11', '8.14', '8.14'),
    (2011, LET, 'S', '9.30', '9.30', '9.33', '9.33'), (1830, HK, 'D', '9.53', '9.54', '9.50', '9.50'),
    (1827, LET, 'D', '10.11', '10.11', '10.14', '10.14'), (1832, HK, 'D', '11.53', '11.54', '11.50', '11.50'),
    (1829, LET, 'D', '12.11', '12.11', '12.14', '12.14'), (1834, HK, 'D', '13.52', '13.53', '13.49', '13.49'),
    (1831, LET, 'D', '14.10', '14.10', '14.13', '14.13'), (2010, TY, 'X', '14.33', '14.41', '14.29', '14.29'),
    (1836, HK, 'W', '14.53', '14.54', '14.49', '14.50'), (1833, LET, 'W', '15.08', '15.09', '15.11', '15.12'),
    (1838, HK, 'D', '15.53', '15.54', '15.50', '15.50'), (1835, LET, 'D', '16.11', '16.11', '16.14', '16.14'),
    (2012, HK, 'S2', '16.33', '16.35', '16.30', '16.30'), (1840, HK, 'W', '16.53', '16.54', '16.49', '16.50'),
    (1837, LET, 'W', '17.08', '17.09', '17.11', '17.12'), (1842, HK, 'P24', '17.53', '17.54', '17.50', '17.50'),
    (1839, LET, 'P24', '18.11', '18.11', '18.14', '18.14'), (1844, HK, 'P2431', '19.53', '19.54', '19.50', '19.50'),
    (1841, LET, 'P2431', '20.11', '20.11', '20.14', '20.14'), (1845, LET, 'W31', '22.07', '22.08', '22.10', '22.11'),
    (5152, DO, 'W31', '22.51', '22.51', '22.48', '22.48'),
]
SVATKY_V_TYDNU = [20251224, 20251225, 20251226, 20260101, 20260403, 20260406, 20260501, 20260508, 20260706, 20260928,
                  20261028, 20261117, 20261224, 20261225]
_NEDELE = []
for ord_ in range(time.mktime((2026, 4, 26, 12, 0, 0, 0, 0, -1)).__int__() // 86400, time.mktime((2026, 9, 28, 12, 0, 0, 0, 0, -1)).__int__() // 86400 + 1):
    t_ = time.gmtime(ord_ * 86400)
    if t_.tm_wday >= 5: _NEDELE.append(t_.tm_year * 10000 + t_.tm_mon * 100 + t_.tm_mday)
LETNI = sorted(set(_NEDELE) | {20260501, 20260508, 20260706, 20260928})
SLUZBY = {
    'D': [[1] * 7, OD, DO_DNE, [], []],
    'W': [[1] * 5 + [0, 0], OD, DO_DNE, [], SVATKY_V_TYDNU],
    'W31': [[1] * 5 + [0, 0], OD, DO_DNE, [], SVATKY_V_TYDNU + [20251231, 20261231]],
    'P24': [[1] * 7, OD, DO_DNE, [], [20251224, 20261224]],
    'P2431': [[1] * 7, OD, DO_DNE, [], [20251224, 20251231, 20261224, 20261231]],
    'S': [[0] * 7, OD, DO_DNE, LETNI, []],                                  # sezónní víkendové vlaky jen ve vyjmenované dny
    'S2': [[0] * 7, OD, DO_DNE, [d for d in LETNI if d != 20260510], []],   # 2012 Letohrad–Litice nejede 10. 5.
    'X': [[0] * 7, OD, DO_DNE, [20260510], []],
}


def cas(t):
    h, m = t.split('.')
    return int(h) * 3600 + int(m) * 60


def delka(p):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(p, p[1:]))


def poloha_na_trase(p, bod):
    best, s, nej = 1e18, 0.0, 0.0
    for a, b in zip(p, p[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]; l2 = dx * dx + dy * dy or 1e-9
        u = max(0.0, min(1.0, ((bod[0] - a[0]) * dx + (bod[1] - a[1]) * dy) / l2))
        d = math.hypot(a[0] + u * dx - bod[0], a[1] + u * dy - bod[1])
        if d < best: best, nej = d, s + u * math.sqrt(l2)
        s += math.sqrt(l2)
    return nej, best


class Koleje:
    def __init__(self, cary):
        self.xy, self.idx, self.adj = [], {}, []
        for c in cary:
            ids = [self.uzel(p) for p in c]
            for a, b in zip(ids, ids[1:]):
                if a != b:
                    w = math.hypot(self.xy[a][0] - self.xy[b][0], self.xy[a][1] - self.xy[b][1])
                    self.adj[a].append((b, w)); self.adj[b].append((a, w))

    def uzel(self, p):
        k = (round(p[0] * 2), round(p[1] * 2))
        if k not in self.idx: self.idx[k] = len(self.xy); self.xy.append((float(p[0]), float(p[1]))); self.adj.append([])
        return self.idx[k]

    def nejblizsi(self, p):
        return min(range(len(self.xy)), key=lambda i: math.hypot(self.xy[i][0] - p[0], self.xy[i][1] - p[1]))

    def dijkstra(self, a, zakaz=()):
        dist, prev, q = {a: 0.0}, {}, [(0.0, a)]
        while q:
            d, u = heapq.heappop(q)
            if d > dist[u]: continue
            for v, w in self.adj[u]:
                if v not in zakaz and d + w < dist.get(v, 1e18): dist[v] = d + w; prev[v] = u; heapq.heappush(q, (d + w, v))
        return dist, prev


def cesta(prev, a, b):
    out = [b]
    while out[-1] != a: out.append(prev[out[-1]])
    return out[::-1]


def hlavni_trat(cary, bod_l, bod_b):
    """celá trať přes obě zastávky: konec za Liticemi -> Litice -> Bohousová -> konec za Bohousovou"""
    K = Koleje(cary)
    a, b = K.nejblizsi(bod_l), K.nejblizsi(bod_b)
    dist, prev = K.dijkstra(a)
    if b not in dist: sys.exit('Koleje mezi zastávkami nejsou v datech souvislé.')
    mezi = cesta(prev, a, b)
    d1, p1 = K.dijkstra(a, set(mezi[1:]))
    konec_a = max(d1, key=d1.get); pred = cesta(p1, a, konec_a)[::-1]
    d2, p2 = K.dijkstra(b, set(mezi[:-1]))
    konec_b = max(d2, key=d2.get); za = cesta(p2, b, konec_b)
    return [K.xy[i] for i in pred[:-1] + mezi + za[1:]]


def sestav_mhd(trat, bod_l, bod_b):
    sl, dl = poloha_na_trase(trat, bod_l)
    sb, db = poloha_na_trase(trat, bod_b)
    print(f'trať {delka(trat):.0f} m, Litice {sl:.0f} m (od kolejí {dl:.0f} m), Bohousová {sb:.0f} m (od kolejí {db:.0f} m)')
    if dl > 150 or db > 150 or sb <= sl: sys.exit('Zastávka neleží na nalezené trati.')
    L = delka(trat)
    v = (sb - sl) / 180.0                     # jízdní řád: mezi zastávkami 3 minuty
    print(f'rychlost {v * 3.6:.0f} km/h')
    if not 25 / 3.6 < v < 120 / 3.6: sys.exit('Nesmyslná rychlost – zkontroluj polohy zastávek.')
    nahoru = [[round(x, 1), round(y, 1)] for x, y in trat]
    dolu = nahoru[::-1]
    names = [LITICE, BOHOUSOVA, LET, HK, TY, DO]; N = {n: i for i, n in enumerate(names)}
    trips = []
    for cislo, cil, sluzba, la, lo, ba, bo in VLAKY:
        la, lo, ba, bo = cas(la), cas(lo), cas(ba), cas(bo)
        if la < bo and ba > lo:               # Litice -> Bohousová
            tvar, a1, o1, n1, s1, a2, o2, n2, s2 = 0, la, lo, LITICE, sl, ba, bo, BOHOUSOVA, sb
        elif ba < lo and la > bo:             # Bohousová -> Litice
            tvar, a1, o1, n1, s1, a2, o2, n2, s2 = 1, ba, bo, BOHOUSOVA, L - sb, la, lo, LITICE, L - sl
        else:
            sys.exit(f'Vlak {cislo}: časy nesedí.')
        if a1 == o1: a1 -= 10; o1 += 10       # jízdní řád je po minutách: krátký pobyt kolem odjezdu
        if a2 == o2: a2 -= 10; o2 += 10
        t0 = int(a1 - s1 / v)
        konec = int(o2 + (L - s2) / v)
        seq = [0, 0, a1 - t0, round(s1), o1 - t0, round(s1), a2 - t0, round(s2), o2 - t0, round(s2), konec - t0, round(L)]
        trips.append([0, tvar, sluzba, t0, seq, N[cil], [N[n1], a1 - t0, N[n2], a2 - t0]])
    trips.sort(key=lambda t: t[3])
    return {'routes': [['V2', 2]], 'shapes': [nahoru, dolu], 'services': SLUZBY, 'trips': trips, 'names': names, 'feed': '2026'}


VLAK_JS = r'''if (isBus === 3) {                                                      // vlak: obecná modrá motorová jednotka
      const BL = [38, 88, 164], WH = [238, 240, 236], GL = [38, 44, 54], DOOR = [244, 196, 28], ROOF = snow || [204, 208, 212];
      const ch = 1.3, fp = [[-l + ch, -w], [l - ch, -w], [l, -w * 0.55], [l, w * 0.55], [l - ch, w], [-l + ch, w], [-l, w * 0.55], [-l, -w * 0.55]];
      const bands = [[0.25, 0.65, DARK], [0.65, 1.3, BL], [1.3, 1.46, WH], [1.46, 2.55, null], [2.55, 3.45, BL]];
      const Q = (A, B, z0, z1, rgb, d) => faces.push([[R(A[0], A[1], z0), R(B[0], B[1], z0), R(B[0], B[1], z1), R(A[0], A[1], z1)], lit(rgb, d)]);
      for (let i = 0; i < fp.length; i++) {
        const A = fp[i], B = fp[(i + 1) % fp.length], es = B[0] - A[0], et = B[1] - A[1], el = Math.hypot(es, et), ns = et / el, nt = -es / el;
        const nx = fx_ * ns + sxv * nt, ny = fy_ * ns + syv * nt;
        if (!vis(nx, ny)) continue;
        const d = sun(nx, ny, 0), side = Math.abs(nt) > 0.9;
        for (const [z0, z1, col] of bands) {
          if (col) { Q(A, B, z0, z1, col, d); continue; }
          Q(A, B, z0, z1, side ? GL : (Math.abs(ns) > 0.9 ? GL : BL), d);
        }
        if (side) for (const ds of [-l * 0.62, -0.7, l * 0.62 - 1.4]) {        // dveře
          const q0 = (ds - A[0]) / es, q1 = (ds + 1.4 - A[0]) / es, P = (q) => [A[0] + es * q, A[1] + et * q];
          Q(P(Math.min(q0, q1)), P(Math.max(q0, q1)), 0.65, 2.75, DOOR, d);
        }
        if (Math.abs(ns) > 0.9) Q(A, B, 0.65, 1.0, DOOR, d);                  // žluté čelo dole
      }
      const rz = 3.72, ip = fp.map(([s_, t_]) => [s_ * 0.985, t_ * 0.78]);
      for (let i = 0; i < fp.length; i++) {
        const A = fp[i], B = fp[(i + 1) % fp.length], a = ip[i], b = ip[(i + 1) % fp.length], es = B[0] - A[0], et = B[1] - A[1], el = Math.hypot(es, et);
        const nx = fx_ * et / el - sxv * es / el, ny = fy_ * et / el - syv * es / el;
        if (nx + ny >= 0.3) continue;
        faces.push([[R(A[0], A[1], 3.45), R(B[0], B[1], 3.45), R(b[0], b[1], rz), R(a[0], a[1], rz)], lit(snow || WH, sun(nx * 0.6, ny * 0.6, 0.8))]);
      }
      faces.push([ip.map(([s_, t_]) => R(s_, t_, rz)), lit(ROOF, sun(0, 0, 1))]);
      box(-l * 0.5, -l * 0.15, -0.65, 0.65, rz, rz + 0.3, [150, 154, 160], ROOF);
      box(l * 0.15, l * 0.5, -0.65, 0.65, rz, rz + 0.3, [150, 154, 160], ROOF);
    } else if (isBus === 2) {'''

UPRAVY = [
    ("if (isBus === 2) return; for (const s_ of isBus", "if (isBus >= 2) return; for (const s_ of isBus"),
    ("if (isBus === 2) {                                                      // tramvaj T3", VLAK_JS + "                                                      // tramvaj T3"),
    ("const shown_ = typ === 0 ? drawVehicle(o, 15, 2.5, 't3', sx, ox, oy, night, 2) :",
     "if (typ === 2) o.lane = 0;\n          const shown_ = typ === 2 ? drawVehicle(o, 25, 2.9, '#2658a4', sx, ox, oy, night, 3) : typ === 0 ? drawVehicle(o, 15, 2.5, 't3', sx, ox, oy, night, 2) :"),
    ("`${typ === 0 ? 'Tramvaj' : 'Autobus'} ${line}`", "`${typ === 2 ? 'Vlak' : typ === 0 ? 'Tramvaj' : 'Autobus'} ${line}`"),
]


def uprav_kod(text):
    for a, b in UPRAVY:
        if text.count(a) != 1: sys.exit(f'V kódu mapy chybí očekávané místo: {a[:50]}')
        text = text.replace(a, b)
    return text


def stahni_koleje():
    import pyarrow.dataset as ds, pyarrow.fs as fs, shapely, geo
    from shapely.ops import transform
    X0, X1, Y0, Y1 = geo.bbox_lonlat(400)
    d = ds.dataset('overturemaps-us-west-2/release/2026-10-21.0/theme=transportation/type=segment/',
                   filesystem=fs.S3FileSystem(anonymous=True, region='us-west-2'), format='parquet')
    f = ((ds.field('bbox', 'xmin') < X1) & (ds.field('bbox', 'xmax') > X0) & (ds.field('bbox', 'ymin') < Y1) & (ds.field('bbox', 'ymax') > Y0)
         & (ds.field('subtype') == 'rail'))
    cary = []
    for r in d.to_table(filter=f, columns=['class', 'geometry']).to_pylist():
        if r['class'] == 'tram': continue
        g = transform(lambda x, y, z=None: geo.to_local(x, y), shapely.from_wkb(r['geometry'])).segmentize(20.0)
        cary += [list(ls.coords) for ls in getattr(g, 'geoms', [g])]
    print('úseků kolejí', len(cary))
    return cary


def najdi_zastavky():
    import geo
    X0, X1, Y0, Y1 = geo.bbox_lonlat(400)
    q = f'[out:json][timeout:60];nwr["railway"~"^(station|halt)$"]["name"~"Bohousov|Litice"]({Y0},{X0},{Y1},{X1});out center;'
    for pokus in range(4):
        try:
            rq = urllib.request.Request('https://overpass-api.de/api/interpreter', urllib.parse.urlencode({'data': q}).encode(), {'User-Agent': 'mapa-zachlumi'})
            el = json.load(urllib.request.urlopen(rq, timeout=90))['elements']
            break
        except Exception as e:
            print('Overpass:', e); time.sleep(20)
    else:
        sys.exit('Nepodařilo se načíst polohy zastávek.')
    out = {}
    for e in el:
        n = e.get('tags', {}).get('name', ''); print('nalezeno', n, e.get('lat') or e['center']['lat'], e.get('lon') or e['center']['lon'])
        lat, lon = e.get('lat') or e['center']['lat'], e.get('lon') or e['center']['lon']
        klic = 'b' if 'Bohousov' in n else 'l' if 'Litice' in n else None
        if klic: out[klic] = tuple(float(v) for v in geo.to_local(lon, lat))
    if len(out) < 2: sys.exit(f'V OpenStreetMap chybí některá zastávka: {out}')
    return out['l'], out['b']


if __name__ == '__main__':
    import geo
    ov = json.load(open('site/overlay.json', encoding='utf-8'))
    ch = {f'c{i}_{j}' for i, j in geo.CHUNKS}
    if ch != set(ov['chunks']): sys.exit(f'mesto.json nesedí k hotové mapě: {sorted(ch)} / {sorted(ov["chunks"])}')
    bod_l, bod_b = najdi_zastavky()
    m = sestav_mhd(hlavni_trat(stahni_koleje(), bod_l, bod_b), bod_l, bod_b)
    json.dump(m, open('site/mhd.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print('vlaků', len(m['trips']), 'kB', os.path.getsize('site/mhd.json') // 1000)
    a = open('web/app.html', encoding='utf-8').read()
    a = uprav_kod(a).replace('{{MHD_ZDROJ}}', ', jízdní řád vlaků podle údajů dopravce České dráhy, a.s.')
    open('web/app.html', 'w', encoding='utf-8').write(a)
    import subprocess
    subprocess.run([sys.executable, 'build_html.py'], check=True)
