# -*- coding: utf-8 -*-
"""
PATI KED GRAFIK - tarama sonuclarini grafiklerle gosteren pencereli program.

Yalnizca OKUR: KED, KED_GPU ve KED_CLANG altindaki PATI_TARAMALAR/ARALIK_* klasorleri.
Grafikler saf tkinter Canvas ile cizilir (ek kutuphane gerekmez).
"""
import math
import queue
import threading
import tkinter as tk
import traceback
from tkinter import ttk

import ked_analiz as ka
import ked_veri as kv
from ked_aciklama import ACIKLAMA, KAYNAKCA

RENKLER = ["#2a6fdb", "#e0612b", "#1a9e5c", "#b8338f", "#c9a400", "#6b4fd8",
           "#0d9aa8", "#8a5a2b", "#d43d51", "#5d6b7a"]
UZUN_RENK = {6: "#2a6fdb", 7: "#1a9e5c", 8: "#c9a400", 9: "#e0612b", 10: "#d43d51",
             11: "#6b4fd8", 12: "#0d9aa8", 13: "#8a5a2b"}
VARYANT_RENK = ["#999999", "#2a6fdb", "#1a9e5c", "#e0612b", "#6b4fd8"]
UST = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def sayi_yaz(v):
    if v == 0:
        return "0"
    if abs(v) >= 1 and float(v).is_integer():
        return kv.nokta(v)
    if abs(v) >= 100:
        return kv.nokta(round(v))
    if abs(v) >= 0.01:
        return f"{v:.3g}".replace(".", ",")
    return f"{v:.2e}".replace(".", ",")


def konum_yaz(x):
    """Sayi dogrusunda konum: 1 trilyonun altinda tam sayi, ustunde trilyon."""
    if x is None:
        return "-"
    return kv.nokta(round(x)) if x < 1e12 else kv.trilyon(x)


def us_yaz(k):
    if 0 <= k <= 6:
        return kv.nokta(10 ** k)
    return "10" + str(k).translate(UST)


def guzel_adimlar(lo, hi, n=6):
    if hi <= lo:
        hi = lo + 1
    ham = (hi - lo) / n
    us = 10 ** math.floor(math.log10(ham))
    for c in (1, 2, 2.5, 5, 10):
        if c * us >= ham:
            adim = c * us
            break
    bas = math.floor(lo / adim) * adim
    out = []
    x = bas
    while x <= hi + adim * 1e-9:
        if x >= lo - adim * 1e-9:
            out.append(x)
        x += adim
    return out


class Grafik(tk.Canvas):
    """Basit cizim alani: gruplu cubuk ve cizgi grafikleri, log eksen, ipucu."""

    def __init__(self, ust, **kw):
        super().__init__(ust, bg="white", highlightthickness=0, **kw)
        self.cizici = None
        self.noktalar = []      # (x, y, metin) ipucu icin
        self.bind("<Configure>", lambda e: self.yeniden())
        self.bind("<Motion>", self._hareket)
        self.bind("<Leave>", lambda e: self.delete("ipucu"))

    def ayarla(self, cizici):
        self.cizici = cizici
        self.yeniden()

    def yeniden(self):
        self.delete("all")
        self.noktalar = []
        if self.cizici:
            self.cizici(self)

    def _hareket(self, e):
        self.delete("ipucu")
        if not self.noktalar:
            return
        en = min(self.noktalar, key=lambda p: (p[0] - e.x) ** 2 + (p[1] - e.y) ** 2)
        if (en[0] - e.x) ** 2 + (en[1] - e.y) ** 2 > 400:
            return
        x = min(e.x + 14, self.winfo_width() - 10)
        t = self.create_text(x, e.y - 12, text=en[2], anchor="sw" if x == e.x + 14 else "se",
                             font=("Segoe UI", 9), tags="ipucu")
        b = self.bbox(t)
        r = self.create_rectangle(b[0] - 5, b[1] - 3, b[2] + 5, b[3] + 3, fill="#fffbe6",
                                  outline="#888", tags="ipucu")
        self.tag_raise(t, r)

    # ---------------------------------------------------- eksen yardimcilari
    def cerceve(self, baslik, ylog, ymin, ymax, ybaslik, sol=84, alt=56):
        W, H = max(self.winfo_width(), 300), max(self.winfo_height(), 200)
        x0, x1, y0, y1 = sol, W - 24, 48, H - alt
        if ylog and ymax / ymin < 30:      # tek onluga sigan veride log eksen okunmaz
            ylog = False
        self.create_text(W / 2, 18, text=baslik, font=("Segoe UI", 12, "bold"))
        if ylog:
            lo = math.log10(ymin) - 0.25
            hi = math.ceil(math.log10(ymax))
            if hi == lo:
                hi += 1
            donus = lambda v: y1 - (math.log10(v) - lo) / (hi - lo) * (y1 - y0)
            for k in range(math.ceil(lo), hi + 1):
                y = donus(10 ** k)
                self.create_line(x0, y, x1, y, fill="#e4e4e4")
                self.create_text(x0 - 6, y, text=us_yaz(k), anchor="e", font=("Segoe UI", 9))
        else:
            hi = ymax * 1.08 if ymax > 0 else 1
            donus = lambda v: y1 - v / hi * (y1 - y0)
            for v in guzel_adimlar(0, hi):
                y = donus(v)
                self.create_line(x0, y, x1, y, fill="#e4e4e4")
                self.create_text(x0 - 6, y, text=sayi_yaz(v), anchor="e", font=("Segoe UI", 9))
        self.create_line(x0, y1, x1, y1, fill="#444")
        self.create_line(x0, y0, x0, y1, fill="#444")
        self.create_text(16, (y0 + y1) / 2, text=ybaslik, angle=90, font=("Segoe UI", 9))
        return x0, x1, y0, y1, donus

    def gosterge(self, ogeler, x1, y0):
        y = y0 + 4
        for ad, renk in ogeler:
            self.create_rectangle(x1 - 14, y, x1 - 4, y + 10, fill=renk, outline="")
            self.create_text(x1 - 20, y + 5, text=ad, anchor="e", font=("Segoe UI", 9))
            y += 16

    def bos(self, metin):
        W, H = self.winfo_width(), self.winfo_height()
        self.create_text(W / 2, H / 2, text=metin, font=("Segoe UI", 11), fill="#777",
                         justify="center")

    # ---------------------------------------------------- cizim turleri
    def cubuklar(self, baslik, kategoriler, seriler, ylog=True, ybaslik="", etiket=True):
        """seriler: [(ad, renk, [deger...])]"""
        degerler = [v for _, _, ds in seriler for v in ds if v > 0]
        if not degerler:
            return self.bos("Gosterilecek veri yok")
        x0, x1, y0, y1, Y = self.cerceve(baslik, ylog, min(degerler), max(degerler), ybaslik)
        n, m = len(kategoriler), len(seriler)
        grup = (x1 - x0) / n
        gen = grup * 0.8 / m
        for i, kat in enumerate(kategoriler):
            gx = x0 + i * grup + grup * 0.1
            self.create_text(x0 + (i + 0.5) * grup, y1 + 12, text=kat, font=("Segoe UI", 9))
            for j, (ad, renk, ds) in enumerate(seriler):
                v = ds[i]
                bx = gx + j * gen
                if v > 0:
                    yt = Y(v)
                    self.create_rectangle(bx, yt, bx + gen - 1, y1, fill=renk, outline="")
                    self.noktalar.append((bx + gen / 2, yt, f"{ad} · {kat}: {sayi_yaz(v)}"))
                    if etiket and gen >= 30:
                        self.create_text(bx + gen / 2, yt - 3, text=sayi_yaz(v), anchor="s",
                                         font=("Segoe UI", 7), angle=0 if gen >= 70 else 90)
                elif etiket:
                    self.create_text(bx + gen / 2, y1 - 3, text="0", anchor="s",
                                     font=("Segoe UI", 7), fill="#999")
        if m > 1:
            self.gosterge([(a, r) for a, r, _ in seriler], x1, y0)

    def cizgiler(self, baslik, seriler, ylog=True, ybaslik="", xbaslik="", xmin=None, xmax=None,
                 xetiket=sayi_yaz, isaretler=(), kategorik=None):
        """seriler: [(ad, renk, xs, ys, ipucu_listesi_ya_da_None[, stil])]; kategorik: x etiketleri.
        stil: {"kesik": bool, "nokta": bool, "cizgi": bool}; '_' ile baslayan ad gostergede yok."""
        ys = [y for s in seriler for y in s[3] if y is not None and y > 0]
        if not ys:
            return self.bos("Gosterilecek veri yok")
        x0, x1, y0, y1, Y = self.cerceve(baslik, ylog, min(ys), max(ys), ybaslik)
        xs_hepsi = [x for s in seriler for x in s[2]]
        xa = min(xs_hepsi) if xmin is None else xmin
        xb = max(xs_hepsi) if xmax is None else xmax
        if xb == xa:
            xb = xa + 1
        X = lambda v: x0 + (v - xa) / (xb - xa) * (x1 - x0)
        if kategorik:
            for i, k in enumerate(kategorik):
                self.create_text(X(i), y1 + 12, text=k, font=("Segoe UI", 9))
        else:
            for v in guzel_adimlar(xa, xb, 10):
                self.create_line(X(v), y1, X(v), y1 + 4, fill="#444")
                self.create_text(X(v), y1 + 12, text=xetiket(v), font=("Segoe UI", 9))
        self.create_text((x0 + x1) / 2, y1 + 34, text=xbaslik, font=("Segoe UI", 9))
        for ad, renk, xs, vs, ipuclari, *stil in seriler:
            stil = stil[0] if stil else {}
            kesik = stil.get("kesik", ad.startswith("Birlesik"))
            onceki = None
            for i, (x, v) in enumerate(zip(xs, vs)):
                if v is None or v <= 0:
                    onceki = None
                    continue
                p = (X(x), Y(v))
                if onceki and stil.get("cizgi", True):
                    self.create_line(*onceki, *p, fill=renk, width=2,
                                     dash=(6, 4) if kesik else None)
                if stil.get("nokta", len(xs) <= 60):
                    self.create_oval(p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3, fill=renk,
                                     outline="")
                self.noktalar.append((p[0], p[1], ipuclari[i] if ipuclari else
                                      f"{ad}: {sayi_yaz(v)}"))
                onceki = p
        for x, renk, metin in isaretler:
            px = X(x)
            self.create_polygon(px, y1 - 9, px - 4, y1 - 1, px + 4, y1 - 1, fill=renk, outline="")
            self.noktalar.append((px, y1 - 5, metin))
        self.gosterge([(s[0], s[1]) for s in seriler if not s[0].startswith("_")], x1, y0)


class Uygulama:
    def __init__(self, kok):
        self.kok = kok
        kok.title("PATI KED GRAFIK – zincir dagilimlari")
        kok.geometry("1280x820")
        kok.minsize(900, 600)
        self.kuyruk = queue.Queue()
        self.dur = threading.Event()
        self.kaynaklar = []
        self.secim = {}
        self.R = None                   # analiz sonuclari (ked_analiz.analiz_et)
        self.analiz_anahtar = None      # R'nin hesaplandigi kaynak secimi
        self.analiz_calisan = None
        self.yukleme_bitti = False

        ust = ttk.Frame(kok, padding=(8, 6))
        ust.pack(fill="x")
        ttk.Label(ust, text="Taramalar (birlesik grafiklerde kullanilacaklari secin):",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.secim_cerceve = ttk.Frame(ust)
        self.secim_cerceve.pack(fill="x")
        satir = ttk.Frame(ust)
        satir.pack(fill="x", pady=(4, 0))
        ttk.Button(satir, text="Yeniden tara (diskten oku)", command=self.yukle).pack(side="left")
        self.uyari = ttk.Label(satir, text="", foreground="#b00")
        self.uyari.pack(side="left", padx=10)

        self.defter = ttk.Notebook(kok)
        self.defter.pack(fill="both", expand=True, padx=8)
        self._sekme_uzunluk()
        self._sekme_yogunluk()
        self._sekme_oran()
        self._sekme_tablo()
        self._sekme_analizler()

        alt = ttk.Frame(kok, padding=(8, 4))
        alt.pack(fill="x")
        self.durum = ttk.Label(alt, text="")
        self.durum.pack(side="left")
        self.cubuk = ttk.Progressbar(alt, length=260, mode="determinate")
        self.cubuk.pack(side="right")

        kok.protocol("WM_DELETE_WINDOW", self.kapat)
        self.kok.after(100, self._kuyruk_isle)
        self.yukle()

    # ------------------------------------------------------------ sekmeler
    def _secenek_satiri(self, ust):
        f = ttk.Frame(ust, padding=(4, 4))
        f.pack(fill="x")
        return f

    def _sekme_uzunluk(self):
        s = ttk.Frame(self.defter)
        self.defter.add(s, text="Uzunluk dagilimi")
        f = self._secenek_satiri(s)
        self.u_gorunum = tk.StringVar(value="ayri")
        ttk.Radiobutton(f, text="Her tarama ayri", variable=self.u_gorunum, value="ayri",
                        command=self.ciz_uzunluk).pack(side="left")
        ttk.Radiobutton(f, text="Birlesik toplam", variable=self.u_gorunum, value="birlesik",
                        command=self.ciz_uzunluk).pack(side="left", padx=8)
        self.u_log = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Logaritmik", variable=self.u_log,
                        command=self.ciz_uzunluk).pack(side="left", padx=8)
        self.g_uzunluk = Grafik(s)
        self.g_uzunluk.pack(fill="both", expand=True)

    def _sekme_yogunluk(self):
        s = ttk.Frame(self.defter)
        self.defter.add(s, text="Sayi dogrusunda yogunluk")
        f = self._secenek_satiri(s)
        ttk.Label(f, text="Dilim:").pack(side="left")
        self.y_dilim = tk.StringVar(value="5 trilyon")
        cb = ttk.Combobox(f, textvariable=self.y_dilim, width=11, state="readonly",
                          values=["1 trilyon", "2 trilyon", "5 trilyon", "10 trilyon",
                                  "25 trilyon"])
        cb.pack(side="left", padx=(2, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.ciz_yogunluk())
        self.y_olcek = tk.StringVar(value="asal")
        ttk.Radiobutton(f, text="Adet", variable=self.y_olcek, value="adet",
                        command=self.ciz_yogunluk).pack(side="left")
        ttk.Radiobutton(f, text="Milyon asal basina", variable=self.y_olcek, value="asal",
                        command=self.ciz_yogunluk).pack(side="left", padx=4)
        ttk.Radiobutton(f, text="Ortalamaya gore (1 = aralik ortalamasi)",
                        variable=self.y_olcek, value="goreli",
                        command=self.ciz_yogunluk).pack(side="left", padx=4)
        self.y_log = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Logaritmik", variable=self.y_log,
                        command=self.ciz_yogunluk).pack(side="left", padx=8)
        self.y_isaret = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="P10+ konumlari", variable=self.y_isaret,
                        command=self.ciz_yogunluk).pack(side="left", padx=4)
        f2 = self._secenek_satiri(s)
        ttk.Label(f2, text="Uzunluklar:").pack(side="left")
        self.y_uz = {}
        for uz in range(6, 13):
            v = tk.BooleanVar(value=uz <= 11)
            self.y_uz[uz] = v
            ttk.Checkbutton(f2, text=f"P{uz}", variable=v,
                            command=self.ciz_yogunluk).pack(side="left", padx=3)
        self.g_yogunluk = Grafik(s)
        self.g_yogunluk.pack(fill="both", expand=True)

    def _sekme_oran(self):
        s = ttk.Frame(self.defter)
        self.defter.add(s, text="Asal basina oranlar / karsilastirma")
        f = self._secenek_satiri(s)
        self.o_tur = tk.StringVar(value="asal")
        ttk.Radiobutton(f, text="Pk / asal sayisi (milyon asal basina)", variable=self.o_tur,
                        value="asal", command=self.ciz_oran).pack(side="left")
        ttk.Radiobutton(f, text="Uzama orani P(k+1) / Pk", variable=self.o_tur, value="uzama",
                        command=self.ciz_oran).pack(side="left", padx=8)
        ttk.Radiobutton(f, text="En az k uzunlukta (≥Pk) / asal", variable=self.o_tur,
                        value="kumulatif", command=self.ciz_oran).pack(side="left", padx=8)
        self.g_oran = Grafik(s)
        self.g_oran.pack(fill="both", expand=True)

    def _sekme_tablo(self):
        s = ttk.Frame(self.defter)
        self.defter.add(s, text="Tablo ve dogrulama")
        self.tablo = ttk.Treeview(s, show="headings")
        self.tablo.pack(fill="both", expand=True, padx=4, pady=4)
        self.not_metni = tk.Text(s, height=9, font=("Consolas", 9), wrap="word")
        self.not_metni.pack(fill="x", padx=4, pady=(0, 4))

    # ------------------------------------------------------------ yukleme
    def yukle(self):
        self.dur.set()
        self.dur = threading.Event()
        self.yukleme_bitti = False
        self.analiz_anahtar = self.analiz_calisan = None
        self.kaynaklar = kv.kaynaklari_bul()
        varsayilan = kv.varsayilan_secim(self.kaynaklar)
        for w in self.secim_cerceve.winfo_children():
            w.destroy()
        eski = {k: v.get() for k, v in self.secim.items()}
        self.secim = {}
        for i, k in enumerate(self.kaynaklar):
            v = tk.BooleanVar(value=eski.get(k.kimlik, k.kimlik in varsayilan))
            self.secim[k.kimlik] = v
            renk = RENKLER[i % len(RENKLER)]
            satir = ttk.Frame(self.secim_cerceve)
            satir.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 24))
            tk.Label(satir, bg=renk, width=2).pack(side="left", padx=(0, 4))
            ttk.Checkbutton(satir, text=k.etiket(), variable=v,
                            command=self.hepsini_ciz).pack(side="left")
        for i, k in enumerate(self.kaynaklar):
            k.renk = RENKLER[i % len(RENKLER)]
        self.hepsini_ciz()
        dur = self.dur
        threading.Thread(target=self._arka_plan, args=(list(self.kaynaklar), dur),
                         daemon=True).start()

    def _arka_plan(self, kaynaklar, dur):
        for k in kaynaklar:
            def ilerleme(metin, yapilan, toplam):
                self.kuyruk.put(("ilerleme", metin, yapilan, toplam))
            self.kuyruk.put(("ilerleme", f"{k.program} {kv.trilyon(k.bas)}–"
                                         f"{kv.trilyon(k.bit)} dosya listesi", 0, 1))
            try:
                if not kv.kaynak_yukle(k, ilerleme, dur):
                    return
            except OSError as e:
                self.kuyruk.put(("hata", f"{k.kimlik}: {e}"))
                continue
            self.kuyruk.put(("kaynak", k))
        self.kuyruk.put(("bitti",))

    def _kuyruk_isle(self):
        try:
            while True:
                m = self.kuyruk.get_nowait()
                if m[0] == "ilerleme":
                    _, metin, yapilan, toplam = m
                    self.durum.config(text=f"Okunuyor: {metin}  {kv.nokta(yapilan)} / "
                                           f"{kv.nokta(toplam)} dosya (ilk okuma uzun surer, "
                                           f"sonra onbellekten gelir)")
                    self.cubuk.config(maximum=max(toplam, 1), value=yapilan)
                elif m[0] == "kaynak":
                    self.hepsini_ciz()
                elif m[0] == "hata":
                    self.uyari.config(text=m[1])
                elif m[0] == "bitti":
                    self.durum.config(text="Tum tarama dosyalari okundu.")
                    self.cubuk.config(value=0)
                    self.yukleme_bitti = True
                    self.hepsini_ciz()
                elif m[0] == "analiz":
                    if m[2] == self.analiz_calisan:
                        self.R, self.analiz_anahtar = m[1], m[2]
                        self.analiz_calisan = None
                        self.durum.config(text="Tum tarama dosyalari okundu; analizler hazir.")
                        self.cubuk.config(value=0)
                        self.analizleri_ciz()
                elif m[0] == "analiz_hata":
                    self.analiz_calisan = None
                    self.uyari.config(text="Analiz hatasi (ayrinti Analizler sekmesinde)")
                    for _, t, _ in self.analiz_sekmeleri.values():
                        self._metin(t, m[1])
        except queue.Empty:
            pass
        self.kok.after(150, self._kuyruk_isle)

    def kapat(self):
        self.dur.set()
        self.kok.destroy()

    # ------------------------------------------------------------ cizimler
    def secili(self):
        return [k for k in self.kaynaklar if self.secim[k.kimlik].get()]

    def birlesik(self):
        alinan, atilan = kv.birlesik_kaynaklar(self.secili())
        if atilan:
            self.uyari.config(text="Cakisan aralik birlesikte kullanilmadi: " +
                                   ", ".join(k.etiket() for k in atilan))
        else:
            self.uyari.config(text="")
        return alinan

    def hepsini_ciz(self):
        self.birlesik()
        self.ciz_uzunluk()
        self.ciz_yogunluk()
        self.ciz_oran()
        self.tablo_doldur()
        self.analiz_baslat()

    def _en_uzun(self, kaynaklar):
        m = 5
        for k in kaynaklar:
            for i, a in enumerate(kv.SAYAC_ANAHTARLARI):
                if k.sayac[a]:
                    m = max(m, i + 1)
        return min(m + 1, 21)

    def _birlesik_sayac(self, kaynaklar):
        say = {a: sum(k.sayac[a] for k in kaynaklar) for a in kv.SAYAC_ANAHTARLARI}
        return say, sum(k.asal for k in kaynaklar)

    def _aralik_adi(self, kaynaklar):
        if not kaynaklar:
            return "-"
        return f"{kv.trilyon(min(k.bas for k in kaynaklar))} – " \
               f"{kv.trilyon(max(k.sinir for k in kaynaklar))}"

    def ciz_uzunluk(self):
        sec = self.birlesik() if self.u_gorunum.get() == "birlesik" else self.secili()
        m = self._en_uzun(sec)
        kat = kv.SAYAC_ANAHTARLARI[:m]

        def cizici(g):
            if not sec:
                return g.bos("Ustten en az bir tarama secin")
            if self.u_gorunum.get() == "birlesik":
                say, _ = self._birlesik_sayac(sec)
                seriler = [(f"Birlesik {self._aralik_adi(sec)}", "#2a6fdb",
                            [say[a] for a in kat])]
            else:
                seriler = [(f"{k.program} {kv.trilyon(k.bas)}–{kv.trilyon(k.sinir)}", k.renk,
                            [k.sayac[a] for a in kat]) for k in sec]
            g.cubuklar("Uzunluga gore zincir sayisi (tam uzunluk Pk)", kat, seriler,
                       ylog=self.u_log.get(), ybaslik="zincir sayisi")
        self.g_uzunluk.ayarla(cizici)

    def ciz_yogunluk(self):
        sec = self.birlesik()
        gen = int(self.y_dilim.get().split()[0]) * 10 ** 12
        uzunluklar = [uz for uz, v in self.y_uz.items() if v.get()]
        olcek = self.y_olcek.get()
        hazir = all(k.yuklendi for k in sec)

        def cizici(g):
            if not sec:
                return g.bos("Ustten en az bir tarama secin")
            if not hazir:
                return g.bos("Bolum dosyalari okunuyor...\n(ilerleme alt satirda; ilk okuma "
                             "P6/P7 icin birkac dakika surebilir)")
            dilimler, adet, kapsam, asal = kv.dilim_yogunlugu(sec, gen, uzunluklar)
            seriler = []
            for uz in uzunluklar:
                xs, ys, ip = [], [], []
                toplam_adet = sum(adet[uz])
                toplam_asal = sum(asal)
                ort = toplam_adet / toplam_asal if toplam_asal else 0
                for d, c, kp, a in zip(dilimler, adet[uz], kapsam, asal):
                    if kp == 0:
                        continue
                    if olcek == "adet":
                        v = c
                    elif olcek == "asal":
                        v = c / a * 1e6
                    else:
                        v = (c / a) / ort if ort else 0
                    xs.append((d + gen / 2) / 1e12)
                    ys.append(v)
                    kis = "" if kp == gen else f" (kapsanan {kv.trilyon(kp)})"
                    ip.append(f"P{uz} · {kv.trilyon(d)}–{kv.trilyon(d + gen)}{kis}\n"
                              f"adet {kv.nokta(c)} · tahmini asal {kv.nokta(round(a))}\n"
                              f"milyon asal basina {sayi_yaz(c / a * 1e6)}")
                seriler.append((f"P{uz} (top. {kv.nokta(toplam_adet)})",
                                UZUN_RENK.get(uz, "#555"), xs, ys, ip))
            isaretler = []
            if self.y_isaret.get():
                for k in sec:
                    for bas, uz in k.konum:
                        isaretler.append((bas / 1e12, UZUN_RENK.get(uz, "#000"),
                                          f"P{uz} baslangic: {kv.nokta(bas)}"))
            yb = {"adet": "dilimdeki zincir sayisi",
                  "asal": "milyon asal basina zincir",
                  "goreli": "dilim orani / genel oran"}[olcek]
            xa = min(k.bas for k in sec) / 1e12
            xb = max(k.sinir for k in sec) / 1e12
            g.cizgiler(f"P6+ zincirlerin sayi dogrusundaki yogunlugu – "
                       f"{self.y_dilim.get()}lik dilimler ({self._aralik_adi(sec)})",
                       seriler, ylog=self.y_log.get(), ybaslik=yb,
                       xbaslik="baslangic asali (trilyon)  ·  ▲ = P10+ zincir baslangici",
                       xmin=xa, xmax=xb, xetiket=lambda v: sayi_yaz(v) + "T",
                       isaretler=isaretler)
        self.g_yogunluk.ayarla(cizici)

    def ciz_oran(self):
        sec = self.secili()
        tur = self.o_tur.get()
        bir = self.birlesik()

        def cizici(g):
            if not sec:
                return g.bos("Ustten en az bir tarama secin")
            m = self._en_uzun(sec)
            kat = kv.SAYAC_ANAHTARLARI[:m]
            liste = [(f"{k.program} {kv.trilyon(k.bas)}–{kv.trilyon(k.sinir)}", k.renk,
                      [k.sayac[a] for a in kv.SAYAC_ANAHTARLARI], k.asal) for k in sec]
            if len(bir) > 1:
                say, asal = self._birlesik_sayac(bir)
                liste.append((f"Birlesik {self._aralik_adi(bir)}", "#222",
                              [say[a] for a in kv.SAYAC_ANAHTARLARI], asal))
            seriler = []
            for ad, renk, ds, asal in liste:
                if tur == "asal":
                    ys = [d / asal * 1e6 for d in ds[:m]]
                    x = list(range(m))
                    ip = [f"{ad}\n{kat[i]}: {kv.nokta(ds[i])} / {kv.nokta(asal)} asal\n"
                          f"= milyon asal basina {sayi_yaz(ys[i])}" for i in x]
                elif tur == "kumulatif":
                    ys = [sum(ds[i:]) / asal for i in range(m)]
                    x = list(range(m))
                    ip = [f"{ad}\n≥{kat[i]}: {kv.nokta(sum(ds[i:]))} / {kv.nokta(asal)}\n"
                          f"= {sayi_yaz(ys[i])}" for i in x]
                else:
                    x = list(range(1, m))
                    ys = [ds[i] / ds[i - 1] if ds[i - 1] else None for i in x]
                    ip = [f"{ad}\n{kat[i]} / {kat[i - 1]} = {kv.nokta(ds[i])} / "
                          f"{kv.nokta(ds[i - 1])}\n= {sayi_yaz(ys[i - 1] or 0)}" for i in x]
                seriler.append((ad, renk, x, ys, ip))
            baslik, yb = {
                "asal": ("Asal basina zincir orani (taramalar arasi karsilastirma)",
                         "milyon asal basina Pk"),
                "kumulatif": ("En az k uzunlukta zincir baslatan asallarin orani",
                              "≥Pk / asal sayisi"),
                "uzama": ("Uzama orani: Pk zincirlerinin P(k+1)'e gore sayisi",
                          "P(k+1) / Pk")}[tur]
            g.cizgiler(baslik, seriler, ylog=True, ybaslik=yb, xbaslik="zincir uzunlugu",
                       xmin=-0.3, xmax=m - 0.7, kategorik=kat)
        self.g_oran.ayarla(cizici)

    def tablo_doldur(self):
        sec = self.secili()
        t = self.tablo
        t.delete(*t.get_children())
        kolonlar = ["uz"]
        for i, k in enumerate(sec):
            kolonlar += [f"s{i}", f"d{i}", f"o{i}"]
        t["columns"] = kolonlar
        t.heading("uz", text="Uzunluk")
        t.column("uz", width=80, anchor="center")
        for i, k in enumerate(sec):
            ad = f"{k.program} {kv.trilyon(k.bas)}–{kv.trilyon(k.sinir)}"
            t.heading(f"s{i}", text=f"{ad} SAYACLAR")
            t.heading(f"d{i}", text="dosyalardan")
            t.heading(f"o{i}", text="milyon asal basina")
            t.column(f"s{i}", width=150, anchor="e")
            t.column(f"d{i}", width=100, anchor="e")
            t.column(f"o{i}", width=110, anchor="e")
        satirlar = [(a, i) for i, a in enumerate(kv.SAYAC_ANAHTARLARI)]
        notlar = []
        for a, i in satirlar + [("Asal", None)]:
            deger = [a]
            for k in sec:
                if i is None:
                    oz = k.ozet.get("asal_toplami", k.asal)
                    deger += [kv.nokta(oz) + ("" if oz == k.asal else " ≠ckp"), "", ""]
                    continue
                oz = k.ozet.get(a, k.sayac[a])
                s = kv.nokta(oz) + ("" if oz == k.sayac[a] else f" ≠ckp {kv.nokta(k.sayac[a])}")
                uz = i + 1
                if uz >= 6 and k.yuklendi:
                    dt = k.dosya_toplami(uz)
                    d = f"{kv.nokta(dt)} {'✓' if dt == k.sayac[a] else '✗'}"
                    if dt != k.sayac[a]:
                        notlar.append(f"✗ {k.kimlik} {a}: checkpoint {kv.nokta(k.sayac[a])}, "
                                      f"dosyalar {kv.nokta(dt)}")
                elif uz >= 6:
                    d = "okunuyor"
                else:
                    d = "-"
                deger += [s, d, sayi_yaz(k.sayac[a] / k.asal * 1e6) if k.asal else "-"]
            t.insert("", "end", values=deger)

        metin = []
        for k in sec:
            tahmin = kv.asal_tahmini(k.bas, k.sinir)
            sapma = (tahmin - k.asal) / k.asal * 1e6 if k.asal else 0
            p6 = sum(k.sayac[a] for a in kv.SAYAC_ANAHTARLARI[5:])
            metin.append(
                f"{k.kimlik}: {kv.nokta(k.bas)} – {kv.nokta(k.sinir)} "
                f"({'tamam' if k.tamam else 'yarim, %' + format(k.oran * 100, '.3f')}); "
                f"P1..P21+ toplami {'=' if sum(k.sayac.values()) == k.asal else '≠'} asal toplami; "
                f"∫dt/ln t asal tahmini {kv.nokta(round(tahmin))} (sapma {sapma:+.2f} ppm); "
                f"P6+ = {kv.nokta(p6)}")
        if notlar:
            metin.append("UYUMSUZLUK:\n" + "\n".join(notlar))
        elif sec and all(k.yuklendi for k in sec):
            metin.append("✓ Tum P6+ uzunluklarda bolum dosyalarindaki satir sayilari "
                         "checkpoint/SAYACLAR ile birebir tutarli.")
        metin.append("Not: P1–P5 icin yalniz aralik toplami kayitli (bolum dagilimi yok); "
                     "yarim taramalarda yalniz tamamlanan_sinir'e kadarki bolum dosyalari sayilir.")
        self.not_metni.config(state="normal")
        self.not_metni.delete("1.0", "end")
        self.not_metni.insert("1.0", "\n".join(metin))
        self.not_metni.config(state="disabled")

    # ------------------------------------------------------------ analizler
    def _sekme_analizler(self):
        s = ttk.Frame(self.defter)
        self.defter.add(s, text="Analizler")
        self.alt_defter = ttk.Notebook(s)
        self.alt_defter.pack(fill="both", expand=True)
        self.analiz_sekmeleri = {}
        self.analiz_secenek = {}
        tanim = [
            ("beklenti", "1 Beklenti modeli", [("oran", "P(k+1)/Pk"),
                                                ("q", "Uzama olasiligi q(k)")]),
            ("hafiza", "2 Hafiza testi", [("3", "Model: + mod 11"), ("4", "Model: elek ≤1000"),
                                          ("2", "Model: + mod 3")]),
            ("rakam", "3 Rakam yapisi", [("siklik", "Rakam sikligi"), ("ilk", "Ilk rakam"),
                                         ("r01", "0 ve 1 rakamlari"), ("oran", "KED(p)/p"),
                                         ("basamak", "Basamak buyumesi")]),
            ("sinif3", "4 3'e gore siniflar", None),
            ("kume", "5 Kumelenme", [("10", "P10+"), ("9", "P9+"), ("8", "P8+")]),
            ("egilim", "6 Egilim ve ongoru", [("blok", "P6–P12 (milyarlik bloklar)"),
                                              ("toplam", "P2–P5 (tarama toplamlari)")]),
            ("rekor", "7 Rekorlar", None),
            ("birlesme", "8 Birlesen zincirler", [("bag", "Bagimsiz zincir sayisi"),
                                                  ("onimge", "KED onimge sayisi")]),
            ("kontrol", "9 Kontrol deneyi", None),
            ("yerel", "10 Yerel carpanlar", None),
        ]
        for anahtar, ad, secenek in tanim:
            self.analiz_sekmeleri[anahtar] = self._alt_sekme(anahtar, ad, secenek)
        s = ttk.Frame(self.alt_defter)
        self.alt_defter.add(s, text="Kaynakca")
        t = tk.Text(s, font=("Consolas", 10), wrap="word")
        t.pack(fill="both", expand=True, padx=4, pady=4)
        self._metin(t, KAYNAKCA)

    def _alt_sekme(self, anahtar, ad, secenek):
        s = ttk.Frame(self.alt_defter)
        self.alt_defter.add(s, text=ad)
        if secenek:
            f = self._secenek_satiri(s)
            v = tk.StringVar(value=secenek[0][0])
            self.analiz_secenek[anahtar] = v
            for deger, metin in secenek:
                ttk.Radiobutton(f, text=metin, variable=v, value=deger,
                                command=lambda a=anahtar: self.analiz_ciz(a)).pack(side="left",
                                                                                   padx=4)
        bol = ttk.PanedWindow(s, orient="vertical")
        bol.pack(fill="both", expand=True)
        tablo = None
        if anahtar == "rekor":
            tablo = ttk.Treeview(bol, show="headings", height=8,
                                 columns=("k", "p", "bas", "nere", "model"))
            for c, baslik, gen in (("k", "Uzunluk", 70), ("p", "Ilk baslangic asali", 170),
                                   ("bas", "Basamak", 70), ("nere", "Nereden", 260),
                                   ("model", "Egilim modelinde 1 beklenen konum", 230)):
                tablo.heading(c, text=baslik)
                tablo.column(c, width=gen, anchor="e" if c != "nere" else "w")
            bol.add(tablo, weight=2)
            self.rekor_tablo = tablo
        g = Grafik(bol)
        bol.add(g, weight=4)
        t = tk.Text(bol, height=11, font=("Consolas", 9), wrap="word")
        bol.add(t, weight=2)
        return g, t, tablo

    @staticmethod
    def _metin(t, s):
        t.config(state="normal")
        t.delete("1.0", "end")
        t.insert("1.0", s)
        t.config(state="disabled")

    def analiz_baslat(self):
        """Yukleme bittiyse ve secim degistiyse analizleri arka planda (yeniden) hesaplar."""
        if not self.yukleme_bitti:
            self.analizleri_ciz()
            return
        alinan = self.birlesik()
        anahtar = tuple(k.kimlik for k in alinan)
        if not alinan or anahtar in (self.analiz_anahtar, self.analiz_calisan):
            self.analizleri_ciz()
            return
        self.analiz_calisan = anahtar
        self.analizleri_ciz()
        dur = self.dur

        def is_():
            def ilerleme(metin, yapilan, toplam):
                self.kuyruk.put(("ilerleme", metin, yapilan, toplam))
            try:
                if not ka.hazirla(alinan, dur, ilerleme):
                    return
                self.kuyruk.put(("ilerleme", "analizler hesaplaniyor", 0, 1))
                self.kuyruk.put(("analiz", ka.analiz_et(alinan), anahtar))
            except Exception:
                self.kuyruk.put(("analiz_hata", "Analiz hesaplanirken hata:\n" +
                                 traceback.format_exc()))

        threading.Thread(target=is_, daemon=True).start()

    def analizleri_ciz(self):
        for a in self.analiz_sekmeleri:
            self.analiz_ciz(a)

    def analiz_ciz(self, anahtar):
        g, t, _ = self.analiz_sekmeleri[anahtar]
        acik = ACIKLAMA[anahtar]
        R = self.R
        if R is None or self.analiz_anahtar != tuple(k.kimlik for k in self.birlesik()):
            mesaj = ("Tarama dosyalari okunuyor; analizler okuma bitince hesaplanir."
                     if not self.yukleme_bitti else
                     "Analizler hesaplaniyor (ilk seferde P8+ dosyalari ve rastgele orneklem "
                     "icin birkac dakika; sonra ONBELLEK'ten gelir)...")
            g.ayarla(lambda gg: gg.bos(mesaj))
            self._metin(t, acik)
            return
        sec = self.analiz_secenek.get(anahtar)
        cizici, bulgu = getattr(self, "_a_" + anahtar)(R, sec.get() if sec else None)
        g.ayarla(cizici)
        bas = f"Secili taramalar: {kv.trilyon(R['aralik'][0])} – {kv.trilyon(R['aralik'][1])}"
        self._metin(t, f"{acik}\n\nBULGULAR ({bas})\n{bulgu}")

    # --- 1
    def _a_beklenti(self, R, tur):
        km = R["kmax"]
        sat = []
        if tur == "oran":
            ks = sorted(R["oran_goz"])
            ser = [("Gozlenen", "#222", ks, [R["oran_goz"][k] for k in ks],
                    [f"P{k + 1}/P{k} gozlenen = {sayi_yaz(R['oran_goz'][k])}" for k in ks])]
            for v in range(5):
                kk = [k for k in sorted(R["oran_model"]) if R["oran_model"][k][v]]
                ser.append((f"Model {ka.VARYANTLAR[v]}", VARYANT_RENK[v], kk,
                            [R["oran_model"][k][v] for k in kk],
                            [f"P{k + 1}/P{k} model ({ka.VARYANTLAR[v]}) = "
                             f"{sayi_yaz(R['oran_model'][k][v])}" for k in kk], {"kesik": True}))
            kat = [""] + [f"P{k + 1}/P{k}" for k in range(1, km)]
            baslik, yb = "Gozlenen ve beklenen P(k+1)/Pk", "P(k+1) / Pk"
            xa, xb = 0.5, km - 0.5
        else:
            q = R["qgoz"]
            ks = sorted(q)
            ser = [("Gozlenen q(k)", "#222", ks, [q[k][2] for k in ks],
                    [f"k={k}: {kv.nokta(q[k][0])} / {kv.nokta(q[k][1])} = {sayi_yaz(q[k][2])}"
                     f"\n%95 aralik {sayi_yaz(q[k][3])} – {sayi_yaz(q[k][4])}" for k in ks]),
                   ("_alt", "#222", ks, [q[k][3] or None for k in ks], None,
                    {"kesik": True, "nokta": False}),
                   ("_ust", "#222", ks, [q[k][4] for k in ks], None,
                    {"kesik": True, "nokta": False})]
            for v in range(5):
                kk = sorted(R["qmodel"])
                ser.append((f"Model {ka.VARYANTLAR[v]}", VARYANT_RENK[v], kk,
                            [R["qmodel"][k][1][v] for k in kk],
                            [f"k={k} model {ka.VARYANTLAR[v]}: {sayi_yaz(R['qmodel'][k][1][v])}"
                             f" ± {sayi_yaz(R['qmodel'][k][2][v])}\n{R['qmodel'][k][4]}, "
                             f"n={kv.nokta(R['qmodel'][k][0])}" for k in kk], {"kesik": True}))
            kat = [""] + [f"{k}→{k + 1}" for k in range(1, km + 1)]
            baslik, yb = "Uzama olasiligi q(k) = N(≥k+1) / N(≥k)", "q(k)"
            xa, xb = 0.5, km + 0.5
        sat.append(f"{'k':>3} {'gozlenen':>10} " + " ".join(f"{'V' + str(v):>9}" for v in range(5))
                   + "   (P(k+1)/Pk; V0=1/ln x ... V4=elek≤1000)")
        for k in range(1, km):
            m = R["oran_model"].get(k)
            sat.append(f"{k:>3} {sayi_yaz(R['oran_goz'].get(k, 0)):>10} " +
                       " ".join(f"{sayi_yaz(m[v]) if m and m[v] else '-':>9}" for v in range(5)))
        sat.append("\nModel q(k) kaynaklari: " + "; ".join(
            f"k={k}: {v[4]} (n={kv.nokta(v[0])}, ort. ln x={v[3]:.1f})"
            for k, v in sorted(R["qmodel"].items())))
        h = R["hafiza"].get(3)
        if h:
            sat.append(f"Gozlenen/model (V3) agirlikli ortalama = {h['ort']:.3f}: "
                       f"model sabit carpan disinda {'iyi' if abs(h['ort'] - 1) < 0.1 else 'kaba'}"
                       f" uyuyor.")

        def cizici(g):
            g.cizgiler(baslik, ser, ylog=True, ybaslik=yb, xbaslik="zincir uzunlugu",
                       xmin=xa, xmax=xb, kategorik=kat)
        return cizici, "\n".join(sat)

    # --- 2
    def _a_hafiza(self, R, v):
        v = int(v)
        h = R["hafiza"].get(v)
        if not h:
            return (lambda g: g.bos("Yeterli veri yok")), "-"
        ks = sorted(h["oran"])
        r = [h["oran"][k][0] for k in ks]
        s = [h["oran"][k][1] for k in ks]
        ser = [("Gozlenen / model", "#d43d51", ks, r,
                [f"k={k}: gozlenen q / model q = {r[i]:.3f} ± {s[i]:.3f}"
                 for i, k in enumerate(ks)]),
               ("_alt", "#d43d51", ks, [a - 2 * b for a, b in zip(r, s)], None,
                {"kesik": True, "nokta": False}),
               ("_ust", "#d43d51", ks, [a + 2 * b for a, b in zip(r, s)], None,
                {"kesik": True, "nokta": False}),
               (f"Agirlikli ortalama {h['ort']:.3f}", "#2a6fdb", [ks[0], ks[-1]],
                [h["ort"]] * 2, None, {"kesik": True, "nokta": False})]
        sat = [f"Model: {ka.VARYANTLAR[v]}. Her k icin r(k) = gozlenen q(k) / model q(k) (±2σ).",
               f"Sabit oran hipotezi (hafiza yok): ki-kare = {h['chi']:.1f}, sd = {h['sd']}, "
               f"p = {h['p']:.3g}"]
        sat.append("→ " + ("Oran k ile anlamli degisiyor: uzama olasiligi, terim buyuklugu ve "
                           "yerel kosullar hesaba katildiktan sonra da zincir uzunluguna bagli."
                           if h["p"] < 0.01 else
                           "Oranin k ile degistigine dair anlamli kanit yok: model terim "
                           "buyuklugunu ve yerel kosullari hesaba kattiginda zincir hafizasizdir."))
        for k in ks:
            sat.append(f"  k={k:>2}: r = {h['oran'][k][0]:.3f} ± {h['oran'][k][1]:.3f}  "
                       f"(gozlenen q={sayi_yaz(R['qgoz'][k][2])}, "
                       f"model q={sayi_yaz(R['qmodel'][k][1][v])})")
        km = R["kmax"]

        def cizici(g):
            g.cizgiler(f"Hafiza testi: gozlenen / beklenen uzama olasiligi ({ka.VARYANTLAR[v]})",
                       ser, ylog=False, ybaslik="gozlenen q(k) / model q(k)",
                       xbaslik="adim k (k. terimden k+1. terime)", xmin=0.5, xmax=km + 0.5,
                       kategorik=[""] + [str(k) for k in range(1, km + 1)])
        return cizici, "\n".join(sat)

    # --- 3
    def _a_rakam(self, R, tur):
        D = R["rakam"]
        sat = []
        if tur in ("siklik", "ilk"):
            a, b = (D["p8"], D["ornek"]) if tur == "siklik" else (D["p8_ilk"], D["ornek_ilk"])
            rng = range(10) if tur == "siklik" else range(1, 10)
            ta, tb = sum(a) or 1, sum(b) or 1
            seri = [("P8+ baslangic asallari", "#d43d51", [a[d] / ta * 100 for d in rng]),
                    ("Siradan asallar (duzgun orneklem)", "#2a6fdb",
                     [b[d] / tb * 100 for d in rng])]
            for d in rng:
                sat.append(f"  rakam {d}: P8+ %{a[d] / ta * 100:5.2f}   siradan "
                           f"%{b[d] / tb * 100:5.2f}   oran {a[d] / ta / (b[d] / tb or 1):.2f}")
            if tur == "siklik":
                c, sd, p = D["chi"]
                sat.insert(0, f"Son rakam haric butun basamaklar. Ki-kare (P8+ ~ siradan) = "
                              f"{c:.0f}, sd={sd}, p = {p:.3g}")
            baslik = ("Rakam sikligi (%), son rakam haric" if tur == "siklik"
                      else "Ilk (en soldaki) rakam dagilimi (%)")

            def cizici(g):
                g.cubuklar(baslik, [str(d) for d in rng], seri, ylog=False, ybaslik="%")
            return cizici, "\n".join(sat)
        if tur == "r01":
            xs, ys, ip = [], [], []
            for L in range(1, 8):
                h = D["ornek_r01"][L]
                n = sum(h)
                ham = sum(D["ornek_r01_ham"][L])
                if n and ham >= 100:
                    m = sum(i * c for i, c in enumerate(h)) / n
                    xs.append(L)
                    ys.append(m)
                    ip.append(f"orneklem P{L}{'+' if L == 7 else ''}: ortalama {m:.3f} "
                              f"(n={kv.nokta(ham)})")
            x8, y8, ip8 = [], [], []
            for L, h in sorted(D["p8_r01"].items()):
                n = sum(h)
                m = sum(i * c for i, c in enumerate(h)) / n
                x8.append(L)
                y8.append(m)
                ip8.append(f"P{L} dosyalari: ortalama {m:.3f} (n={kv.nokta(n)})")
            sat.append("Baslangic asalinin alttaki 6 basamaginda (son rakam haric) 0 ya da 1 "
                       "olan rakam sayisinin ortalamasi, zincir uzunluguna gore (rastgele: 1,2):")
            sat += [f"  {s}" for s in ip + ip8]
            ser = [("Orneklem (P1–P7+)", "#2a6fdb", xs, ys, ip),
                   ("P8+ dosyalari", "#d43d51", x8, y8, ip8)]

            def cizici(g):
                g.cizgiler("Baslangic asalindaki 0/1 rakam sayisi (ortalama)", ser, ylog=False,
                           ybaslik="ortalama 0/1 rakam sayisi", xbaslik="zincir uzunlugu",
                           xmin=0.5, xmax=max(x8 + xs) + 0.5,
                           kategorik=[""] + [f"P{k}" for k in range(1, max(x8 + xs) + 1)])
            return cizici, "\n".join(sat)
        if tur == "oran":
            xs = [(i + 0.5) * ka.ORAN_BIN for i in range(ka.ORAN_N)]
            ser = []
            for ad, renk, h in (("Siradan asallar (duzgun orneklem)", "#2a6fdb",
                                 D["ornek_oran"]),
                                ("P8+ baslangiclari", "#d43d51", D["p8_oran"])):
                n = sum(h) or 1
                ys = [c / n / ka.ORAN_BIN for c in h]
                ort = sum(x * c for x, c in zip(xs, h)) / n
                sat.append(f"  {ad}: ortalama log10(KED(p)/p) = {ort:.3f} "
                           f"(KED(p)/p ≈ {10 ** ort:.2f})")
                ser.append((ad, renk, xs, ys, [f"{ad}: log10 oran {x:.3f} → yogunluk "
                                               f"{sayi_yaz(y)}" for x, y in zip(xs, ys)]))
            xb = max(x for x, y1, y2 in zip(xs, ser[0][3], ser[1][3]) if y1 or y2) + 0.1

            def cizici(g):
                g.cizgiler("log10(KED(p) / p) dagilimi", ser, ylog=False, ybaslik="yogunluk",
                           xbaslik="log10(KED(p)/p)", xmin=0, xmax=xb)
            return cizici, "\n".join(sat)
        B = R["basamak_p8"]
        ks = sorted(B)
        xo = sorted(R["basamak_ornek"])
        ser = [("P8+ zincirleri", "#d43d51", ks, [B[k][1] for k in ks],
                [f"P8+ {k}. terim: ort. {B[k][1]:.2f} basamak; sonraki adim "
                 f"log10 artisi {B[k][2]:.3f} (n={kv.nokta(B[k][0])})" for k in ks]),
               ("Orneklem zincirleri", "#2a6fdb", xo, [R["basamak_ornek"][k] for k in xo], None)]
        sat.append("k. terimin ortalama basamak sayisi ve bir sonraki adimda ortalama "
                   "log10(t(k+1)/t(k)):")
        sat += [f"  k={k:>2}: {B[k][1]:6.2f} basamak, adim artisi {B[k][2]:.3f} "
                f"(×{10 ** B[k][2]:.2f})" for k in ks]

        def cizici(g):
            g.cizgiler("Zincir terimlerinin basamak sayisi", ser, ylog=False,
                       ybaslik="ortalama basamak", xbaslik="terim sirasi k",
                       xmin=0.5, xmax=ks[-1] + 0.5,
                       kategorik=[""] + [str(k) for k in range(1, ks[-1] + 1)])
        return cizici, "\n".join(sat)

    # --- 4
    def _a_sinif3(self, R, _):
        S = R["sinif3"]
        kat = ["sinif 0 (KED(p)≡0)", "sinif 1", "sinif 2"]
        seri = [("Gozlenen P2/P1 (orneklem)", "#d43d51", [s["P2P1"] for s in S]),
                ("Model (2,5 + mod 3 + mod 11)", "#2a6fdb", [s["model"] for s in S])]
        sat = []
        for k, s in zip(kat, S):
            sat.append(f"  {k:<20} pay %{s['pay'] * 100:5.2f}  P2/P1 gozlenen "
                       f"{sayi_yaz(s['P2P1'])}  model {sayi_yaz(s['model'])}  "
                       f"(ham P1={kv.nokta(round(s['ham'][0]))}, P2={kv.nokta(round(s['ham'][1]))})"
                       f"  ≥3 payi {sayi_yaz(s['ge3'])}")
        m = R["mod11"]
        sat.append(f"Mod 11 benzeri: KED(p)≡0 (mod 11) olan asallar %{m[1][0] * 100:.2f} "
                   f"(rastgele 1/11 = %9,09); P2/P1: 11∤KED(p) icin {sayi_yaz(m[0][1])}, "
                   f"11|KED(p) icin {sayi_yaz(m[1][1])} (ham P2 = {kv.nokta(round(m[1][3]))}).")
        sat.append(f"P8+ zincirlerinde ara terimlerden KED'i 3'e bolunen (olmamasi gereken) "
                   f"zincir sayisi: {R['sinif3_p8_ihlal']} / {kv.nokta(R['kayit_sayisi'])}.")

        def cizici(g):
            g.cubuklar("3'e bolunmeyen rakam sayisinin mod 3 sinifina gore P2/P1", kat, seri,
                       ylog=False, ybaslik="P2 / P1")
        return cizici, "\n".join(sat)

    # --- 5
    def _a_kume(self, R, k):
        k = int(k)
        ser, sat = [], []
        xm = 0
        for aile, ad, renk in ((False, "Butun baslangiclar", "#d43d51"),
                               (True, "Aile basina bir baslangic", "#c9a400")):
            K = R["kume"].get((k, aile))
            if not K:
                continue
            gs = K["g"]
            n = len(gs)
            adim = max(1, n // 400)
            xs = gs[::adim]
            ser.append((ad, renk, xs, [(i * adim + 1) / n for i in range(len(xs))], None,
                        {"nokta": False}))
            xm = max(xm, gs[-1])
            sapma = ("ustel dagilimdan anlamli sapma (kumelenme)" if K["p"] < 0.01
                     else "ustel dagilimla uyumlu")
            sat += [f"{ad}: {kv.nokta(n + 1)} baslangic (≥10^10), {kv.nokta(n)} bosluk",
                    f"  Kolmogorov–Smirnov D = {K['D']:.4f}, p = {K['p']:.3g} → {sapma}",
                    f"  degisim katsayisi {K['cv']:.3f} (Poisson 1); ortalamanin %1'inden kisa "
                    f"bosluk %{K['kucuk'] * 100:.2f} (Poisson %1,0); 20 esit beklenenli kutu: "
                    f"ki-kare {K['chi']:.1f}, sd=19, p = {K['chi_p']:.3g}"]
        if not ser:
            return (lambda g: g.bos("Yeterli veri yok")), "-"
        xm = min(xm, 8)
        xt = [xm * i / 200 for i in range(1, 201)]
        ser.append(("Ustel dagilim 1 − e^(−g)", "#2a6fdb", xt, [1 - math.exp(-x) for x in xt],
                    None, {"kesik": True, "nokta": False}))
        sat.insert(0, "Bosluklar A/(ln x)^b egilimiyle birim yogunluga donusturuldu ve "
                      "ortalamaya bolundu (Poisson sureci → ustel dagilim).")

        def cizici(g):
            g.cizgiler(f"P{k}+ baslangiclari arasi normalize bosluklarin dagilimi", ser,
                       ylog=False, ybaslik="F(g)", xbaslik="normalize bosluk g", xmin=0,
                       xmax=xm)
        return cizici, "\n".join(sat)

    # --- 6
    def _a_egilim(self, R, tur):
        E = R["egilim"]
        F = E["fit"]
        ser, sat = [], []
        ust = R["aralik"][1]
        izgara = [10 + i * 0.05 for i in range(121)]       # 10^10 .. 10^16

        def egri(A, b):
            return [A * 1e6 * (x * math.log(10)) ** -b for x in izgara]

        if tur == "blok":
            for uz in range(6, 12):
                if uz not in F and uz not in R["uzanti"]:
                    continue
                xs, ys, ip = [], [], []
                for (lo, hi), c, a in zip(E["dilimler"], E["say"][uz], E["asal"]):
                    if c and a:
                        xs.append(math.log10(math.sqrt(lo * hi)))
                        ys.append(c / a * 1e6)
                        ip.append(f"P{uz} · {kv.trilyon(lo)}–{kv.trilyon(hi)}: {kv.nokta(c)} "
                                  f"zincir, milyon asal basina {sayi_yaz(c / a * 1e6)}")
                renk = UZUN_RENK.get(uz, "#555")
                ser.append((f"P{uz}", renk, xs, ys, ip, {"nokta": True, "cizgi": False}))
                if uz <= 9:
                    ser.append((f"_P{uz} egri", renk, izgara, egri(F[uz][0], F[uz][1]), None,
                                {"nokta": False}))
            for uz in range(10, 14):
                if uz in R["uzanti"]:
                    A, b = R["uzanti"][uz]
                    ser.append((f"P{uz} (uzanti)", UZUN_RENK.get(uz, "#555"), izgara, egri(A, b),
                                None, {"kesik": True, "nokta": False}))
        else:
            for i, uz in enumerate(range(2, 6)):
                if uz not in F:
                    continue
                xs = [math.log10(math.sqrt(max(b, 1) * s)) for b, s, _, _ in E["kaynak"]]
                ys = [P[uz - 1] / a * 1e6 for _, _, a, P in E["kaynak"]]
                renk = RENKLER[i]
                ser.append((f"P{uz}", renk, xs, ys, None, {"nokta": True, "cizgi": False}))
                ser.append((f"_P{uz} egri", renk, izgara, egri(F[uz][0], F[uz][1]), None,
                            {"nokta": False}))
        sat.append("Milyon asal basina Pk = A / (ln x)^b  (Poisson en cok olabilirlik; "
                   "teori: b ≈ k−1, terimler buyudukce biraz daha az)")
        for uz in sorted(F):
            A, b, h = F[uz]
            sat.append(f"  P{uz:<2}: A = {A * 1e6:.4g}, b = {b:.2f} ± {h:.2f}")
        for uz, (A, b) in sorted(R["uzanti"].items()):
            sat.append(f"  P{uz:<2}: uzanti A = {A * 1e6:.4g}, b = {b:.2f} "
                       f"(P9 egrisi × (P9/P8)^{uz - 9} × terim buyumesi duzeltmesi)")
        sat.append("P10+ icin ongoru, az olayla oturan P10/P11 egrileri yerine bu zincirleme "
                   "uzantiyla yapilir; taranan bolgede beklenen/gozlenen karsilastirmasi asagida.")
        sat.append("\nOngoru (beklenen zincir sayisi):")
        for o in R["ongoru"]:
            lo, hi = o["aralik"]
            sat.append(f"  {kv.trilyon(lo)} – {kv.trilyon(hi)}: " + ", ".join(
                f"P{k} ≈ {o[k]:.1f}" for k in (10, 11, 12, 13) if k in o))
        sat.append("\nIlk gorunum / sonraki gorunum tahmini (10^9'dan itibaren birikimli "
                   "beklenen = 1; sonraki: taranan sinirdan medyan bekleme):")
        for k, t in sorted(R["ilk_tahmin"].items()):
            gercek = R["rekor"].get(k)
            sat.append(f"  P{k:<2}: beklenen 1 → {konum_yaz(t['ilk_1'])}"
                       f"   gercek ilk: {konum_yaz(gercek[0]) if gercek else 'henuz yok'}"
                       f"   taranan bolgede beklenen {t['taranan_beklenen']:.1f}"
                       f" (gozlenen {kv.nokta(R['P'][k]) if k <= 21 else '-'})"
                       f"   sonraki ≈ {konum_yaz(t['sonraki_medyan'])}")

        def cizici(g):
            g.cizgiler("Milyon asal basina Pk ve A/(ln x)^b egrileri (kesikli: uzanti)", ser,
                       ylog=True, ybaslik="milyon asal basina Pk", xbaslik="x (log olcek)",
                       xmin=10 if tur == "blok" else 12, xmax=16,
                       xetiket=lambda v: us_yaz(round(v)) if abs(v - round(v)) < 1e-9 else "",
                       isaretler=[(math.log10(ust), "#000", f"taranan sinir {kv.trilyon(ust)}")])
        return cizici, "\n".join(sat)

    # --- 7
    def _a_rekor(self, R, _):
        t = self.rekor_tablo
        t.delete(*t.get_children())
        ks = sorted(R["rekor"])
        sat = []
        for k in ks:
            p, nere, z = R["rekor"][k]
            m = R["ilk_tahmin"].get(k) if k >= 9 else None
            t.insert("", "end", values=(f"P{k}", kv.nokta(p), len(str(p)), nere,
                                        kv.nokta(round(m["ilk_1"])) if m and m["ilk_1"] else "-"))
            sat.append(f"P{k}: " + " > ".join(str(v) for v in z))
        for k in (12, 13, 14):
            if k not in R["rekor"] and k in R["ilk_tahmin"]:
                m = R["ilk_tahmin"][k]
                t.insert("", "end", values=(f"P{k}", "henuz yok", "-", "-",
                                            kv.nokta(round(m["ilk_1"])) if m["ilk_1"] else "-"))
        ser = [("Gercek ilk gorunum", "#d43d51", ks, [math.log10(R["rekor"][k][0]) for k in ks],
                [f"P{k}: {kv.nokta(R['rekor'][k][0])}" for k in ks])]
        mk = [k for k in sorted(R["ilk_tahmin"]) if k >= 9 and R["ilk_tahmin"][k]["ilk_1"]]
        ser.append(("Egilim modeli (birikimli beklenen = 1)", "#2a6fdb", mk,
                    [math.log10(R["ilk_tahmin"][k]["ilk_1"]) for k in mk],
                    [f"P{k} model: {konum_yaz(R['ilk_tahmin'][k]['ilk_1'])}" for k in mk],
                    {"kesik": True}))
        km = max(ks + mk)
        sat.insert(0, "Not: ilk gorunumler monoton degil (ornegin ilk P8, ilk P7'den kucuk). "
                      "Kucuk sayilarda model gecersiz (egriler 10^10 ustunden oturtuldu); model "
                      "konumu P9 ve ustu icin verilir.")

        def cizici(g):
            g.cizgiler("Her uzunlugun ilk gorundugu baslangic asali", ser, ylog=False,
                       ybaslik="log10(ilk baslangic)", xbaslik="zincir uzunlugu",
                       xmin=0.5, xmax=km + 0.5,
                       kategorik=[""] + [f"P{k}" for k in range(1, km + 1)])
        return cizici, "\n".join(sat)

    # --- 8
    def _a_birlesme(self, R, tur):
        B = R["birlesme"]
        sat = [f"P8+ zincirlerinde birlesme dugumu (≥2 farkli onculu terim): {B['dugum']}; "
               f"birlesmenin oldugu terim sirasi: " +
               ", ".join(f"{k}. terim: {v}" for k, v in sorted(B["derinlik"].items()))]
        sat.append("Aile boyu dagilimi (ortak terimi olan baslangiclar): " +
                   ", ".join(f"{k}: {v}" for k, v in sorted(B["aile_boyu"].items())))
        for a in B["aileler"][:5]:
            sat.append("  aile: " + ", ".join(f"{kv.nokta(b)} (P{L})" for b, L in a[:6]) +
                       (" ..." if len(a) > 6 else ""))
        O = R["onimge"]
        sat.append(f"Iki basamakli carpismalar 10a²+b² = 10c²+d²: " +
                   ", ".join(f"{'/'.join(ab)}→{v}" for v, ab in O["ciftler"]))
        sat.append(f"{kv.nokta(O['aralik'][0])}–{kv.nokta(O['aralik'][1])} arasinda en cok "
                   f"onimgeli deger {kv.nokta(O['en_cok'][0])}: {O['en_cok'][1]} onimge "
                   f"(ornek: {', '.join(map(str, O['en_cok_onimge'][:6]))})")
        if tur == "bag":
            ks = sorted(B["bag"])
            kat = [f"P{k}" for k in ks]
            seri = [("Zincir sayisi", "#d43d51", [B["bag"][k][0] for k in ks]),
                    ("Farkli KED(p)", "#c9a400", [B["bag"][k][1] for k in ks]),
                    ("Bagimsiz aile", "#2a6fdb", [B["bag"][k][2] for k in ks])]
            sat.insert(0, "Ayni KED(p) degerine giden baslangiclarin geri kalan zinciri ortaktir; "
                          "bunlar istatistikte tek olay sayilmalidir:\n" + "\n".join(
                              f"  P{k}: {B['bag'][k][0]} zincir, {B['bag'][k][1]} farkli KED(p), "
                              f"{B['bag'][k][2]} bagimsiz aile" for k in ks))

            def cizici(g):
                g.cubuklar("Zincir sayisi ve bagimsiz (birlesmeyen) zincir sayisi", kat, seri,
                           ylog=True, ybaslik="adet")
        else:
            ms = sorted(set(O["hepsi"]) | set(O["asal"]))
            kat = [str(m) for m in ms]
            seri = [("Butun n", "#2a6fdb", [O["hepsi"].get(m, 0) for m in ms]),
                    ("Yalniz asal n", "#d43d51", [O["asal"].get(m, 0) for m in ms])]

            def cizici(g):
                g.cubuklar(f"KED degerlerinin onimge sayisi ({kv.nokta(O['aralik'][0])} ≤ n < "
                           f"{kv.nokta(O['aralik'][1])})", kat, seri, ylog=True,
                           ybaslik="deger sayisi")
        return cizici, "\n".join(sat)

    # --- 9
    def _a_kontrol(self, R, _):
        K = R["kontrol"]
        adlar = (("k_gercek", "Gercek: asal baslangic + KED", "#d43d51"),
                 ("k_bilesik", "Kontrol: bilesik tek baslangic + KED", "#2a6fdb"),
                 ("k_rastgele", "Kontrol: asal + rastgele esleme", "#1a9e5c"),
                 ("tarama", "Tarama sayaclari (tam)", "#222"))
        ser, sat = [], []
        km = 1
        for a, ad, renk in adlar:
            n, f = K[a]
            ks = [k for k in range(1, len(f)) if f[k] > 0]
            km = max(km, ks[-1])
            ser.append((ad, renk, ks, [f[k] for k in ks],
                        [f"{ad}\n≥{k}: {sayi_yaz(f[k])}" for k in ks]))
            sat.append(f"  {ad:<40} n={kv.nokta(round(n)):>16}  " + "  ".join(
                f"≥{k}: {sayi_yaz(f[k])}" for k in range(2, 6) if k < len(f)))
        sat.insert(0, "Zincirin en az k uzunlukta olma orani (rastgele esleme: KED(t) + 10·U, "
                      "ayni son rakam, [x, 2x) araligi):")

        def cizici(g):
            g.cizgiler("Kontrol deneyi: en az k uzunlukta zincir orani", ser, ylog=True,
                       ybaslik="N(≥k) / N", xbaslik="zincir uzunlugu", xmin=0.5,
                       xmax=km + 0.5, kategorik=[""] + [f"≥{k}" for k in range(1, km + 1)])
        return cizici, "\n".join(sat)

    # --- 10
    def _a_yerel(self, R, _):
        Y = R["yerel"]
        kat = [str(q) for q, *_ in Y]
        seri = [("KED(p), siradan asal p", "#2a6fdb", [q * rp for q, rp, *_ in Y]),
                ("KED(t), zincir ici (k≥2)", "#1a9e5c", [q * rz for q, _, rz, *_ in Y]),
                ("Sonlayan bilesik (P8+)", "#d43d51", [q * rs for q, _, _, rs, _ in Y])]
        sat = ["q · P(q | KED): 1 = rastgele sayi gibi; 0 = hic bolunmez; >1 = fazla bolunur.",
               "Sonlayanlar bilesik olmak zorunda oldugundan beklenen deger 1'in biraz ustudur "
               "(asal olmama kosulu: yaklasik 1/(1 − q(k)) ≈ 1,06).",
               "Etkin sabit C (2,5 duzeltmesi × listedeki q'larin yerel carpani "
               "(1−ρ_q)/(1−1/q)):"]
        sat += [f"  q={q:>2}: ρ_q={rp:.4f} (1/q={1 / q:.4f}), zincir ici {rz:.4f}, "
                f"sonlayan {rs:.4f}  → C = {C:.3f}" for q, rp, rz, rs, C in Y]
        S = R["sonlayan"]
        top = sum(S.values()) or 1
        sat.append("P8+ zincirlerini sonlayan bilesiklerin en kucuk asal carpani: " + ", ".join(
            f"{q if q else '>1000'}: %{c / top * 100:.1f}"
            for q, c in sorted(S.items(), key=lambda x: (x[0] is None, x[0] or 0))[:14]))

        def cizici(g):
            g.cubuklar("Kucuk asallara bolunme: q · P(q | KED)", kat, seri, ylog=False,
                       ybaslik="q · bolunme olasiligi", etiket=False)
        return cizici, "\n".join(sat)


def main():
    kok = tk.Tk()
    Uygulama(kok)
    kok.mainloop()


if __name__ == "__main__":
    main()
