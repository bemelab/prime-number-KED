# -*- coding: utf-8 -*-
"""
PATI KED ANALIZLERI - tarama sonuclarindan sezgisel model ve istatistik analizleri.

Sonuc klasorlerini yalniz OKUR. Pahali ara sonuclar KED_GRAFIK/ONBELLEK altinda TXT saklanir:
  ANALIZ_ZINCIR__<prog>__<aralik>.txt  P8+ zincirler (baslangic uzunluk isaret blok dogru)
  ANALIZ_ORNEK__<prog>__<aralik>.txt   rastgele pencere ornekleminin toplamlari (tek satir JSON)
  ANALIZ_BLOK__<prog>__<aralik>.txt    P6/P7 blok ornekleminin model toplamlari (tek satir JSON)

KED(n) = sum rakam^2 * 10^konum. Zincir p -> KED(p) -> ... terimler asal kaldikca uzar.
Model: x = KED(t) icin P(x asal) = C(x) / ln x; C(x) yerel (kucuk asal modulu) duzeltmelerdir.
"""
import itertools
import json
import math
import os
import random
from array import array
from bisect import bisect_right
from collections import Counter, defaultdict

import ked_veri as kv

SURUM = 1
ORNEK_SURUM = 2                 # pencere orneklemi onbellegi icin
KMAX = 16                       # orneklemde izlenen en uzun adim
MILYAR = 10 ** 9
PENCERE = 4_000_000             # orneklem penceresi genisligi
PENCERE_YOGUNLUK = 50 / 1e15    # sayi dogrusunda birim uzunluk basina pencere
KONTROL_N = 15_000              # pencere basina kontrol deneyi ornegi
DUZGUN_N = 4_000                # pencere basina duzgun dagilimli rastgele asal (rakam analizleri)
ALT_BASAMAK = slice(-7, -1)     # 0/1 sayimi: son rakam haric alttaki 6 basamak (pencerede degisen)
BLOK_ADIM = 97                  # P6/P7 icin her 97. milyarlik blok okunur
ORAN_BIN, ORAN_N = 0.05, 60     # log10(KED(p)/p) histogrami
YEREL_Q = [3, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83,
           89, 97]
VARYANTLAR = ["1/ln x", "+ 2 ve 5 (son rakam 1/9)", "+ mod 3", "+ mod 11",
              "+ elek ≤1000 (Granville)"]
UZK_P8 = [f"P{k}" for k in range(8, 21)] + ["P21_PLUS"]


# ---------------------------------------------------------------- KED ve asallik

_KED3 = [(c // 100) ** 2 * 100 + (c // 10 % 10) ** 2 * 10 + (c % 10) ** 2 for c in range(1000)]


def ked(n):
    """KED(n) = sum d_i^2 10^i (uc basamakli parcalarla)."""
    s, c = 0, 1
    while n:
        n, r = divmod(n, 1000)
        s += _KED3[r] * c
        c *= 1000
    return s


def elek(n):
    s = bytearray(b"\x01") * (n + 1)
    s[0:2] = b"\x00\x00"
    for i in range(2, math.isqrt(n) + 1):
        if s[i]:
            s[i * i::i] = bytes((n - i * i) // i + 1)
    return s


def asal_listesi(n):
    return list(itertools.compress(range(n + 1), elek(n)))


KUCUK = asal_listesi(1000)
KUCUK_KUME = frozenset(KUCUK)
P200 = math.prod(q for q in KUCUK if q <= 200)
PRIMORIAL = math.prod(KUCUK)
MERTENS = math.prod(q / (q - 1) for q in KUCUK)
MR_TABAN = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)   # n < 3,3e24 icin kesin


def asal_mi(n):
    if n < 1000:
        return n in KUCUK_KUME
    if math.gcd(n, P200) != 1:
        return False
    d, s = n - 1, 0
    while not d & 1:
        d >>= 1
        s += 1
    for a in MR_TABAN:
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def model(x):
    """x = KED(t) icin bes model varyantinin 'x asal' olasiligi."""
    L = math.log(x)
    v0 = 1 / L
    if x % 2 == 0 or x % 5 == 0:
        return (v0, 0.0, 0.0, 0.0, 0.0)
    v1 = 2.5 / L                                   # 2 ve 5'e bolunmez: (2/1)(5/4)
    v2 = 0.0 if x % 3 == 0 else 1.5 * v1           # 3'e bolunmez: 3/2
    v3 = 0.0 if (v2 == 0.0 or x % 11 == 0) else 1.1 * v2
    v4 = MERTENS / L if math.gcd(x, PRIMORIAL) == 1 else 0.0
    return (min(v0, 1.0), min(v1, 1.0), min(v2, 1.0), min(v3, 1.0), min(v4, 1.0))


def zincir(p, sinir=64):
    """p'den baslayan zincir terimleri ve sonlayan bilesik (sabit nokta/dongu: None)."""
    t = [p]
    while len(t) < sinir:
        x = ked(t[-1])
        if x in t:
            return t, None
        if not asal_mi(x):
            return t, x
        t.append(x)
    return t, None


def en_kucuk_carpan(x, sinir=1000):
    for q in KUCUK:
        if q > sinir:
            break
        if x % q == 0:
            return q
    return None


# ---------------------------------------------------------------- yardimci istatistik

def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 1.0
    p = k / n
    m = 1 + z * z / n
    c = (p + z * z / (2 * n)) / m
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / m
    return p, max(0.0, c - h), min(1.0, c + h)


def ks_p(D, n):
    """Kolmogorov dagilimi ile iki yonlu KS p-degeri (Stephens duzeltmesi)."""
    if n == 0:
        return 1.0
    lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * D
    if lam < 0.2:
        return 1.0
    s = sum((-1) ** (j - 1) * math.exp(-2 * j * j * lam * lam) for j in range(1, 101))
    return max(0.0, min(1.0, 2 * s))


def ki_kare_p(x, sd):
    """P(Chi2_sd > x): duzenli ust eksik gamma Q(sd/2, x/2)."""
    if sd <= 0:
        return 1.0
    a, x = sd / 2, x / 2
    if x <= 0:
        return 1.0
    if x < a + 1:
        terim = toplam = 1 / a
        n = a
        for _ in range(500):
            n += 1
            terim *= x / n
            toplam += terim
            if terim < toplam * 1e-15:
                break
        return max(0.0, 1 - toplam * math.exp(-x + a * math.log(x) - math.lgamma(a)))
    b = x + 1 - a                                  # surekli kesir (Lentz)
    c, d = 1e300, 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - math.lgamma(a)) * h)


# ---------------------------------------------------------------- onbellek

def _ob_yolu(on, kaynak):
    return os.path.join(kv.ONBELLEK, f"{on}__{kaynak.program}__{kaynak.ad}.txt")


def _json_oku(yol, anahtar):
    if not os.path.exists(yol):
        return None
    with open(yol, encoding="utf-8") as f:
        if f.readline().strip() != f"# anahtar = {anahtar}":
            return None
        return json.loads(f.readline())


def _json_yaz(yol, anahtar, veri):
    os.makedirs(kv.ONBELLEK, exist_ok=True)
    with open(yol + ".tmp", "w", encoding="utf-8") as f:
        f.write(f"# anahtar = {anahtar}\n")
        f.write(json.dumps(veri, separators=(",", ":")) + "\n")
    os.replace(yol + ".tmp", yol)


def _dosyalar(kaynak, uzklar, suzgec=None):
    out = []
    for uzk in uzklar:
        d = os.path.join(kaynak.klasor, uzk)
        if not os.path.isdir(d):
            continue
        for e in os.scandir(d):
            m = kv.DOSYA_RE.search(e.name)
            if m and int(m.group(2)) <= kaynak.sinir:
                blok = int(m.group(1)) // MILYAR
                if suzgec is None or suzgec(blok):
                    out.append((e.path, e.stat().st_size, blok))
    return out


def _satir_terimleri(satir):
    p = satir.split()
    return p, [int(v) for v in p[3::2]]


# ---------------------------------------------------------------- P8+ zincir kayitlari

def zincir_kayitlari(kaynak, dur=None, ilerleme=None):
    """[(baslangic, uzunluk, olasilikli_mi, blok, dogru_mu)] - dogru: dosyadaki terimler
    KED yinelemesiyle birebir ayni."""
    girdiler = _dosyalar(kaynak, UZK_P8)
    anahtar = f"v{SURUM} {len(girdiler)} {sum(g[1] for g in girdiler)} {kaynak.sinir}"
    yol = _ob_yolu("ANALIZ_ZINCIR", kaynak)
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            if f.readline().strip() == f"# anahtar = {anahtar}":
                out = []
                for satir in f:
                    a = satir.split()
                    out.append((int(a[0]), int(a[1]), a[2] == "1", int(a[3]), a[4] == "1"))
                return out
    out = []
    for i, (dosya, _, blok) in enumerate(girdiler):
        if dur is not None and dur.is_set():
            return None
        if ilerleme and i % 500 == 0:
            ilerleme(f"{kaynak.program} {kv.trilyon(kaynak.bas)} P8+ zincirleri", i, len(girdiler))
        with open(dosya, encoding="utf-8", errors="replace") as f:
            for satir in f:
                if not satir.startswith("P"):
                    continue
                p, terim = _satir_terimleri(satir)
                yineleme = [terim[0]]
                while len(yineleme) < len(terim):
                    yineleme.append(ked(yineleme[-1]))
                out.append((terim[0], len(terim), p[2].endswith("*"), blok, yineleme == terim))
    out.sort()
    os.makedirs(kv.ONBELLEK, exist_ok=True)
    with open(yol + ".tmp", "w", encoding="utf-8") as f:
        f.write(f"# anahtar = {anahtar}\n")
        for b, L, y, blok, d in out:
            f.write(f"{b} {L} {int(y)} {blok} {int(d)}\n")
    os.replace(yol + ".tmp", yol)
    return out


# ---------------------------------------------------------------- P6/P7 blok orneklemi

def _adim_bos():
    return [0.0] * 12          # n, sum f (5), sum f^2 (5), sum ln x


def _adim_ekle(a, x):
    f = model(x)
    a[0] += 1
    for v in range(5):
        a[1 + v] += f[v]
        a[6 + v] += f[v] * f[v]
    a[11] += math.log(x)


def blok_orneklemi(kaynak, kayitlar, dur=None, ilerleme=None):
    """Her BLOK_ADIM. milyarlik blokta >=6 zincirlerin 6. ve 7. terimleri icin model toplamlari."""
    sec = lambda blok: blok % BLOK_ADIM == 0
    girdiler = _dosyalar(kaynak, ("P6", "P7"), sec)
    anahtar = f"v{SURUM} {len(girdiler)} {sum(g[1] for g in girdiler)} {len(kayitlar)}"
    yol = _ob_yolu("ANALIZ_BLOK", kaynak)
    veri = _json_oku(yol, anahtar)
    if veri is not None:
        return veri
    adim = {6: _adim_bos(), 7: _adim_bos()}
    ge = {6: 0, 7: 0, 8: 0}
    baslar = []
    for i, (dosya, _, blok) in enumerate(girdiler):
        if dur is not None and dur.is_set():
            return None
        if ilerleme and i % 200 == 0:
            ilerleme(f"{kaynak.program} {kv.trilyon(kaynak.bas)} P6/P7 blok orneklemi", i,
                     len(girdiler))
        with open(dosya, encoding="utf-8", errors="replace") as f:
            for satir in f:
                if satir.startswith("P"):
                    p = satir.split()
                    baslar.append((int(p[1]), len(p[3::2])))
    baslar += [(b, L) for b, L, _, blok, _ in kayitlar if sec(blok)]
    for b, L in baslar:
        t = b
        for k in range(1, min(L, 7) + 1):
            x = ked(t)
            if k >= 6:
                _adim_ekle(adim[k], x)
            t = x
        for k in (6, 7, 8):
            ge[k] += L >= k
    veri = {"adim": adim, "ge": ge, "blok_sayisi": len({g[2] for g in girdiler})}
    _json_yaz(yol, anahtar, veri)
    return json.loads(json.dumps(veri))      # anahtarlar dosyadan okununca da str olsun


# ---------------------------------------------------------------- rastgele pencere orneklemi

_TABAN = array("I")


def _taban_asallar(ust):
    global _TABAN
    k = math.isqrt(ust) + 1
    if not _TABAN or _TABAN[-1] < k:
        _TABAN = array("I", asal_listesi(max(k, 1000)))
    return _TABAN


def pencere_elegi(a, b):
    """[a, b) icin bytearray: 1 = asal."""
    W = b - a
    s = bytearray(b"\x01") * W
    for p in _taban_asallar(b):
        pp = p * p
        if pp >= b:
            break
        st = max(pp, -(-a // p) * p) - a
        if st < W:
            s[st::p] = bytes((W - 1 - st) // p + 1)
    for i in range(min(W, max(0, 2 - a))):
        s[i] = 0
    return s


def ornek_bos():
    return {"n": 0, "dongu": 0, "uzunluk": [0] * (KMAX + 2),
            "adim": [_adim_bos() for _ in range(KMAX + 2)],
            "basamak": [0] * (KMAX + 2),
            "sinif3": [[0] * (KMAX + 2) for _ in range(3)],
            "sinif3_f": [[0.0, 0.0, 0.0] for _ in range(3)],   # sum f(v3) adim1, adim2, n2
            "mod11": [[0] * (KMAX + 2) for _ in range(2)],
            "rakam": [0] * 10, "ilk_rakam": [0] * 10, "duzgun_n": 0,
            "r01": [[0] * 24 for _ in range(8)],
            "oran": [0] * ORAN_N,
            "yerel_p": [0] * len(YEREL_Q), "yerel_z": [0] * len(YEREL_Q), "yerel_zn": 0,
            "k_gercek": [0] * (KMAX + 2), "k_bilesik": [0] * (KMAX + 2),
            "k_rastgele": [0] * (KMAX + 2)}


def _duzgun_isle(p, O):
    """Duzgun dagilimli asal ornegi: rakam sikligi, ilk rakam ve KED(p)/p.
    (Pencere asallarinin ust basamaklari pencere icinde sabit oldugundan burada kullanilmaz.)"""
    s = str(p)
    govde = s[:-1]
    for d in range(10):
        O["rakam"][d] += govde.count(chr(48 + d))
    O["ilk_rakam"][ord(s[0]) - 48] += 1
    r = math.log10(ked(p) / p) / ORAN_BIN
    O["oran"][min(ORAN_N - 1, max(0, int(r)))] += 1
    O["duzgun_n"] += 1


def duzgun_asal(rng, lo, hi):
    while True:
        n = rng.randrange(lo, hi) | 1
        if asal_mi(n):
            return n


def _asal_isle(p, O):
    s = str(p)
    alt = s[ALT_BASAMAK]
    c01 = alt.count("0") + alt.count("1")
    adim, basamak = O["adim"], O["basamak"]
    t, L, c3, f11 = p, 1, 0, 0
    while True:
        x = ked(t)
        if x == t:                       # 0/1 rakamli sabit nokta (tarama: P1 sayar)
            if L > 1:
                O["dongu"] += 1
            break
        a = adim[L]
        f = model(x)
        a[0] += 1
        for v in range(5):
            a[1 + v] += f[v]
            a[6 + v] += f[v] * f[v]
        a[11] += math.log(x)
        basamak[L] += len(str(t))
        if L == 1:
            c3, f11 = x % 3, int(x % 11 == 0)
            O["sinif3_f"][c3][0] += f[3]
            yp = O["yerel_p"]
            for i, q in enumerate(YEREL_Q):
                if x % q == 0:
                    yp[i] += 1
        else:
            if L == 2:
                O["sinif3_f"][c3][1] += f[3]
                O["sinif3_f"][c3][2] += 1
            O["yerel_zn"] += 1
            yz = O["yerel_z"]
            for i, q in enumerate(YEREL_Q):
                if x % q == 0:
                    yz[i] += 1
        if L <= KMAX and asal_mi(x):
            t = x
            L += 1
        else:
            break
    O["n"] += 1
    O["uzunluk"][L] += 1
    O["sinif3"][c3][L] += 1
    O["mod11"][f11][L] += 1
    O["r01"][min(L, 7)][min(c01, 23)] += 1
    return L


def _kontrol_uzunlugu(n, rng=None):
    """n'den baslayip KED (ya da rastgele eslemeyle) yinelenen degerler asal kaldikca uzunluk."""
    t, L = n, 1
    while L <= KMAX:
        x = ked(t)
        if rng is not None:
            x += 10 * rng.randrange(max(1, x // 10))     # ayni son rakam, [x, 2x) araliginda
        if x == t or not asal_mi(x):
            break
        t, L = x, L + 1
    return L


def pencere_orneklemi(kaynak, dur=None, ilerleme=None):
    ust = kaynak.bit
    adet = max(1, round((ust - kaynak.bas) * PENCERE_YOGUNLUK))
    anahtar = f"v{ORNEK_SURUM} {kaynak.bas} {ust} {adet} {PENCERE} {KONTROL_N} {DUZGUN_N}"
    yol = _ob_yolu("ANALIZ_ORNEK", kaynak)
    veri = _json_oku(yol, anahtar)
    if veri is not None:
        return veri
    O = ornek_bos()
    for i in range(adet):
        if dur is not None and dur.is_set():
            return None
        if ilerleme:
            ilerleme(f"{kaynak.program} {kv.trilyon(kaynak.bas)} rastgele pencere orneklemi "
                     f"(ilk seferde birkac dakika)", i, adet)
        rng = random.Random(f"{kaynak.bas}-{ust}-{i}")
        a = rng.randrange(kaynak.bas, max(kaynak.bas + 1, ust - PENCERE))
        b = a + PENCERE
        s = pencere_elegi(a, b)
        asallar = [a + j for j in itertools.compress(range(PENCERE), s)]
        for j, p in enumerate(asallar):
            L = _asal_isle(p, O)
            if j < KONTROL_N:
                O["k_gercek"][L] += 1
                O["k_rastgele"][_kontrol_uzunlugu(p, rng)] += 1
        for _ in range(DUZGUN_N):
            _duzgun_isle(duzgun_asal(rng, max(kaynak.bas, 2), ust), O)
        bilesik = 0
        n = a | 1
        while bilesik < KONTROL_N and n < b:
            if n % 5 and not s[n - a] and n > 1:
                O["k_bilesik"][_kontrol_uzunlugu(n)] += 1
                bilesik += 1
            n += 2
    O["pencere"] = adet
    _json_yaz(yol, anahtar, O)
    return O


def _topla(hedef, kaynak, w):
    if isinstance(kaynak, dict):
        for k, v in kaynak.items():
            if k in hedef:
                hedef[k] = _topla(hedef[k], v, w)
            else:
                hedef[k] = _topla(_sifir(v), v, w)
        return hedef
    if isinstance(kaynak, list):
        return [_topla(h, v, w) for h, v in zip(hedef, kaynak)]
    return hedef + kaynak * w


def _sifir(v):
    if isinstance(v, dict):
        return {k: _sifir(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_sifir(x) for x in v]
    return 0


# ---------------------------------------------------------------- egilim (A / (ln x)^b)

def ln_integral(lo, hi, b, n=8):
    """integral_lo^hi (ln t)^(-b-1) dt  (u = ln t, Simpson)."""
    lo = max(lo, 3.0)
    if hi <= lo:
        return 0.0
    ua, ub = math.log(lo), math.log(hi)
    n = max(n, 2 * int((ub - ua) / 0.1) + 2)
    h = (ub - ua) / n
    s = 0.0
    for i in range(n + 1):
        u = ua + i * h
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        s += w * math.exp(u - (b + 1) * math.log(u))
    return s * h / 3


def egri_oturt(parcalar, gozlenen):
    """Poisson en cok olabilirlik: beklenen_i = A * integral (ln t)^(-b-1) dt.
    parcalar: her dilim icin [(lo, hi)] kapsanan parcalar. Donus: A, b, b_hata."""
    N = sum(gozlenen)
    if N == 0:
        return None

    def profil(b):
        I = [sum(ln_integral(lo, hi, b) for lo, hi in pp) for pp in parcalar]
        A = N / sum(I)
        return sum(o * math.log(A * i) for o, i in zip(gozlenen, I) if o > 0) - N, A

    lo, hi = -2.0, 30.0
    g = (math.sqrt(5) - 1) / 2
    c, d = hi - g * (hi - lo), lo + g * (hi - lo)
    fc, fd = profil(c)[0], profil(d)[0]
    for _ in range(60):
        if fc > fd:
            hi, d, fd = d, c, fc
            c = hi - g * (hi - lo)
            fc = profil(c)[0]
        else:
            lo, c, fc = c, d, fd
            d = lo + g * (hi - lo)
            fd = profil(d)[0]
    b = (lo + hi) / 2
    f0, A = profil(b)
    e = 0.01
    ikinci = (profil(b + e)[0] - 2 * f0 + profil(b - e)[0]) / (e * e)
    hata = 1 / math.sqrt(-ikinci) if ikinci < 0 else float("nan")
    return A, b, hata


def beklenen(A, b, lo, hi):
    return A * ln_integral(lo, hi, b)


def birikimli_konum(A, b, bas, hedef, ust=1e22):
    """bas'tan itibaren beklenen sayinin 'hedef'e ulastigi x (geometrik arama + ikiye bolme)."""
    x, top = bas, 0.0
    while x < ust:
        y = x * 1.1
        e = beklenen(A, b, x, y)
        if top + e >= hedef:
            lo, hi = x, y
            for _ in range(50):
                m = (lo + hi) / 2
                if top + beklenen(A, b, x, m) >= hedef:
                    hi = m
                else:
                    lo = m
            return hi
        top += e
        x = y
    return None


# ---------------------------------------------------------------- KED onimgeleri

def onimge_analizi(lo=10 ** 5, hi=10 ** 6):
    say = Counter(ked(n) for n in range(lo, hi))
    hepsi = Counter(say.values())
    s = elek(hi)
    asal_say = Counter(ked(p) for p in range(lo, hi) if s[p])
    asal = Counter(asal_say.values())
    iki = defaultdict(list)
    for a in range(1, 10):
        for b in range(10):
            iki[10 * a * a + b * b].append(f"{a}{b}")
    ciftler = [(v, ab) for v, ab in sorted(iki.items()) if len(ab) > 1]
    ornek = max(say.items(), key=lambda kv_: kv_[1])
    return {"aralik": (lo, hi), "hepsi": dict(hepsi), "asal": dict(asal), "ciftler": ciftler,
            "en_cok": ornek, "en_cok_onimge": [n for n in range(lo, hi) if ked(n) == ornek[0]][:12]}


def kucuk_rekorlar(ust=2_000_000):
    """Kucuk asallarda her uzunlugun ilk gorundugu asal (tarama kurali: sabit nokta P1)."""
    ilk = {}
    s = elek(ust)
    for p in itertools.compress(range(ust + 1), s):
        L = len(zincir(p)[0])
        if L not in ilk:
            ilk[L] = p
    return ilk


def _dosyadan_ilk(kaynak, uz):
    """Kaynagin en kucuk alt sinirli dolu bolum dosyasindaki en kucuk baslangic."""
    bolum = kaynak.bolum.get(uz, {})
    altlar = sorted(a for a, c in bolum.items() if c)
    if not altlar:
        return None
    uzk = "P21_PLUS" if uz >= 21 else f"P{uz}"
    d = os.path.join(kaynak.klasor, uzk)
    for e in os.scandir(d):
        if e.name.startswith(f"{uzk}_{altlar[0]}_"):
            with open(e.path, encoding="utf-8", errors="replace") as f:
                b = [int(s.split()[1]) for s in f if s.startswith("P")]
            return min(b) if b else None
    return None


# ---------------------------------------------------------------- ana hesap

def hazirla(kaynaklar, dur=None, ilerleme=None):
    """Pahali parcalari (zincir kayitlari, blok ve pencere orneklemi) kaynaklara yukler."""
    for k in kaynaklar:
        if getattr(k, "kayitlar", None) is None:
            k.kayitlar = zincir_kayitlari(k, dur, ilerleme)
            if k.kayitlar is None:
                return False
        if getattr(k, "blok_ornek", None) is None:
            k.blok_ornek = blok_orneklemi(k, k.kayitlar, dur, ilerleme)
            if k.blok_ornek is None:
                return False
        if getattr(k, "pencere_ornek", None) is None:
            k.pencere_ornek = pencere_orneklemi(k, dur, ilerleme)
            if k.pencere_ornek is None:
                return False
    return True


def _q_ortalama(a):
    """adim toplamindan (n, ortalama f[5], standart hata[5], ortalama ln x)."""
    n = a[0]
    if n <= 0:
        return None
    ort = [a[1 + v] / n for v in range(5)]
    se = [math.sqrt(max(0.0, a[6 + v] / n - ort[v] ** 2) / n) for v in range(5)]
    return n, ort, se, a[11] / n


def analiz_et(kaynaklar, ilerleme=None):
    """Secili (cakismayan) kaynaklardan butun analiz sonuclarini tek sozlukte dondurur."""
    R = {}
    kaynaklar = sorted(kaynaklar, key=lambda k: k.bas)
    R["aralik"] = (min(k.bas for k in kaynaklar), max(k.sinir for k in kaynaklar))
    P = [0] * 22
    for k in kaynaklar:
        for i, a in enumerate(kv.SAYAC_ANAHTARLARI):
            P[i + 1] += k.sayac[a]
    asal = sum(k.asal for k in kaynaklar)
    kmax = max([i for i in range(1, 22) if P[i]] or [1])
    Nge = [sum(P[i:]) for i in range(23)]
    R.update(P=P, asal=asal, kmax=kmax, Nge=Nge)

    # --- orneklemleri birlestir (pencere: kaynak asal sayisiyla agirlikli; ham: agirliksiz)
    Ow, Ou = ornek_bos(), ornek_bos()
    for k in kaynaklar:
        O = k.pencere_ornek
        if O["n"]:
            _topla(Ow, O, k.asal / O["n"])
            _topla(Ou, O, 1)
    B = {"adim": {"6": _adim_bos(), "7": _adim_bos()}, "ge": {"6": 0, "7": 0, "8": 0}}
    for k in kaynaklar:
        _topla(B, k.blok_ornek, 1)
    kayit = [r for k in kaynaklar for r in k.kayitlar]
    R["kayit_sayisi"] = len(kayit)
    R["kayit_yanlis"] = sum(1 for r in kayit if not r[4])
    R["ornek_n"] = Ou["n"]
    R["pencere"] = sum(k.pencere_ornek.get("pencere", 0) for k in kaynaklar)

    # --- adim bazinda model q_k
    adim_kayit = defaultdict(_adim_bos)
    terimler = {}
    for b, L, *_ in kayit:
        t = [b]
        for _ in range(L):
            t.append(ked(t[-1]))         # son eleman = sonlayan bilesik
        terimler[b] = t
        for kk in range(8, L + 1):
            _adim_ekle(adim_kayit[kk], t[kk])
    qmodel = {}
    for kk in range(1, kmax + 1):
        if kk <= 5:
            ham = Ou["adim"][kk][0]
            if ham < 30:
                continue
            r = _q_ortalama(Ow["adim"][kk])
            r_ham = _q_ortalama(Ou["adim"][kk])
            qmodel[kk] = (ham, r[1], r_ham[2], r[3], "pencere orneklemi")
        elif kk <= 7:
            r = _q_ortalama(B["adim"][str(kk)])
            if r:
                qmodel[kk] = (r[0], r[1], r[2], r[3], f"P6/P7 blok orneklemi (1/{BLOK_ADIM})")
        else:
            r = _q_ortalama(adim_kayit[kk])
            if r:
                qmodel[kk] = (r[0], r[1], r[2], r[3], "P8+ dosyalarinin tamami")
    R["qmodel"] = qmodel
    qgoz = {}
    for kk in range(1, kmax + 1):
        if Nge[kk]:
            qgoz[kk] = (Nge[kk + 1], Nge[kk]) + wilson(Nge[kk + 1], Nge[kk])
    R["qgoz"] = qgoz

    # --- beklenen P(k+1)/Pk
    oran = {}
    for kk in range(1, kmax):
        if kk in qmodel and kk + 1 in qmodel:
            oran[kk] = [qmodel[kk][1][v] * (1 - qmodel[kk + 1][1][v]) / (1 - qmodel[kk][1][v])
                        if qmodel[kk][1][v] < 1 else None for v in range(5)]
    R["oran_model"] = oran
    R["oran_goz"] = {kk: P[kk + 1] / P[kk] for kk in range(1, kmax) if P[kk]}

    # --- hafiza: gozlenen / model orani ve homojenlik
    hafiza = {}
    for v in range(5):
        satir = {}
        for kk, (n, ort, se, _, _) in qmodel.items():
            if kk not in qgoz or ort[v] <= 0 or n < 30:      # cok az ornekli adimlar disarida
                continue
            q, lo, hi = qgoz[kk][2:]
            r = q / ort[v]
            rel = math.sqrt(((hi - lo) / 3.92 / max(q, 1e-12)) ** 2 + (se[v] / ort[v]) ** 2)
            satir[kk] = (r, r * rel)
        if len(satir) >= 2:
            w = {kk: 1 / s ** 2 for kk, (r, s) in satir.items() if s > 0}
            rbar = sum(satir[kk][0] * w[kk] for kk in w) / sum(w.values())
            chi = sum((satir[kk][0] - rbar) ** 2 * w[kk] for kk in w)
            hafiza[v] = {"oran": satir, "ort": rbar, "chi": chi, "sd": len(w) - 1,
                         "p": ki_kare_p(chi, len(w) - 1)}
    R["hafiza"] = hafiza

    # --- rakam yapisi
    rak8 = [0] * 10
    ilk8 = [0] * 10
    oran8 = [0] * ORAN_N
    r01_8 = defaultdict(lambda: [0] * 24)
    for b, L, *_ in kayit:
        s = str(b)
        for d in range(10):
            rak8[d] += s[:-1].count(chr(48 + d))
        ilk8[ord(s[0]) - 48] += 1
        x = terimler[b][1]
        oran8[min(ORAN_N - 1, max(0, int(math.log10(x / b) / ORAN_BIN)))] += 1
        alt = s[ALT_BASAMAK]
        r01_8[L][min(23, alt.count("0") + alt.count("1"))] += 1
    R["rakam"] = {"ornek": Ow["rakam"], "p8": rak8, "ornek_ilk": Ow["ilk_rakam"], "p8_ilk": ilk8,
                  "ornek_oran": Ow["oran"], "p8_oran": oran8,
                  "ornek_r01": Ow["r01"], "ornek_r01_ham": Ou["r01"], "p8_r01": dict(r01_8)}
    basamak = {}
    for kk in range(1, 22):
        zz = [terimler[b][kk - 1] for b, L, *_ in kayit if L >= kk]
        if zz:
            dig = sum(len(str(z)) for z in zz) / len(zz)
            buyume = sum(math.log10(terimler[b][kk] / terimler[b][kk - 1])
                         for b, L, *_ in kayit if L >= kk) / len(zz)
            basamak[kk] = (len(zz), dig, buyume)
    R["basamak_p8"] = basamak
    R["basamak_ornek"] = {kk: Ow["basamak"][kk] / Ow["adim"][kk][0]
                          for kk in range(1, KMAX + 1)
                          if Ou["adim"][kk][0] >= 30 and Ow["adim"][kk][0] > 0}
    # rakam sikligi ki-kare (P8+ ile siradan asal oranlari)
    top8, topo = sum(rak8), sum(Ow["rakam"])
    chi = sum((rak8[d] - top8 * Ow["rakam"][d] / topo) ** 2 / (top8 * Ow["rakam"][d] / topo)
              for d in range(10) if Ow["rakam"][d])
    R["rakam"]["chi"] = (chi, 9, ki_kare_p(chi, 9))

    # --- 3'e gore siniflar
    sinif = []
    for c in range(3):
        h = Ow["sinif3"][c]
        n = sum(h)
        p1, p2 = h[1], h[2]
        fs = Ow["sinif3_f"][c]
        q1 = fs[0] / n if n else 0
        q2 = fs[1] / fs[2] if fs[2] else 0
        model_oran = q1 * (1 - q2) / (1 - q1) if q1 < 1 else 0
        hu = Ou["sinif3"][c]
        sinif.append({"pay": n / Ow["n"] if Ow["n"] else 0, "P2P1": p2 / p1 if p1 else 0,
                      "model": model_oran, "ham": (hu[1], hu[2]),
                      "ge3": sum(h[3:]) / n if n else 0})
    R["sinif3"] = sinif
    m11 = []
    for f in range(2):
        h = Ow["mod11"][f]
        m11.append((sum(h) / Ow["n"] if Ow["n"] else 0, h[2] / h[1] if h[1] else 0,
                    Ou["mod11"][f][1], Ou["mod11"][f][2]))
    R["mod11"] = m11
    ara3 = sum(1 for b, L, *_ in kayit if any(terimler[b][i] % 3 == 0 for i in range(1, L)))
    R["sinif3_p8_ihlal"] = ara3

    # --- egilim: P6..P11 milyarlik bloklardan, P2..P5 tarama toplamlarindan
    kenar = [10 ** 10]
    ust = max(k.sinir for k in kaynaklar)
    while kenar[-1] < ust:
        kenar.append(min(ust, max(kenar[-1] + MILYAR, round(kenar[-1] * 1.25 / MILYAR) * MILYAR)))
    dilimler = list(zip(kenar[:-1], kenar[1:]))

    def kapsam(lo, hi):
        return [(max(lo, k.bas), min(hi, k.sinir)) for k in kaynaklar
                if min(hi, k.sinir) > max(lo, k.bas)]

    dparca = [kapsam(lo, hi) for lo, hi in dilimler]
    dasal = [sum(kv.asal_tahmini(a, b) for a, b in pp) for pp in dparca]
    blok_say = {}
    for uz in range(6, 22):
        d = [0] * len(dilimler)
        for k in kaynaklar:
            for alt, c in k.bolum.get(uz, {}).items():
                x = alt // MILYAR * MILYAR
                if x >= kenar[0]:
                    d[min(len(d) - 1, bisect_right(kenar, x) - 1)] += c
        blok_say[uz] = d
    egilim = {}
    for uz in range(6, 12):
        if sum(blok_say.get(uz, [])):
            r = egri_oturt(dparca, blok_say[uz])
            if r:
                egilim[uz] = r
    buyuk = [k for k in kaynaklar if k.bas >= 10 ** 12]
    for uz in range(2, 6):
        r = egri_oturt([[(k.bas, k.sinir)] for k in buyuk], [k.sayac[f"P{uz}"] for k in buyuk])
        if r:
            egilim[uz] = r
    ge = {}
    for kk in (8, 9, 10):
        say = [sum(blok_say[u][i] for u in range(kk, 22)) for i in range(len(dilimler))]
        ge[kk] = egri_oturt(dparca, say)
    R["egilim"] = {"dilimler": dilimler, "asal": dasal, "say": blok_say, "fit": egilim, "ge": ge,
                   "kaynak": [(k.bas, k.sinir, k.asal, [k.sayac[f"P{u}"] for u in range(1, 6)])
                              for k in buyuk]}
    # k >= 10 icin zincirleme uzanti (P10/P11 egrileri az olayla oturdugundan):
    # oran_k(x) = oran_9(x) * [(oran_9/oran_8)(x)]^(k-9) * prod_j lnx_8/lnx_j
    # son carpan: terimler buyudukce uzama olasiligi 1/ln(terim) ile azalir (model V1).
    tahmin = {}
    if 8 in egilim and 9 in egilim:
        A8, b8, _ = egilim[8]
        A9, b9, _ = egilim[9]
        lnx = {kk: v[3] for kk, v in qmodel.items() if 6 <= kk <= 9}
        egim = (lnx[9] - lnx[6]) / 3 if 6 in lnx and 9 in lnx else 1.2
        for kk in range(10, 15):
            n = kk - 9
            S = math.prod(lnx.get(8, 44) / (lnx.get(8, 44) + (j - 8) * egim)
                          for j in range(9, kk))
            tahmin[kk] = (A9 * (A9 / A8) ** n * S, b9 + n * (b9 - b8))
    R["uzanti"] = tahmin
    araliklar = [(ust, 2e15), (2e15, 5e15), (5e15, 1e16), (1e16, 1e17)]
    ongoru = []
    for lo, hi in araliklar:
        sat = {"aralik": (lo, hi), "asal": kv.asal_tahmini(lo, hi)}
        for kk in (10, 11, 12, 13):
            pr = tahmin.get(kk)
            if pr:
                sat[kk] = beklenen(pr[0], pr[1], lo, hi)
        ongoru.append(sat)
    R["ongoru"] = ongoru
    ilk_tahmin = {}
    for kk in range(6, 15):
        pr = egilim.get(kk) if kk <= 9 else tahmin.get(kk)
        if pr:
            ilk_tahmin[kk] = {
                "ilk_1": birikimli_konum(pr[0], pr[1], 1e9, 1.0),
                "sonraki_medyan": birikimli_konum(pr[0], pr[1], ust, math.log(2)),
                "taranan_beklenen": beklenen(pr[0], pr[1], kenar[0], ust)}
    R["ilk_tahmin"] = ilk_tahmin

    # --- birlesen zincirler
    onc = defaultdict(set)              # terim -> onculler
    derinlik = {}
    for b, L, *_ in kayit:
        t = terimler[b]
        for i in range(1, L):
            onc[t[i]].add(t[i - 1])
            derinlik.setdefault(t[i], i + 1)
    birlesme = {x: s for x, s in onc.items() if len(s) > 1}
    ebeveyn = {}

    def bul(x):
        while ebeveyn.get(x, x) != x:
            x = ebeveyn[x]
        return x

    for b, L, *_ in kayit:
        if L >= 2:
            ra, rb = bul(b), bul(terimler[b][1])
            if ra != rb:
                ebeveyn[ra] = rb
        for i in range(1, L - 1):
            ra, rb = bul(terimler[b][i]), bul(terimler[b][i + 1])
            if ra != rb:
                ebeveyn[ra] = rb
    aileler = defaultdict(list)
    for b, L, *_ in kayit:
        aileler[bul(b)].append((b, L))
    bag = {}
    for uz in range(8, 22):
        uzunlar = [b for b, L, *_ in kayit if L == uz]
        if uzunlar:
            ikinci = {terimler[b][1] for b in uzunlar}
            aile = {bul(b) for b in uzunlar}
            bag[uz] = (len(uzunlar), len(ikinci), len(aile))
    buyuk_aile = sorted(aileler.values(), key=lambda a: -len(a))[:8]
    derin = Counter(derinlik[x] for x in birlesme)
    R["birlesme"] = {"dugum": len(birlesme), "bag": bag, "derinlik": dict(derin),
                     "aileler": [sorted(a) for a in buyuk_aile if len(a) > 1],
                     "aile_boyu": dict(Counter(len(a) for a in aileler.values()))}
    # --- kumelenme (>=k baslangiclari, egilimle birim yogunluga donusturulmus)
    kume = {}
    for kk, aile_temsil in itertools.product((8, 9, 10), (False, True)):
        if aile_temsil:       # her birlesen aileden yalniz en kucuk baslangic
            temsil = {}
            for b, L, *_ in kayit:
                if L >= kk and b >= kenar[0]:
                    r = bul(b)
                    temsil[r] = min(temsil.get(r, b), b)
            xs = sorted(temsil.values())
        else:
            xs = sorted(b for b, L, *_ in kayit if L >= kk and b >= kenar[0])
        if len(xs) < 5 or not ge.get(kk):
            continue
        A, bb, _ = ge[kk]
        izgara = [kenar[0] * (1.002 ** i) for i in range(int(math.log(ust / kenar[0]) /
                                                             math.log(1.002)) + 2)]
        lam = [0.0]
        for a, b in zip(izgara[:-1], izgara[1:]):
            lam.append(lam[-1] + beklenen(A, bb, a, b))

        def Lam(x):
            i = min(len(izgara) - 2, max(0, int(math.log(x / kenar[0]) / math.log(1.002))))
            return lam[i] + beklenen(A, bb, izgara[i], x)

        u = [Lam(x) for x in xs]
        bos = [b - a for a, b in zip(u[:-1], u[1:])]
        ort = sum(bos) / len(bos)
        g = sorted(v / ort for v in bos)
        n = len(g)
        D = max(max((i + 1) / n - (1 - math.exp(-v)), (1 - math.exp(-v)) - i / n)
                for i, v in enumerate(g))
        cv = math.sqrt(sum((v - 1) ** 2 for v in g) / n)
        kucuk = sum(1 for v in g if v < 0.01) / n
        # esit beklenenli 20 kutuda dagilim indeksi
        K = 20
        kut = [0] * K
        for v in u:
            kut[min(K - 1, int(v / u[-1] * K))] += 1
        m = len(u) / K
        chi = sum((c - m) ** 2 / m for c in kut)
        kume[(kk, aile_temsil)] = {"n": n, "g": g, "D": D, "p": ks_p(D, n), "cv": cv, "kucuk": kucuk,
                    "chi": chi, "chi_p": ki_kare_p(chi, K - 1), "toplam_beklenen": u[-1]}
    R["kume"] = kume

    # --- rekorlar
    kucuk = kucuk_rekorlar()
    rekor = {}
    for L, p in kucuk.items():
        rekor[L] = (p, "kucuk asal taramasi (Python, ≤ 2.000.000)")
    for uz in range(6, 22):
        for k in kaynaklar:
            if uz in rekor:
                break
            if uz >= 8:
                aday = [b for b, L, *_ in k.kayitlar if L == uz]
                if aday:
                    rekor[uz] = (min(aday), f"{k.program} P{uz} dosyasi")
            elif k.bolum.get(uz):
                b = _dosyadan_ilk(k, uz)
                if b:
                    rekor[uz] = (b, f"{k.program} P{uz} dosyasi")
    R["rekor"] = {L: (p, nereden, zincir(p)[0]) for L, (p, nereden) in sorted(rekor.items())}

    R["onimge"] = onimge_analizi()

    # --- kontrol deneyi
    kont = {}
    for ad in ("k_gercek", "k_bilesik", "k_rastgele"):
        h = Ou[ad]
        n = sum(h)
        kont[ad] = (n, [sum(h[i:]) / n if n else 0 for i in range(KMAX + 2)])
    kont["tarama"] = (asal, [Nge[i] / asal if asal else 0 for i in range(22)])
    R["kontrol"] = kont

    # --- yerel carpanlar (Bateman-Horn tekil serisi benzeri)
    yerel = []
    sonlayan = Counter()
    son_q = [0] * len(YEREL_Q)
    for b, L, *_ in kayit:
        x = terimler[b][L]
        sonlayan[en_kucuk_carpan(x)] += 1
        for i, q in enumerate(YEREL_Q):
            if x % q == 0:
                son_q[i] += 1
    C = 2.5
    for i, q in enumerate(YEREL_Q):
        rp = Ow["yerel_p"][i] / Ow["n"] if Ow["n"] else 0
        rz = Ow["yerel_z"][i] / Ow["yerel_zn"] if Ow["yerel_zn"] else 0
        rs = son_q[i] / len(kayit) if kayit else 0
        C *= (1 - rp) / (1 - 1 / q)
        yerel.append((q, rp, rz, rs, C))
    R["yerel"] = yerel
    R["sonlayan"] = dict(sonlayan)
    return R
