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
from tkinter import ttk

import ked_veri as kv

RENKLER = ["#2a6fdb", "#e0612b", "#1a9e5c", "#b8338f", "#c9a400", "#6b4fd8",
           "#0d9aa8", "#8a5a2b", "#d43d51", "#5d6b7a"]
UZUN_RENK = {6: "#2a6fdb", 7: "#1a9e5c", 8: "#c9a400", 9: "#e0612b", 10: "#d43d51",
             11: "#6b4fd8", 12: "#0d9aa8", 13: "#8a5a2b"}
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
        """seriler: [(ad, renk, xs, ys, ipucu_listesi_ya_da_None)]; kategorik: x etiketleri"""
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
        for ad, renk, xs, vs, ipuclari in seriler:
            onceki = None
            for i, (x, v) in enumerate(zip(xs, vs)):
                if v is None or v <= 0:
                    onceki = None
                    continue
                p = (X(x), Y(v))
                if onceki:
                    self.create_line(*onceki, *p, fill=renk, width=2,
                                     dash=(6, 4) if ad.startswith("Birlesik") else None)
                if len(xs) <= 60:
                    self.create_oval(p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3, fill=renk,
                                     outline="")
                self.noktalar.append((p[0], p[1], ipuclari[i] if ipuclari else
                                      f"{ad}: {sayi_yaz(v)}"))
                onceki = p
        for x, renk, metin in isaretler:
            px = X(x)
            self.create_polygon(px, y1 - 9, px - 4, y1 - 1, px + 4, y1 - 1, fill=renk, outline="")
            self.noktalar.append((px, y1 - 5, metin))
        self.gosterge([(s[0], s[1]) for s in seriler], x1, y0)


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
                    self.hepsini_ciz()
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


def main():
    kok = tk.Tk()
    Uygulama(kok)
    kok.mainloop()


if __name__ == "__main__":
    main()
