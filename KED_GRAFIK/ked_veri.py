# -*- coding: utf-8 -*-
"""
PATI KED tarama sonuclarini OKUYAN yardimci modul (hicbir sonuc dosyasina yazmaz).

Kaynaklar: <depo>/{KED,KED_GPU,KED_CLANG}/PATI_TARAMALAR/ARALIK_*/
  - PATI_CHECKPOINT.txt : baslangic, bitis, tamamlanan_sinir, P1..P20, P21+, asal_toplami
  - SAYACLAR.txt        : ayni sayaclarin ekran ozeti (dogrulama icin okunur)
  - P6..P20, P21_PLUS   : 1 milyarlik bolum basina zincir tablolari (Pk_<alt>_<ust>.txt)

P6/P7 klasorlerinde yuz binlerce dosya olabildiginden bolum basina zincir adetleri
KED_GRAFIK/ONBELLEK altinda TXT olarak saklanir; dosya boyutu degismediyse yeniden okunmaz.
"""
import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

PROGRAMLAR = ("KED", "KED_GPU", "KED_CLANG")
UZUNLUK_KLASORLERI = [f"P{k}" for k in range(6, 21)] + ["P21_PLUS"]
SAYAC_ANAHTARLARI = [f"P{k}" for k in range(1, 21)] + ["P21+"]
KONUM_ESIGI = 10            # bu uzunluk ve ustu zincirlerin baslangic konumlari da tutulur
DOSYA_RE = re.compile(r"_(\d+)_(\d+)\.txt$")

BU_KLASOR = os.path.dirname(os.path.abspath(__file__))
DEPO = os.path.dirname(BU_KLASOR)
ONBELLEK = os.path.join(BU_KLASOR, "ONBELLEK")


def nokta(n):
    """12345678 -> '12.345.678'"""
    return f"{int(n):,}".replace(",", ".")


def trilyon(x):
    t = x / 1e12
    s = f"{t:.3f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") + "T"


def klasor_uzunlugu(ad):
    return 21 if ad == "P21_PLUS" else int(ad[1:])


def anahtar_degerleri(yol):
    """'anahtar = deger' satirlarini sozluge cevirir."""
    d = {}
    with open(yol, encoding="utf-8", errors="replace") as f:
        for satir in f:
            if satir.startswith("#") or "=" not in satir:
                continue
            k, v = satir.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def sayaclar_oku(yol):
    """SAYACLAR.txt icindeki 'P6    =   323.462' ve 'Asal toplami = ...' satirlari."""
    d = {}
    if not os.path.exists(yol):
        return d
    with open(yol, encoding="utf-8", errors="replace") as f:
        for satir in f:
            if "=" not in satir:
                continue
            k, v = satir.split("=", 1)
            k, v = k.strip(), v.strip().replace(".", "")
            if (k in SAYAC_ANAHTARLARI or k == "Asal toplami") and v.isdigit():
                d["asal_toplami" if k == "Asal toplami" else k] = int(v)
    return d


def li(x):
    """Logaritmik integral li(x), Ramanujan serisi (x >= 2)."""
    L = math.log(x)
    toplam, terim, ic = 0.0, 1.0, 0.0
    for n in range(1, 400):
        terim *= L / n                      # L^n / n!
        if n % 2:
            ic += 1 / n                     # sum 1/(2k+1), k <= (n-1)/2
        parca = terim / 2 ** (n - 1) * ic
        toplam += parca if n % 2 else -parca
        if n > 2 * L and abs(parca) < 1e-17 * abs(toplam):
            break
    return 0.5772156649015329 + math.log(L) + math.sqrt(x) * toplam


def asal_tahmini(a, b):
    """[a, b) icindeki asal sayisi tahmini: li(b) - li(a) = integral dt/ln t. 10^13 olceginde
    gercek degerden sapma milyonda birin altindadir (Dogrulama sekmesinde gosterilir).
    Tarama 1'den baslayabilir: t < 2 bolgesinde asal yoktur (ln 1 = 0 bolmesi olmaz)."""
    a = max(a, 2)
    if b <= a:
        return 0.0
    return li(b) - li(a)


class Kaynak:
    """Bir ARALIK_* klasoru."""

    def __init__(self, program, klasor):
        self.program = program
        self.klasor = klasor
        self.ad = os.path.basename(klasor)
        ck = anahtar_degerleri(os.path.join(klasor, "PATI_CHECKPOINT.txt"))
        self.bas = int(ck["baslangic"])
        self.bit = int(ck["bitis"])
        self.sinir = int(ck.get("tamamlanan_sinir", self.bas))
        self.sayac = {k: int(ck.get(k, 0)) for k in SAYAC_ANAHTARLARI}
        self.asal = int(ck.get("asal_toplami", 0))
        self.ozet = sayaclar_oku(os.path.join(klasor, "SAYACLAR.txt"))
        # dosyalardan doldurulanlar
        self.bolum = {}     # uzunluk -> {bolum_alt: adet}   (yalniz ust <= sinir)
        self.konum = []     # (baslangic, uzunluk) uzunluk >= KONUM_ESIGI
        self.yuklendi = False

    @property
    def tamam(self):
        return self.sinir >= self.bit

    @property
    def oran(self):
        return (self.sinir - self.bas) / (self.bit - self.bas)

    @property
    def kimlik(self):
        return f"{self.program}/{self.ad}"

    def etiket(self):
        durum = "tamam" if self.tamam else f"%{self.oran * 100:.2f} (sinir {trilyon(self.sinir)})"
        return f"{self.program}  {trilyon(self.bas)} – {trilyon(self.bit)}  [{durum}]"

    def dosya_toplami(self, uz):
        return sum(self.bolum.get(uz, {}).values())


def kaynaklari_bul():
    bulunan = []
    for prog in PROGRAMLAR:
        kok = os.path.join(DEPO, prog, "PATI_TARAMALAR")
        if not os.path.isdir(kok):
            continue
        for e in sorted(os.scandir(kok), key=lambda e: e.name):
            if e.is_dir() and e.name.startswith("ARALIK_") and \
                    os.path.exists(os.path.join(e.path, "PATI_CHECKPOINT.txt")):
                try:
                    bulunan.append(Kaynak(prog, e.path))
                except (KeyError, ValueError):
                    pass
    bulunan.sort(key=lambda k: (k.bas, k.bit, k.program))
    return bulunan


def varsayilan_secim(kaynaklar):
    """Tamamlanmis ve birbiriyle cakismayan kaynaklar (ayni aralik iki programda varsa ilki)."""
    secili = []
    for k in sorted(kaynaklar, key=lambda k: -(k.sinir - k.bas)):
        if k.tamam and not any(k.bas < s.sinir and s.bas < k.sinir for s in secili):
            secili.append(k)
    return {k.kimlik for k in secili}


def birlesik_kaynaklar(secili):
    """Secili kaynaklardan kapsami cakismayanlar; cakisanlar ayrica dondurulur."""
    alinan, atilan = [], []
    for k in sorted(secili, key=lambda k: -(k.sinir - k.bas)):
        if any(k.bas < s.sinir and s.bas < k.sinir for s in alinan):
            atilan.append(k)
        else:
            alinan.append(k)
    alinan.sort(key=lambda k: k.bas)
    return alinan, atilan


# ---------------------------------------------------------------- dosya okuma

def _adet_say(yol):
    with open(yol, "rb") as f:
        b = f.read()
    return b.count(b"\nP") + (1 if b.startswith(b"P") else 0)


def _konum_oku(yol):
    out = []
    with open(yol, encoding="utf-8", errors="replace") as f:
        for satir in f:
            if satir.startswith("P"):
                p = satir.split()
                uz = int(p[0][1:]) if p[0][1:].isdigit() else 21
                out.append((int(p[1]), uz))
    return out


def _onbellek_yolu(kaynak, uzk):
    return os.path.join(ONBELLEK, f"{kaynak.program}__{kaynak.ad}__{uzk}.txt")


def _onbellek_oku(yol):
    d = {}
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            for satir in f:
                p = satir.split()
                if len(p) == 3 and not satir.startswith("#"):
                    d[p[0]] = (int(p[1]), int(p[2]))
    return d


def _onbellek_yaz(yol, d):
    os.makedirs(ONBELLEK, exist_ok=True)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        f.write("# KED_GRAFIK onbellegi: dosya boyut adet (silinebilir, yeniden olusur)\n")
        for ad in sorted(d):
            f.write(f"{ad} {d[ad][0]} {d[ad][1]}\n")
    os.replace(gecici, yol)


def kaynak_yukle(kaynak, ilerleme=None, dur=None, isci=16):
    """Bolum dosyalarindan uzunluk basina konum dagilimini cikarir.
    ilerleme(metin, yapilan, toplam) arka plandan cagrilir."""
    bolum, konum = {}, []
    for uzk in UZUNLUK_KLASORLERI:
        if dur is not None and dur.is_set():
            return False
        d = os.path.join(kaynak.klasor, uzk)
        uz = klasor_uzunlugu(uzk)
        sayim = {}
        if os.path.isdir(d):
            girdiler = []
            for e in os.scandir(d):
                m = DOSYA_RE.search(e.name)
                if m and int(m.group(2)) <= kaynak.sinir:
                    girdiler.append((e.name, e.path, e.stat().st_size, int(m.group(1))))
            obyol = _onbellek_yolu(kaynak, uzk)
            eski = _onbellek_oku(obyol)
            yeni = {}
            okunacak = []
            for ad, yol, boyut, alt in girdiler:
                o = eski.get(ad)
                if o and o[0] == boyut:
                    yeni[ad] = o
                    sayim[alt] = o[1]
                else:
                    okunacak.append((ad, yol, boyut, alt))
            if okunacak:
                metin = f"{kaynak.program} {trilyon(kaynak.bas)}–{trilyon(kaynak.bit)} {uzk}"
                yapilan = 0
                kilit = threading.Lock()

                def is_(g):
                    nonlocal yapilan
                    if dur is not None and dur.is_set():
                        return g, None
                    n = _adet_say(g[1])
                    with kilit:
                        yapilan += 1
                        if ilerleme and (yapilan % 500 == 0 or yapilan == len(okunacak)):
                            ilerleme(metin, yapilan, len(okunacak))
                    return g, n

                with ThreadPoolExecutor(isci) as ex:
                    for g, n in ex.map(is_, okunacak, chunksize=64):
                        if n is None:
                            return False
                        yeni[g[0]] = (g[2], n)
                        sayim[g[3]] = n
            if okunacak or len(eski) != len(yeni):
                _onbellek_yaz(obyol, yeni)
            if uz >= KONUM_ESIGI:
                for ad, yol, boyut, alt in girdiler:
                    konum.extend(_konum_oku(yol))
        bolum[uz] = sayim
    kaynak.bolum = bolum
    kaynak.konum = sorted(konum)
    kaynak.yuklendi = True
    return True


# ---------------------------------------------------------------- hesaplar

def dilim_yogunlugu(kaynaklar, genislik, uzunluklar):
    """Sayi dogrusunu `genislik` boyunda dilimlere boler.
    Donus: dilim_alt listesi, {uz: [adet]}, [kapsanan uzunluk], [tahmini asal]"""
    if not kaynaklar:
        return [], {}, [], []
    alt = min(k.bas for k in kaynaklar) // genislik * genislik
    ust = max(k.sinir for k in kaynaklar)
    n = max(1, -(-(ust - alt) // genislik))
    dilimler = [alt + i * genislik for i in range(n)]
    adet = {uz: [0] * n for uz in uzunluklar}
    kapsam = [0] * n
    asal = [0.0] * n
    for k in kaynaklar:
        for i, d in enumerate(dilimler):
            a, b = max(d, k.bas), min(d + genislik, k.sinir)
            if b > a:
                kapsam[i] += b - a
                asal[i] += asal_tahmini(a, b)
        for uz in uzunluklar:
            dizi = adet[uz]
            for bolum_alt, c in k.bolum.get(uz, {}).items():
                dizi[(bolum_alt - alt) // genislik] += c
    return dilimler, adet, kapsam, asal
