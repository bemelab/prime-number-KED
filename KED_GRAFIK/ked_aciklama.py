# -*- coding: utf-8 -*-
"""Analiz sekmelerinin kisa aciklamalari ve kaynak notlari (KED_GRAFIK Analizler sekmesi)."""

ACIKLAMA = {
    "beklenti": """\
YONTEM: x = KED(t) icin "x asal" olasiligi C(x)/ln x kabul edilir (Cramer modeli). Duzeltmeler:
  V0 = 1/ln x (duzeltmesiz)
  V1 = 2.5/ln x: t asal (son rakam 1,3,7,9) ise KED(t)'nin son rakami d0^2 mod 10 = 1 ya da 9;
       KED(t) 2'ye ve 5'e hic bolunmez → (2/1)(5/4) = 2.5
  V2 = + mod 3: 10 ≡ 1 (mod 3) oldugundan KED(n) ≡ Σd² ≡ (3'e bolunmeyen rakam sayisi) (mod 3);
       KED(t) 3'e bolunuyorsa 0, bolunmuyorsa 3/2 carpani
  V3 = + mod 11: 10 ≡ −1 (mod 11) → KED(n) ≡ Σ(−1)^i d_i² (mod 11); bolunuyorsa 0, degilse 11/10
  V4 = 1000'e kadar butun asallarla elek: Π q/(q−1) / ln x (Granville'in elek duzeltmeli modeli)
Model q(k), zincirin k. teriminin gercek dagilimi uzerinden ortalanir: k ≤ 5 rastgele pencere
orneklemi, k = 6,7 P6/P7 dosyalarinin 1/97 blok orneklemi, k ≥ 8 P8+ dosyalarinin tamami.
Beklenen P(k+1)/Pk = q(k)·(1 − q(k+1)) / (1 − q(k)).
KAYNAK: H. Cramer (1936) olasiliksal asal modeli; A. Granville, "Harald Cramer and the distribution
of prime numbers", Scand. Actuarial J. (1995); Bateman–Horn (1962) yerel carpan fikri.""",

    "hafiza": """\
YONTEM: Zincir hafizasiz ise k. terimden k+1. terime gecme olasiligi yalniz o terimin buyuklugune ve
yerel (mod q) kosullarina baglidir. Her k icin r(k) = gozlenen q(k) / model q(k) hesaplanir;
hafiza yoksa r(k) sabittir. Sabitlik, ters varyans agirlikli ki-kare homojenlik testiyle sinanir
(gozlenen icin binom/Wilson hatasi, model icin orneklem ortalamasinin standart hatasi).
KAYNAK: Markov zinciri / hafizasizlik testi; Wilson (1927) binom guven araligi; Pearson ki-kare.""",

    "rakam": """\
YONTEM: P8+ baslangic asallarinin rakamlari, ayni araliklardan duzgun dagilimla secilmis siradan
asallarla karsilastirilir (son rakam haric butun basamaklar; ki-kare). Ilk rakam dagilimi ayrica
verilir (KED(p)/p ≈ ilk rakam buyuklugune bagli). 0 ve 1 rakamlari KED'de degismez (0²=0, 1²=1);
yalniz 0/1'den olusan sayilarda KED(n) = n (sabit nokta, tarama bunlari P1 sayar). 0/1 sayisi
pencere orneklemiyle karsilastirilabilmek icin alttaki 6 basamakta sayilir. KED(p)/p dagilimi
ve terimlerin basamak buyumesi (log10(t(k+1)/t(k))) da gosterilir.
KAYNAK: rakam kareleri toplami / mutlu sayilar: OEIS A003132, A007770; Grundman & Teeple (2001,
2007) genellestirilmis mutlu sayilar. KED, rakam karelerine konum agirligi veren bir varyanttir.""",

    "sinif3": """\
YONTEM: Asallar c(p) = (3'e bolunmeyen rakam sayisi) mod 3'e gore uc sinifa ayrilir. KED(p) ≡ c(p)
(mod 3) oldugundan: sinif 0'da KED(p) daima 3'e bolunur → P2/P1 = 0 (teori); sinif 1 ve 2'de
KED(p) 3'e hic bolunmez → uzama olasiligi ortalamanin 3/2 kati. Gozlenen P2/P1 rastgele pencere
orneklemiyle olculur ve modelle karsilastirilir. Ayni sinama mod 11 icin de verilir.
KAYNAK: KED(n) ≡ Σd² (mod 9) — mutlu sayilarda kullanilan mod 3/mod 9 degismezligiyle ayni fikir.""",

    "kume": """\
YONTEM: P8+/P9+/P10+ baslangic asallari sirali alinir; aradaki bosluklar A/(ln x)^b egilim
egrisinin birikimli integraliyle birim yogunluga donusturulup ortalamaya bolunur. Bagimsiz
(Poisson) olaylarda bu bosluklar ustel dagilir: Kolmogorov–Smirnov testi (Stephens yaklasimi),
degisim katsayisi ve 20 esit beklenenli kutuda ki-kare. Ayni KED(p)'de birlesen baslangiclar ortak
kuyruga sahip oldugundan test, her aileden yalniz bir baslangic alinarak da tekrarlanir.
KAYNAK: Kolmogorov (1933), Smirnov (1948), Stephens (1970) KS p-degeri yaklasimi; Gallagher (1976)
asallarin kisa araliklarda Poisson dagilimi (Hardy–Littlewood varsayimi altinda).""",

    "egilim": """\
YONTEM: Milyon asal basina Pk orani = A/(ln x)^b. P6–P11 icin milyarlik bolum dosyalarindan
~%25 genislikte geometrik dilimler, P2–P5 icin tarama toplamlari kullanilir; A ve b Poisson en cok
olabilirlikle (her dilimde beklenen = A ∫ (ln t)^(−b−1) dt) oturtulur. Bateman–Horn/Cunningham
sezgisi: en az k uzunlukta zincir baslatma olasiligi ≈ Π 1/ln(t_i) → b ≈ k−1. P10+ ongorusu,
az olayla oturan egriler yerine P8/P9 egrilerinden zincirleme uzanti ile yapilir. Ilk gorunum:
birikimli beklenen sayinin 1'e ulastigi yer; sonraki gorunum: taranan sinirdan medyan bekleme.
KAYNAK: Bateman & Horn (1962) Math. Comp. 16; Cunningham zincirleri icin N/(log N)^k sayimi
(Loh 1989 Math. Comp. 53; t5k.org Cunningham zinciri sayfalari).""",

    "rekor": """\
YONTEM: Her uzunlugun ilk gorundugu baslangic asali: kucuk uzunluklar Python'la 2.000.000'a kadar
dogrudan taranir (tarama kurali: KED(p) = p sabit noktasi P1), buyukleri bolum dosyalarindan
okunur. Model sutunu egilim egrisinin birikimli beklenen sayisinin 1'e ulastigi konumdur.
KAYNAK: Cunningham zincirlerinde en kucuk baslangic tablolari (OEIS A005602, A005603) ile ayni
tur kayit; rekorlarin modelle karsilastirilmasi Bateman–Horn sayimindan.""",

    "birlesme": """\
YONTEM: KED birebir degildir: ornegin KED(19) = KED(31) = 91 (10·1+81 = 10·9+1). Farkli baslangiclar
ayni KED degerine gidince zincirin geri kalani ortaktir. P8+ zincirlerinin butun terimleri bir
fonksiyon grafinin kenarlari olarak alinir; ≥2 onculu dugumler (birlesme noktalari) ve birlesim-
bul ile aileler bulunur. Bagimsiz olay sayisi = aile sayisi. Ayrica 10^5–10^6 arasinda KED'in
onimge sayisi dagilimi (fonksiyon grafinin giris derecesi) verilir.
KAYNAK: Rastgele fonksiyon/fonksiyonel graf istatistikleri (Flajolet & Odlyzko 1990, "Random
mapping statistics"); mutlu sayi yinelemesinin fonksiyon grafi olarak incelenmesi.""",

    "kontrol": """\
YONTEM: Ayni islem uc durumda olculur (rastgele pencerelerde, pencere basina 15.000 ornek):
  Gercek: asal p'den KED yinelemesi;  Bilesik: 2 ve 5'e bolunmeyen bilesik tek sayidan baslatma;
  Rastgele esleme: KED(t) yerine KED(t) + 10·U (U rastgele; son rakam ve buyukluk korunur, mod 3
  yapisi bozulur). Tam tarama sayaclari da referans olarak cizilir.
KAYNAK: Monte Carlo kontrol deneyi; rastgele esleme Cramer modelinin dogrudan benzetimidir.""",

    "yerel": """\
YONTEM: Her kucuk asal q icin P(q | KED) olculur: siradan asallarda KED(p), zincir icinde KED(t_k)
(k ≥ 2) ve P8+ zincirlerini sonlayan bilesikler. q·P = 1 rastgele sayi gibi davranir demektir.
Etkin sabit C = 2.5 · Π (1−ρ_q)/(1−1/q), Bateman–Horn'daki tekil serinin (yerel carpanlarin
carpimi) bu probleme uyarlanmis halidir. Sonlayan bilesiklerin en kucuk carpani "olum nedeni"dir.
KAYNAK: Hardy & Littlewood (1923) Partitio Numerorum III (asal k-liler, tekil seri);
Bateman & Horn (1962); Aletheia-Zomlefer, Fukshansky & Garcia (2020) Bateman–Horn derlemesi.""",
}

KAYNAKCA = """\
KAYNAKCA VE YONTEMLERIN KOKENI

Olasiliksal asal modelleri
  - H. Cramer, "On the order of magnitude of the difference between consecutive prime numbers",
    Acta Arith. 2 (1936). Rastgele n'nin asal olma olasiligi 1/ln n.  → Beklenti modeli V0
  - A. Granville, "Harald Cramer and the distribution of prime numbers", Scand. Actuarial J.
    (1995). Kucuk asallara bolunebilirligi hesaba katan duzeltilmis model.  → V4 (elek ≤1000)
  - W. Banks, K. Ford, T. Tao, "Large prime gaps and probabilistic models", Invent. Math. (2023),
    arXiv:1908.08613.

Asal k-liler ve polinom degerleri
  - G. H. Hardy, J. E. Littlewood, "Some problems of 'Partitio numerorum' III", Acta Math. 44
    (1923). Tekil seri (yerel carpanlar).  → Yerel carpanlar sekmesi
  - P. T. Bateman, R. A. Horn, "A heuristic asymptotic formula concerning the distribution of
    prime numbers", Math. Comp. 16 (1962).  → Egilim (b ≈ k−1), yerel carpanlar
  - S. L. Aletheia-Zomlefer, L. Fukshansky, S. R. Garcia, "The Bateman–Horn conjecture:
    heuristics, history, and applications", Expo. Math. (2020), arXiv:1807.08899.

Cunningham zincirleri (p → 2p±1)
  - G. Loh, "Long chains of nearly doubled primes", Math. Comp. 53 (1989).
  - Bateman–Horn'a gore en az k uzunlukta zincir baslatan p ≤ N sayisi ≈ B_k N/(log N)^k;
    t5k.org "Cunningham Chains" sayfalari (B_k degerleri ve rekorlar). KED zincirleri ayni
    yapidadir: her adim bagimsiz bir "asal mi" denemesi, ancak terimler ~×4 buyur ve donusum
    rakam tabanlidir.  → Egilim, rekorlar, hafiza testi
  - OEIS A005602 / A005603: uzunlugu k olan en kucuk Cunningham zinciri baslangici.  → Rekorlar

Rakam fonksiyonlarinin yinelenmesi
  - Mutlu sayilar: rakam karelerinin toplami S2(n) yinelenir; 1'e ya da 4→16→37→58→89→145→42→20
    dongusune iner. OEIS A003132 (S2), A007770 (mutlu sayilar).
  - H. G. Grundman, E. A. Teeple, "Generalized happy numbers", Fibonacci Quart. 39 (2001) ve
    "Sequences of generalized happy numbers with small bases", J. Integer Seq. 10 (2007).
  - E. El-Sedy, S. Siksek, "On happy numbers", Rocky Mountain J. Math. 30 (2000).
  - Baglanti: KED(n) ≡ S2(n) (mod 9), dolayisiyla mod 3 sinifi mutlu sayi kuramindaki
    degismezlikle aynidir; KED ise konum agirligi tasidigindan iraksar (KED(n) ≥ n).  → 3'e gore
    siniflar, rakam yapisi

Istatistik
  - E. B. Wilson (1927) binom guven araligi; Kolmogorov (1933), Smirnov (1948), M. A. Stephens
    (1970) KS testi; Pearson ki-kare; Poisson en cok olabilirlik (profil olabilirlik, altin oran
    aramasi).
  - P. X. Gallagher, "On the distribution of primes in short intervals", Mathematika 23 (1976):
    Hardy–Littlewood altinda asallar kisa araliklarda Poisson dagilir.  → Kumelenme
  - P. Flajolet, A. Odlyzko, "Random mapping statistics", EUROCRYPT '89 (1990).  → Birlesen
    zincirler (fonksiyonel graf)
"""
