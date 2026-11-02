# -*- coding: utf-8 -*-
"""PATİ KED — CLANG SÜRÜMÜ (KED_CLANG klasörü): KED_GPU ile aynı program, C çekirdeği clang ile derlenmiştir.
PATİ: 5–10 trilyon / ÇOK ÇEKİRDEKLİ / PENCERELİ / P6+ EKRANDA VE TXT / güvenli checkpoint.
Python 3.9+, ek paket gerekmez (tkinter Python ile gelir).

Tum kayitlar TXT'dir: checkpoint PATI_CHECKPOINT.txt; zincirler uzunluklarina gore ayri klasorlerde
(P6, P7 ... P20, P21_PLUS, donguler DONGU), her 1 milyarlik bolum icin bir dosya (o uzunlukta
zincir yoksa dosya acilmaz). Eski yapidaki (ZINCIRLER_P6_PLUS / JSON) klasorlerle calismaz.
Isci (cekirdek) sayisi calisirken degistirilebilir: pencerede kutudan, konsolda sayi yazip Enter.
Hesap, yanindaki ked_cekirdek.dll (ked_cekirdek.c, derle.bat ile derlenir) varsa C'de yapilir;
yoksa (veya --python ile) Python islemleriyle. Sonuc dosyalari iki durumda da aynidir.
Konsol penceresi olmadan acmak icin: PATI_BASLAT.pyw
Tarama baslama/bitis tarihleri checkpoint'e, her oturum CALISMA_GUNLUGU.txt dosyasina yazilir.
Pencere yerine konsolda calistirmak icin: --konsol
"""
import argparse
import collections
import datetime
import gc
import hashlib
import itertools
import math
import multiprocessing as mp
import os
from pathlib import Path
import queue
import signal
import sys
import threading
import time

BASLANGIC = 5_000_000_000_000
BITIS = 10_000_000_000_000  # hariç
ELEK_BLOGU = 2_000_000
KAYIT_ADIMI = 1_000_000_000
ISCI_SAYISI = 16
MR_BASES_64 = (2, 325, 9375, 28178, 450775, 9780504, 1795265022)
MR_BASES_BUYUK = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
KARELER = tuple(i*i for i in range(10))
SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
FORMAT = 'PATI_5_10_TAM_KAYIT_v5_P20'  # her zincir uzunlugu ayri klasorde, sayaclar P1..P20 + P21+
SON_TAM = 20  # P1..P20 tam uzunluk sayilir/klasorlenir; daha uzunlari P21+ (P21_PLUS)
SAYAC_BOYU = SON_TAM + 2  # indeks 0 kullanilmaz, SON_TAM+1 = P21+
CHECKPOINT_ADI = 'PATI_CHECKPOINT.txt'
TARIH_BICIMI = '%d.%m.%Y %H:%M:%S'
U64 = 1 << 64
# 200'e kadar asallarin carpimi: tek gcd ile cogu bilesik MR'a girmeden elenir.
ON_ASALLAR = tuple(p for p in range(2, 200) if all(p % q for q in range(2, math.isqrt(p) + 1)))
ON_CARPIM = math.prod(ON_ASALLAR)
ON_KUME = frozenset(ON_ASALLAR)
ON_SINIR = ON_ASALLAR[-1] ** 2


def ked_yavas(n):
    sonuc = 0
    basamak = 1
    while n:
        n, rakam = divmod(n, 10)
        sonuc += KARELER[rakam] * basamak
        basamak *= 10
    return sonuc


# KED basamak konumuna gore dogrusal: 5'er basamakli parcalar tablodan okunur.
KED5 = tuple(ked_yavas(k) for k in range(100000))


def ked(n, tablo=KED5):
    sonuc = 0
    carpan = 1
    while n:
        n, parca = divmod(n, 100000)
        sonuc += tablo[parca] * carpan
        carpan *= 100000
    return sonuc


def temel_asallari_bul(limit):
    elek = bytearray(b'\x01') * (limit + 1)
    elek[:2] = b'\x00\x00'
    for p in range(2, math.isqrt(limit) + 1):
        if elek[p]:
            first = p * p
            elems = (limit - first) // p + 1
            elek[first:limit + 1:p] = b'\x00' * elems
    return [p for p in range(3, limit + 1, 2) if elek[p]]


def asal_mr(n):
    if n < 2:
        return False, False
    for p in SMALL_PRIMES:
        if n == p:
            return True, False
        if n % p == 0:
            return False, False
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    büyük = n >= (1 << 64)
    for a in (MR_BASES_BUYUK if büyük else MR_BASES_64):
        a %= n
        if a == 0:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = (x*x) % n
            if x == n - 1:
                break
        else:
            return False, büyük
    return True, büyük


def asal_64(n, gcd=math.gcd):
    """n < 2^64 icin asal_mr ile ayni (kesin) sonuc; on eleme tek gcd ile."""
    if n < ON_SINIR:
        return n in ON_KUME or (n > 1 and gcd(n, ON_CARPIM) == 1)
    if gcd(n, ON_CARPIM) != 1:
        return False
    m = n - 1
    s = (m & -m).bit_length() - 1
    d = m >> s
    for a in MR_BASES_64:
        a %= n
        if a == 0:
            continue
        x = pow(a, d, n)
        if x == 1 or x == m:
            continue
        for _ in range(s - 1):
            x = x*x % n
            if x == m:
                break
        else:
            return False
    return True


def zinciri_incele(p1, n=None):
    """n verilirse ked(p1) olarak kabul edilir (ve n < 2^64 ise asal oldugu biliniyordur)."""
    zincir = [p1]
    gorulen = {p1}
    buyuk_mr = 0
    bilinen_asal = n is not None
    if n is None:
        n = ked(p1)
    while True:
        if n in gorulen:
            # Asal sabit nokta özel P1 durumu. Gerçek döngüler ayrı sayılır.
            if n == p1 and len(zincir) == 1:
                return 1, zincir, 'sabit', buyuk_mr
            return len(zincir), zincir, 'dongu', buyuk_mr
        if n < U64:
            asal = bilinen_asal or asal_64(n)
        else:
            # 64 bit ustu: orijinal test ve sayac aynen korunur.
            asal, buyuk = asal_mr(n)
            if buyuk:
                buyuk_mr += 1
        bilinen_asal = False
        if not asal:
            return len(zincir), zincir, 'bilesik', buyuk_mr
        gorulen.add(n)
        zincir.append(n)
        n = ked(n)


def elekteki_asallar(alt, ust, temel_asallar):
    ilk_tek = alt | 1
    adet = max(0, (ust - ilk_tek + 1) // 2)
    if adet == 0:
        return iter(())
    elek = bytearray(b'\x01') * adet
    for p in temel_asallar:
        if p*p >= ust:
            break
        first = max(p*p, ((ilk_tek+p-1)//p)*p)
        if first % 2 == 0:
            first += p
        if first >= ust:
            continue
        konum = (first - ilk_tek)//2
        kac = (adet - 1 - konum)//p + 1
        elek[konum::p] = b'\x00' * kac
    return itertools.compress(range(ilk_tek, ilk_tek + 2*adet, 2), elek)


def atomic_txt(path, metin):
    temp = path.with_suffix(path.suffix+'.tmp')
    with open(temp, 'w', encoding='utf-8') as f:
        f.write(metin)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


CK_SAYI_ALANLARI = ('baslangic', 'bitis', 'elek_blogu', 'kayit_adimi', 'tamamlanan_sinir')
CK_TOPLAM_ALANLARI = ('asal_toplami', 'dongu', '64_bit_ustu_mr_test')
CK_TARIH_ALANLARI = ('tarama_baslama_tarihi', 'tarama_bitis_tarihi')


def checkpoint_yaz(path, d):
    satirlar = ['# PATI KED taramasi kayit noktasi. ELLE DEGISTIRMEYIN, SILMEYIN.',
                'format = ' + d['format']]
    satirlar += ['%s = %d' % (k, d[k]) for k in CK_SAYI_ALANLARI]
    s = d['sayac_tam_uzunluk']
    satirlar += ['P%d = %d' % (k, s[k]) for k in range(1, SON_TAM + 1)]
    satirlar.append('P%d+ = %d' % (SON_TAM + 1, s[SON_TAM + 1]))
    satirlar += ['%s = %d' % (k, d[k]) for k in CK_TOPLAM_ALANLARI]
    satirlar.append('son_bolum_dosyalari = ' + ','.join(d.get('son_bolum_dosyalari') or []))
    satirlar.append('son_bolum_sha256 = ' + (d.get('son_bolum_sha256') or ''))
    satirlar.append('toplam_sure_sn = %d' % d.get('toplam_sure_sn', 0))
    satirlar += ['%s = %s' % (k, d[k]) for k in CK_TARIH_ALANLARI if k in d]
    atomic_txt(path, '\n'.join(satirlar) + '\n')
    sayac_dosyasi_yaz(path.parent, d)


SAYAC_DOSYASI = 'SAYACLAR.txt'


def sayac_dosyasi_yaz(folder, d):
    """Pencerede gorunen kaydedilmis sayaclarin okunur kopyasi (checkpoint ile birlikte guncellenir)."""
    s = d['sayac_tam_uzunluk']
    bas, bit, sinir = d['baslangic'], d['bitis'], d['tamamlanan_sinir']
    satirlar = ['PATI KED TARAMASI - SAYACLAR (kaydedilmis)',
                '=' * 44,
                'Aralik            : %s - %s' % (nokta(bas), nokta(bit)),
                'Taranan sinir     : %s  (%%%.3f)' % (nokta(sinir), 100 * (sinir - bas) / (bit - bas)),
                'Durum             : %s' % ('TAMAMLANDI' if sinir >= bit else 'devam ediyor / durduruldu'),
                'Tarama baslangici : %s' % d.get('tarama_baslama_tarihi', '-'),
                'Tarama bitisi     : %s' % d.get('tarama_bitis_tarihi', '-'),
                'Toplam calisma    : %s' % sure_yaz_sn(d.get('toplam_sure_sn', 0)),
                'Dosya guncellendi : %s' % simdi(),
                '',
                'Zincir uzunluklari (tam uzunluk):']
    satirlar += ['  %-5s = %22s' % ('P%d' % k, nokta(s[k])) for k in range(1, SON_TAM + 1)]
    satirlar.append('  %-5s = %22s' % ('P%d+' % (SON_TAM + 1), nokta(s[SON_TAM + 1])))
    satirlar += ['',
                 '  %-21s = %22s' % ('Dongu', nokta(d['dongu'])),
                 '  %-21s = %22s' % ('Asal toplami', nokta(d['asal_toplami'])),
                 '  %-21s = %22s' % ('64 bit ustu MR testi', nokta(d['64_bit_ustu_mr_test']))]
    atomic_txt(folder/SAYAC_DOSYASI, '\n'.join(satirlar) + '\n')


def checkpoint_oku(path):
    alanlar = {}
    with open(path, 'r', encoding='utf-8') as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith('#'):
                continue
            anahtar, ayrac, deger = satir.partition(' = ')
            if not ayrac:
                anahtar, deger = satir.rstrip('=').strip(), ''
            alanlar[anahtar] = deger
    try:
        d = {'format': alanlar['format']}
        for k in CK_SAYI_ALANLARI + CK_TOPLAM_ALANLARI:
            d[k] = int(alanlar[k])
        d['sayac_tam_uzunluk'] = [0] + [int(alanlar['P%d' % k]) for k in range(1, SON_TAM + 1)] + [int(alanlar['P%d+' % (SON_TAM + 1)])]
    except (KeyError, ValueError) as e:
        raise RuntimeError('Checkpoint TXT okunamadı (%s). SİLMEYİN.' % e)
    d['son_bolum_dosyalari'] = [x for x in alanlar.get('son_bolum_dosyalari', '').split(',') if x]
    d['son_bolum_sha256'] = alanlar.get('son_bolum_sha256', '')
    try:
        d['toplam_sure_sn'] = int(alanlar.get('toplam_sure_sn') or 0)
    except ValueError:
        d['toplam_sure_sn'] = 0
    for k in CK_TARIH_ALANLARI:
        if alanlar.get(k):
            d[k] = alanlar[k]
    return d


# Her zincir uzunlugu kendi klasorune yazilir; bolum dosyalari bu sirayla yazilir ve ozetlenir.
KATEGORILER = tuple('P%d' % k for k in range(6, SON_TAM + 1)) + ('P%d_PLUS' % (SON_TAM + 1), 'DONGU')
ESKI_YAPI = ('ZINCIRLER_P6_PLUS', 'P6_TUM_TERIMLER_TXT', 'PATI_CHECKPOINT.json')


def zincir_kategorisi(length, status):
    if status == 'dongu':
        return 'DONGU'
    return 'P%d' % length if length <= SON_TAM else 'P%d_PLUS' % (SON_TAM + 1)


def kategori_dosyasi(kat, alt, ust):
    """Sonuc klasorune gore goreli yol, orn. 'P7/P7_5000000000000_5001000000000.txt'."""
    return '%s/%s_%d_%d.txt' % (kat, kat, alt, ust)


def zincir_dosya_basligi(kat, alt, ust):
    return ('# PATI KED %s zincirleri | %d - %d\n'
            '# * isaretli sonlanma: 2^64 ustu terim olasilikli MR testiyle denendi (digerleri kesin)\n'
            '# UZ   BASLANGIC         SONLANMA  ZINCIR\n') % (kat.replace('_PLUS', '+'), alt, ust)


def zincir_satiri(p1, length, chain, status, nlarge):
    return '%-5s %-17d %-9s %s\n' % ('P%d' % length, p1, status + ('*' if nlarge else ''),
                                     ' > '.join(map(str, chain)))


def bolum_ozeti(folder, dosyalar):
    """Bir bolumde yazilan tum kategori dosyalarinin (sirayla) tek SHA256 ozeti."""
    h = hashlib.sha256()
    for goreli in dosyalar:
        h.update(goreli.encode('utf-8') + b'\n')
        h.update((folder/goreli).read_bytes())
    return h.hexdigest()


def new_counts():
    return [0]*SAYAC_BOYU  # P1–P20 TAM uzunluk, P21+ birlikte, indeks 0 kullanılmaz


def zincir_metni(p1, length, chain, status):
    satirlar = ['=' * 56, 'P%d ZINCIRI BULUNDU' % length,
                'Baslangic: %d' % p1, 'Uzunluk: %d' % length]
    for i, n in enumerate(chain, 1):
        satirlar.append('p%d = %d' % (i, n))
    satirlar.append('Sonlanma: ' + status)
    satirlar.append('')
    return '\n'.join(satirlar) + '\n'


def eski_yapi_kontrol(folder):
    eski = [ad for ad in ESKI_YAPI if (folder/ad).exists()]
    if eski:
        raise RuntimeError('Bu sonuç klasöründe eski yapıda kayıtlar var (%s). Klasörü arşivleyip kaldırın '
                           'ya da başka bir --output kullanın.' % ', '.join(eski))


def check_checkpoint(d, start, end, chunk, block, folder):
    if d.get('format') != FORMAT or any(d.get(k)!=v for k,v in
        (('baslangic',start),('bitis',end),('kayit_adimi',chunk),('elek_blogu',block))):
        raise RuntimeError('Checkpoint başka bir sürüme veya aralığa ait. SILMEYIN.')
    limit = d.get('tamamlanan_sinir')
    if not isinstance(limit,int) or not (start <= limit <= end):
        raise RuntimeError('Checkpoint tamamlanan sınırı geçersiz.')
    if limit < end and (limit-start)%chunk:
        raise RuntimeError('Checkpoint adım sınırına denk gelmiyor.')
    counts=d.get('sayac_tam_uzunluk')
    if not isinstance(counts,list) or len(counts)!=SAYAC_BOYU or any(type(n)!=int or n<0 for n in counts):
        raise RuntimeError('Checkpoint sayaçları geçersiz.')
    if limit>start:
        if not d.get('son_bolum_sha256'):
            raise RuntimeError('Checkpoint son kayıt kanıtı eksik.')
        for goreli in d['son_bolum_dosyalari']:
            if not (folder/goreli).is_file():
                raise RuntimeError('Checkpoint var ama zincir kayıt dosyası EKSİK: ' + str(folder/goreli))
        if bolum_ozeti(folder, d['son_bolum_dosyalari']) != d['son_bolum_sha256']:
            raise RuntimeError('Son kaydedilen zincir dosyalarının SHA256 doğrulaması başarısız; kayıtlar değiştirilmiş olabilir.')
    return limit


def simdi():
    return datetime.datetime.now().strftime(TARIH_BICIMI)


def sure_yaz(saniye):
    saniye = int(saniye)
    gun, saniye = divmod(saniye, 86400)
    saat, saniye = divmod(saniye, 3600)
    dakika = saniye // 60
    if gun:
        return '%d gün %d sa %d dk' % (gun, saat, dakika)
    return '%d sa %d dk' % (saat, dakika)


def sure_yaz_sn(saniye):
    """Gecen sure: '2 gün 03:04:05' ya da '03:04:05'."""
    saniye = int(saniye)
    gun, saniye = divmod(saniye, 86400)
    saat, saniye = divmod(saniye, 3600)
    dakika, saniye = divmod(saniye, 60)
    metin = '%02d:%02d:%02d' % (saat, dakika, saniye)
    return '%d gün %s' % (gun, metin) if gun else metin


TARAMALAR_KLASORU = Path(__file__).resolve().parent/'PATI_TARAMALAR'
MAKS_BITIS = 10**16  # taban asallar sqrt(bitis)'e kadar bellekte tutulur


def nokta(n):
    return f'{n:,}'.replace(',', '.')


def aralik_klasoru(start, end):
    """Her tarama araligi kendi klasorunde: PATI_TARAMALAR/ARALIK_5.000.000.000.000_10.000.000.000.000"""
    return TARAMALAR_KLASORU/('ARALIK_%s_%s' % (nokta(start), nokta(end)))


def sayi_oku(metin):
    """'5.000.000.000.000', '5,000,000,000,000', '5 000 000 000 000' veya '5000000000000' kabul edilir."""
    temiz = ''.join(ch for ch in metin if ch not in ' .,_\'')
    if not temiz.isdigit():
        raise ValueError('Geçersiz sayı: %r' % metin)
    return int(temiz)


def aralik_hatasi(start, end):
    if start < 3:
        return 'Başlangıç en az 3 olmalı.'
    if start >= end:
        return 'Bitiş, başlangıçtan büyük olmalı.'
    if end > MAKS_BITIS:
        return 'Bitiş en fazla %s olabilir.' % nokta(MAKS_BITIS)
    return None


def gunluge_yaz(output, satir):
    with open(output/'CALISMA_GUNLUGU.txt', 'a', encoding='utf-8') as f:
        f.write(satir + '\n')


# ---------------------------------------------------------------- isci tarafi

_temel_asallar = []


def isci_baslat(end):
    global _temel_asallar
    # Durdurmayi ana islem yonetir; isciler Ctrl+C ile kendiliginden olmez.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _temel_asallar = temel_asallari_bul(math.isqrt(end-1))
    # Zincir taramasi dongusel nesne uretmez; cop toplayici seyrek calissin.
    gc.freeze()
    gc.set_threshold(100000, 50, 100)


def blok_isle(aralik, gcd=math.gcd, ked=ked, asal_64=asal_64):
    """Bir elek blogunu tarar; sonuclari blok sirasiyla yazilmak uzere ana isleme dondurur."""
    subalt, subust = aralik
    counts = new_counts()
    tek = asil = cycles = prob = 0
    kayitlar = []
    zincirler = []
    for p1 in elekteki_asallar(subalt, subust, _temel_asallar):
        n = ked(p1)
        # Hizli yol: asallarin ~%90'i ilk adimda bilesige gider (P1).
        if n != p1 and n < U64 and ((n > 199 and gcd(n, ON_CARPIM) != 1) or not asal_64(n)):
            tek += 1
            continue
        length, chain, status, nlarge = zinciri_incele(p1, n if n < U64 else None)
        asil += 1
        prob += nlarge
        if status == 'dongu':
            cycles += 1
        else:
            counts[min(length, SON_TAM + 1)] += 1
        if length >= 6 or status == 'dongu':
            kayitlar.append((zincir_kategorisi(length, status), zincir_satiri(p1, length, chain, status, nlarge)))
            if length >= 6:
                zincirler.append((length, zincir_metni(p1, length, chain, status)))
    counts[1] += tek
    return counts, asil + tek, cycles, prob, kayitlar, zincirler


# ---------------------------------------------------------------- C hesap cekirdegi

C_DLL_ADI = 'ked_cekirdek.dll'
C_DURUMLAR = ('bilesik', 'sabit', 'dongu')
C_PYTHONA = 3  # zincir 64 biti asti: Python'da orijinal yontemle incelenir
C_GOREV_BLOK = 10  # C ile her gorev 10 elek blogu (bolum sinirlarina tam bolunur)
C_GPU_KAYNAGI = 'ked_gpu.cl'
_c = None
_c_taban = None
_c_blok = ELEK_BLOGU
_c_fonk = None  # ked_aralik (yalniz CPU) ya da ked_aralik_gpu (GPU bossa GPU, degilse CPU)
_gpu = None  # (kullanilabilir_mi, kart adi ya da neden)


def c_cekirdegi_yukle():
    """ked_cekirdek.dll yuklenebilirse onu, yoksa None dondurur (o zaman Python islemleri kullanilir)."""
    global _c
    if _c is None:
        try:
            import ctypes
            dll = ctypes.CDLL(str(Path(__file__).resolve().parent/C_DLL_ADI))
            u64, p64 = ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64)
            for fonk in (dll.ked_aralik, getattr(dll, 'ked_aralik_gpu', None)):
                if fonk is not None:
                    fonk.argtypes = [u64, u64, u64, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int64,
                                     p64, p64, ctypes.c_int64, ctypes.POINTER(ctypes.c_int64)]
                    fonk.restype = ctypes.c_int
            dll.ked_hazirla()
            _c = dll
        except (OSError, AttributeError):
            return None
    return _c


def gpu_hazirla():
    """Ekran kartini (OpenCL) bir kez hazirlar. Donus: (kullanilabilir_mi, kart adi ya da neden)."""
    global _gpu
    if _gpu is None:
        dll = c_cekirdegi_yukle()
        kaynak_yolu = Path(__file__).resolve().parent/C_GPU_KAYNAGI
        if dll is None or not hasattr(dll, 'ked_gpu_hazirla'):
            _gpu = (False, '%s GPU desteklemiyor' % C_DLL_ADI)
        elif not kaynak_yolu.is_file():
            _gpu = (False, '%s bulunamadı' % C_GPU_KAYNAGI)
        else:
            import ctypes
            ad = ctypes.create_string_buffer(8192)
            tamam = dll.ked_gpu_hazirla(kaynak_yolu.read_bytes(), ad, len(ad))
            _gpu = (bool(tamam), ad.value.decode('utf-8', 'replace').strip())
    return _gpu


def gpu_istatistik():
    """(GPU'da, CPU'da) zinciri incelenen asal sayisi; GPU yoksa None."""
    if _c is None or not hasattr(_c, 'ked_gpu_istatistik'):
        return None
    import ctypes
    g, c = ctypes.c_uint64(), ctypes.c_uint64()
    _c.ked_gpu_istatistik(ctypes.byref(g), ctypes.byref(c))
    return g.value, c.value


def c_hazirla(end, block, gpu_ile):
    global _c_taban, _c_blok, _c_fonk
    import ctypes
    taban = temel_asallari_bul(math.isqrt(end-1))
    _c_taban = (ctypes.c_uint32 * len(taban))(*taban)
    _c_blok = block
    _c_fonk = _c.ked_aralik_gpu if gpu_ile else _c.ked_aralik


def blok_isle_c(aralik):
    """blok_isle ile ayni sonucu C cekirdegiyle uretir (is parcaciginda calisir, C kismi GIL'i birakir)."""
    import ctypes
    alt, ust = aralik
    sayac = (ctypes.c_uint64 * (SAYAC_BOYU + 2))()
    uz = ctypes.c_int64()
    kapasite = 1 << 15
    while True:
        cikti = (ctypes.c_uint64 * kapasite)()
        r = _c_fonk(alt, ust, _c_blok, _c_taban, len(_c_taban), sayac, cikti, kapasite, ctypes.byref(uz))
        if r == 0:
            break
        if r == -3:
            raise RuntimeError('GPU ile CPU bir zincirde farklı sonuç verdi (%d–%d). Tarama durduruldu; '
                               'GPU kapalı yeniden başlatın.' % (alt, ust))
        if r != -1:
            raise RuntimeError('C çekirdeği hata verdi: %d' % r)
        kapasite *= 4
    counts = list(sayac[:SAYAC_BOYU])
    asil, cycles, prob = sayac[SAYAC_BOYU], sayac[SAYAC_BOYU + 1], 0
    kayitlar = []
    zincirler = []
    veri = cikti[:uz.value]
    i = 0
    while i < len(veri):
        p1, durum, length = veri[i], veri[i+1], veri[i+2]
        if durum == C_PYTHONA:
            i += 3
            length, chain, status, nlarge = zinciri_incele(p1)
            asil += 1
            prob += nlarge
            if status == 'dongu':
                cycles += 1
            else:
                counts[min(length, SON_TAM + 1)] += 1
        else:
            chain = veri[i+3:i+3+length]
            i += 3 + length
            status, nlarge = C_DURUMLAR[durum], 0
        if length >= 6 or status == 'dongu':
            kayitlar.append((zincir_kategorisi(length, status), zincir_satiri(p1, length, chain, status, nlarge)))
            if length >= 6:
                zincirler.append((length, zincir_metni(p1, length, chain, status)))
    return counts, asil, cycles, prob, kayitlar, zincirler


# ---------------------------------------------------------------- tarama

GPU_EK_ISCI = 4  # GPU'yu bekleyen is parcaciklarini telafi eder (ked_cekirdek.c GPU_YUVA)


def maks_isci():
    return (os.cpu_count() or 1) + GPU_EK_ISCI


def tara(start, end, block, chunk, output, show_min, cooldown, isci_al, olay, dur, python_zorla=False,
         gpu_kullan=True):
    """Taramayi yurutur. isci_al() o anki istenen isci sayisini verir (calisirken degisebilir).
    olay(tur, veri) ile ilerleme bildirir; dur (threading.Event) kurulunca durur.
    ked_cekirdek.dll varsa hesap C'de (is parcaciklariyla), yoksa Python islemleriyle yapilir.
    gpu_kullan ve ekran karti uygunsa zincirler GPU bos oldukca GPU'da hesaplanir."""
    if output.exists() and not output.is_dir():
        raise RuntimeError('Çıktı klasörü yerine bir dosya var: '+str(output))
    output.mkdir(parents=True,exist_ok=True)
    eski_yapi_kontrol(output)
    ckpath=output/CHECKPOINT_ADI
    if ckpath.is_file():
        d=checkpoint_oku(ckpath)
        alt=check_checkpoint(d,start,end,chunk,block,output)
    else:
        if any(next((output/kat).glob('*.txt'), None) for kat in KATEGORILER if (output/kat).is_dir()):
            raise RuntimeError('Checkpoint yok, fakat zincir kayıtları var! SİLMEYİN; önce kurtarma gerek.')
        alt=start
        d={'format':FORMAT,'baslangic':start,'bitis':end,'elek_blogu':block,
           'kayit_adimi':chunk,'tamamlanan_sinir':start,
           'sayac_tam_uzunluk':new_counts(),'asal_toplami':0,
           'dongu':0,'64_bit_ustu_mr_test':0,'son_bolum_dosyalari':[],'son_bolum_sha256':''}
    for kat in KATEGORILER[:-1]:  # DONGU klasoru yalnizca dongu bulunursa acilir
        (output/kat).mkdir(exist_ok=True)
    if 'tarama_baslama_tarihi' not in d:
        d['tarama_baslama_tarihi'] = simdi()
        checkpoint_yaz(ckpath, d)
    if alt >= end:
        olay('bitti', d)
        return

    def istenen_isci():
        return max(1, min(maks, int(isci_al())))

    maks = max(maks_isci(), int(isci_al()))
    isci = istenen_isci()
    c_var = not python_zorla and c_cekirdegi_yukle() is not None
    motor = 'C (%s)' % C_DLL_ADI if c_var else 'Python'
    gpu_ile = False
    if c_var and gpu_kullan:
        gpu_ile, gpu_adi = gpu_hazirla()
        motor = 'C + GPU (%s)' % gpu_adi if gpu_ile else 'C (GPU kullanılamadı: %s)' % gpu_adi[:200]
    gpu_baz = gpu_istatistik() if gpu_ile else None
    oturum_baslama = simdi()
    gunluge_yaz(output, '%s | OTURUM BASLADI | kaldigi yer %s | isci %d | motor %s' % (
        oturum_baslama, f'{alt:,}', isci, motor))
    t_oturum = time.monotonic()  # toplam_sure_sn = onceki oturumlar + bu oturum
    sure_baz = d.get('toplam_sure_sn', 0)
    olay('basladi', {'d': d, 'oturum_baslama': oturum_baslama, 'txtdir': str(output), 'isci': isci, 'motor': motor})

    def ilerleme(konum):
        v = ilerleme_verisi(start, end, konum, hiz_penceresi, isci)
        if gpu_baz is not None:
            g, c = gpu_istatistik()
            g, c = g - gpu_baz[0], c - gpu_baz[1]
            v['gpu_payi'] = 100.0 * g / (g + c) if g + c else 0.0
        return v
    son_bildirim = 0.0
    # Son ~30 sn'lik hiz: isci sayisi degisince kalan sure hemen guncellenir. (zaman, konum, incelenen asal)
    hiz_penceresi = collections.deque([(time.monotonic(), alt, 0)])
    oturum_asal = 0
    # Havuz en fazla cekirdek kadar isci acar; ayni anda en fazla 'isci' kadar gorev verilir,
    # fazlasi bosta bekler (CPU harcamaz). Boylece sayi calisirken artirilip azaltilabilir.
    if c_var:
        from multiprocessing.pool import ThreadPool
        c_hazirla(end, block, gpu_ile)
        havuz = ThreadPool(maks)
        isle = blok_isle_c
        gorev_boyu = block * C_GOREV_BLOK
    else:
        havuz = mp.Pool(maks, initializer=isci_baslat, initargs=(end,))
        isle = blok_isle
        gorev_boyu = block
    olay('havuz_hazir', None)
    uyandir = threading.Event()
    def haber(_):
        uyandir.set()
    # Gorevler 1 milyarlik bolum sinirini asmaz; gorev icindeki elek bloklari Python surumuyle aynidir.
    gorev_akisi = ((s, min(s+gorev_boyu, b+chunk, end)) for b in range(alt, end, chunk)
                   for s in range(b, min(b+chunk, end), gorev_boyu))
    bekleyen = collections.deque()
    gorevler_bitti = False
    bolum = None

    def bolum_ac(b_alt):
        # Kayitlar bellekte toplanir (bolum basina birkac yuz satir); bolum bitince dosyalara yazilir.
        return {'alt': b_alt, 'ust': min(b_alt+chunk, end), 'counts': new_counts(), 'asil': 0, 'cycles': 0,
                'prob': 0, 'kayit': {kat: [] for kat in KATEGORILER}}

    try:
        while True:
            uyandir.clear()
            yeni_isci = istenen_isci()
            if yeni_isci != isci:
                gunluge_yaz(output, '%s | ISCI SAYISI DEGISTI | %d -> %d' % (simdi(), isci, yeni_isci))
                olay('isci', {'eski': isci, 'yeni': yeni_isci})
                isci = yeni_isci
            if dur.is_set():
                break
            # Gorev doldur: calisan sayisi 'isci'yi, bekleyen sonuc tamponu sinirini asmasin.
            calisan = sum(1 for _, r in bekleyen if not r.ready())
            while not gorevler_bitti and calisan < isci and len(bekleyen) < 2*isci + 4:
                g = next(gorev_akisi, None)
                if g is None:
                    gorevler_bitti = True
                    break
                bekleyen.append((g, havuz.apply_async(isle, (g,), callback=haber, error_callback=haber)))
                calisan += 1
            if not bekleyen:
                break
            (sa, su), sonuc = bekleyen[0]
            if not sonuc.ready():
                uyandir.wait(0.5)
                continue
            bekleyen.popleft()
            # Sonuclar blok sirasiyla islenir: dosyalar tek islemli surumle ayni sirada olur.
            counts, asil, cycles, prob, kayitlar, zincirler = sonuc.get()
            if bolum is None:
                bolum = bolum_ac(sa)
            bc = bolum['counts']
            for k in range(SAYAC_BOYU):
                bc[k] += counts[k]
            bolum['asil'] += asil
            bolum['cycles'] += cycles
            bolum['prob'] += prob
            for kat, satir in kayitlar:
                bolum['kayit'][kat].append(satir)
            for length, metin in zincirler:
                if length >= show_min:
                    olay('zincir', metin)
            simdiki = time.monotonic()
            oturum_asal += asil
            hiz_penceresi.append((simdiki, su, oturum_asal))
            while len(hiz_penceresi) > 2 and simdiki - hiz_penceresi[1][0] >= 30:
                hiz_penceresi.popleft()
            if simdiki - son_bildirim >= 0.5:
                son_bildirim = simdiki
                olay('ilerleme', ilerleme(su))
            if su < bolum['ust']:
                continue
            # --- bolum tamamlandi: kalici yap
            b = bolum
            bolum = None
            # Her uzunluk kendi klasorune; o uzunlukta zincir yoksa dosya acilmaz. Yarida kesilirse
            # checkpoint guncellenmedigi icin bolum yeniden taranir ve ayni dosyalar ayni icerikle yazilir.
            dosyalar = []
            for kat in KATEGORILER:
                if b['kayit'][kat]:
                    goreli = kategori_dosyasi(kat, b['alt'], b['ust'])
                    (output/kat).mkdir(exist_ok=True)
                    atomic_txt(output/goreli, zincir_dosya_basligi(kat, b['alt'], b['ust']) + ''.join(b['kayit'][kat]))
                    dosyalar.append(goreli)
            newd=dict(d)
            newd['tamamlanan_sinir']=b['ust']
            newd['sayac_tam_uzunluk']=[x+y for x,y in zip(d['sayac_tam_uzunluk'],b['counts'])]
            newd['asal_toplami']=d['asal_toplami']+b['asil']
            newd['dongu']=d['dongu']+b['cycles']
            newd['64_bit_ustu_mr_test']=d['64_bit_ustu_mr_test']+b['prob']
            newd['son_bolum_dosyalari']=dosyalar
            newd['son_bolum_sha256']=bolum_ozeti(output, dosyalar)
            if sum(newd['sayac_tam_uzunluk'])+newd['dongu'] != newd['asal_toplami']:
                raise RuntimeError('Sayaçların asal toplamı ile uyuşmazlığı!')
            if b['ust'] >= end:
                newd['tarama_bitis_tarihi'] = simdi()
            newd['toplam_sure_sn'] = sure_baz + int(time.monotonic() - t_oturum)
            checkpoint_yaz(ckpath,newd)
            d=newd
            alt=b['ust']
            olay('kayit', {'d': d, 'chunk_asil': b['asil'],
                           'ilerleme': ilerleme(alt)})
            if cooldown and dur.wait(cooldown):
                break
    finally:
        # Yarim bolum yalnizca bellekteydi; kalici degildir, bir dahaki sefere bastan taranir.
        havuz.terminate()
        havuz.join()
    if alt >= end:
        gunluge_yaz(output, '%s | TARAMA TAMAMLANDI | baslama %s | bitis %s' % (
            simdi(), d['tarama_baslama_tarihi'], d['tarama_bitis_tarihi']))
        olay('bitti', d)
    else:
        # Durdurulunca son kayittan sonraki calisma suresi de toplama eklenir (sinir ve sayaclar ayni kalir).
        d = dict(d)
        d['toplam_sure_sn'] = sure_baz + int(time.monotonic() - t_oturum)
        checkpoint_yaz(ckpath, d)
        gunluge_yaz(output, '%s | OTURUM DURDURULDU | son kalici sinir %s | toplam calisma %s' % (
            simdi(), f'{alt:,}', sure_yaz_sn(d['toplam_sure_sn'])))
        olay('durdu', d)


def ilerleme_verisi(start, end, konum, hiz_penceresi, isci):
    yuzde = 100 * (konum - start) / (end - start)
    (t_ilk, k_ilk, a_ilk), (t_son, k_son, a_son) = hiz_penceresi[0], hiz_penceresi[-1]
    hiz = (k_son - k_ilk) / (t_son - t_ilk) if t_son > t_ilk else 0
    asal_hiz = (a_son - a_ilk) / (t_son - t_ilk) if t_son > t_ilk else 0
    kalan = (end - konum) / hiz if hiz > 0 else None
    tahmini_bitis = None
    if kalan is not None:
        tahmini_bitis = (datetime.datetime.now() + datetime.timedelta(seconds=kalan)).strftime(TARIH_BICIMI)
    return {'konum': konum, 'yuzde': yuzde, 'hiz': hiz, 'asal_hiz': asal_hiz, 'kalan': kalan,
            'tahmini_bitis': tahmini_bitis, 'isci': isci}


def checkpoint_oku_sessiz(output, start, end, chunk, block):
    """Pencere acilirken mevcut durumu gostermek icin; hata varsa (None, mesaj) doner."""
    try:
        eski_yapi_kontrol(output)
        ckpath = output/CHECKPOINT_ADI
        if not ckpath.is_file():
            return None, None
        d = checkpoint_oku(ckpath)
        check_checkpoint(d, start, end, chunk, block, output)
        if not (output/SAYAC_DOSYASI).exists():
            sayac_dosyasi_yaz(output, d)
        return d, None
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------- mail bildirimi

MAIL_AYAR_DOSYASI = 'MAIL_AYARLARI.txt'
MAIL_SABLONU = """# PATI KED mail bildirimi ayarlari. Bu dosya yalnizca bu bilgisayarda durur; kimseyle paylasmayin.
# Gmail icin:
#   1) Google hesabinizda 2 adimli dogrulamayi acin.
#   2) https://myaccount.google.com/apppasswords adresinden bir 'uygulama sifresi' olusturun.
#   3) Asagiya gonderen Gmail adresini ve o 16 harfli uygulama sifresini yazin.
#      NORMAL GMAIL SIFRENIZI YAZMAYIN.
# alici: raporlarin gidecegi adres(ler). Birden fazla adresi virgul, noktali virgul ya da
#        bosluk ile ayirin. Ornek: alici = ali@ornek.com, ayse@ornek.com
gonderen =
uygulama_sifresi =
alici =
sunucu = smtp.gmail.com
port = 465
dakika = 15
"""
MAIL_ZINCIR_ESIGI = 9  # bu uzunluk ve ustu zincirler maile ayrica yazilir


def mail_ayar_yolu():
    return Path(__file__).resolve().parent/MAIL_AYAR_DOSYASI


def mail_ayarlarini_oku():
    """(ayar, None) ya da (None, hata metni). Dosya yoksa doldurulacak sablonu olusturur."""
    yol = mail_ayar_yolu()
    if not yol.is_file():
        atomic_txt(yol, MAIL_SABLONU)
        return None, 'Mail ayar dosyası oluşturuldu, doldurmanız gerekiyor: %s' % yol
    alan = {}
    for satir in yol.read_text(encoding='utf-8').splitlines():
        satir = satir.strip()
        if satir and not satir.startswith('#') and '=' in satir:
            k, v = satir.split('=', 1)
            alan[k.strip()] = v.strip()
    eksik = [k for k in ('gonderen', 'uygulama_sifresi', 'alici') if not alan.get(k)]
    if eksik:
        return None, '%s içinde eksik: %s (%s)' % (MAIL_AYAR_DOSYASI, ', '.join(eksik), yol)
    alicilar = [x for x in alan['alici'].replace(';', ' ').replace(',', ' ').split() if x]
    hatali = [x for x in alicilar if x.count('@') != 1 or '.' not in x.split('@')[1]]
    if hatali:
        return None, '%s içinde geçersiz alıcı adresi: %s' % (MAIL_AYAR_DOSYASI, ', '.join(hatali))
    try:
        port = int(alan.get('port') or 465)
        dakika = float(alan.get('dakika') or 15)
    except ValueError:
        return None, '%s içinde port ve dakika sayı olmalı.' % MAIL_AYAR_DOSYASI
    return {'gonderen': alan['gonderen'], 'sifre': alan['uygulama_sifresi'].replace(' ', ''),
            'alici': ', '.join(alicilar), 'alicilar': alicilar, 'sunucu': alan.get('sunucu') or 'smtp.gmail.com',
            'port': port, 'dakika': max(1.0, dakika)}, None


def mail_gonder(ayar, konu, govde):
    """Maili gonderir; basariliysa None, degilse hata metni dondurur."""
    import smtplib
    import ssl
    from email.message import EmailMessage
    m = EmailMessage()
    m['Subject'] = konu
    m['From'] = ayar['gonderen']
    m['To'] = ayar['alici']
    m.set_content(govde)
    hatalar = []
    # Sunucu girisi yanitsiz keserse yeni baglantiyla diger giris yontemi denenir (Gmail bazen PLAIN'i keser).
    for yontem in (None, 'LOGIN', 'PLAIN'):
        asama = 'sunucuya bağlanma (%s:%d)' % (ayar['sunucu'], ayar['port'])
        try:
            baglam = ssl.create_default_context()
            if ayar['port'] == 465:
                s = smtplib.SMTP_SSL(ayar['sunucu'], 465, context=baglam, timeout=30)
            else:
                s = smtplib.SMTP(ayar['sunucu'], ayar['port'], timeout=30)
                if ayar['sunucu'] not in ('localhost', '127.0.0.1'):
                    asama = 'şifreli bağlantı (STARTTLS)'
                    s.starttls(context=baglam)
            with s:
                asama = 'giriş (%s)' % (yontem or 'varsayılan yöntem')
                if yontem:
                    s.ehlo_or_helo_if_needed()
                    if yontem not in s.esmtp_features.get('auth', '').upper().split():
                        continue
                    s.esmtp_features['auth'] = yontem
                s.login(ayar['gonderen'], ayar['sifre'])
                asama = 'gönderme (%d alıcı)' % len(ayar['alicilar'])
                s.send_message(m, to_addrs=ayar['alicilar'])
            return None
        except smtplib.SMTPAuthenticationError as e:
            return ('giriş reddedildi (%s): %s. Uygulama şifresini ve gönderen adresini kontrol edin; '
                    'şifre silindiyse yenisini oluşturun.' % (e.smtp_code, e.smtp_error.decode('utf-8', 'replace')[:200]))
        except smtplib.SMTPServerDisconnected as e:
            hatalar.append('%s aşamasında bağlantı kesildi (%s)' % (asama, e))
            if not asama.startswith('giriş'):
                break
        except Exception as e:
            hatalar.append('%s aşamasında %s: %s' % (asama, type(e).__name__, e))
            break
    return ' | '.join(hatalar)


class MailBildirici:
    """tara'nin olay(...) cagrilarini aynen iletir; ayrica baslangicta, her 'dakika'da bir ve tarama
    bitince/durunca/hata verince sayaclari (SAYACLAR.txt) ve ilerlemeyi maille gonderir.
    Mail gonderimi ayri is parcaciginda yapilir; tarama beklemez."""

    def __init__(self, ayar, olay, dakika=None):
        self.ayar, self.olay = ayar, olay
        self.dakika = dakika or ayar['dakika']
        self.son = None
        self.klasor = None
        self.d = None
        self.ilerleme = {}
        self.motor = ''
        self.uzunlar = []

    def __call__(self, tur, veri):
        self.olay(tur, veri)
        try:
            if tur == 'basladi':
                self.klasor, self.motor, self.d = Path(veri['txtdir']), veri['motor'], veri['d']
                self.son = time.monotonic()
                self.gonder('başladı')
            elif tur == 'ilerleme':
                self.ilerleme = veri
            elif tur == 'kayit':
                self.ilerleme, self.d = veri['ilerleme'], veri['d']
            elif tur == 'zincir':
                satirlar = veri.splitlines()
                uz = int(satirlar[1].split()[0][1:])
                if uz >= MAIL_ZINCIR_ESIGI:
                    self.uzunlar.append('P%d  %s' % (uz, satirlar[2].split(':', 1)[1].strip()))
            elif tur in ('bitti', 'durdu') and self.klasor is not None:
                self.d = veri
                self.gonder('TAMAMLANDI' if tur == 'bitti' else 'durduruldu', bekle=True)
                self.son = None
            if (self.son is not None and tur in ('ilerleme', 'kayit')
                    and time.monotonic() - self.son >= self.dakika * 60):
                self.son = time.monotonic()
                self.gonder('ara rapor')
        except Exception as e:
            self.olay('mail', 'Mail hazırlanamadı: %s' % e)

    def hata(self, mesaj):
        if self.klasor is not None:
            self.gonder('HATA: ' + mesaj[:200], bekle=True)

    def metin(self, durum):
        d, i = self.d, self.ilerleme
        bas, bit = d['baslangic'], d['bitis']
        konum = max(d['tamamlanan_sinir'], i.get('konum', 0))
        yuzde = 100 * (konum - bas) / (bit - bas)
        konu = 'PATİ KED | %s | %%%.2f | %s – %s' % (durum, yuzde, nokta(bas), nokta(bit))
        satirlar = ['Durum            : %s' % durum,
                    'Zaman            : %s' % simdi(),
                    'Aralık           : %s – %s' % (nokta(bas), nokta(bit)),
                    'Taranan sınır    : %s  (%%%.3f)' % (nokta(konum), yuzde),
                    'Son kalıcı kayıt : %s' % nokta(d['tamamlanan_sinir'])]
        if i and durum not in ('TAMAMLANDI', 'durduruldu'):
            satirlar += ['Hız              : %s sayı/sn' % f'{i["hiz"]:,.0f}',
                         'Test edilen asal : %s asal/sn' % f'{i["asal_hiz"]:,.0f}',
                         'Aktif işçi       : %s' % i.get('isci', '-'),
                         'Kalan süre       : %s' % (sure_yaz(i['kalan']) if i.get('kalan') is not None else '-'),
                         'Tahmini bitiş    : %s' % (i.get('tahmini_bitis') or '-')]
        satirlar += ['Hesap motoru     : %s' % self.motor,
                     'Sonuç klasörü    : %s' % self.klasor, '']
        if self.uzunlar:
            satirlar += ['Son rapordan beri bulunan P%d+ zincirler:' % MAIL_ZINCIR_ESIGI] + \
                        ['  ' + z for z in self.uzunlar] + ['']
            self.uzunlar = []
        sayac = self.klasor/SAYAC_DOSYASI
        if sayac.is_file():
            satirlar.append(sayac.read_text(encoding='utf-8'))
        return konu, '\n'.join(satirlar)

    def gonder(self, durum, bekle=False):
        konu, govde = self.metin(durum)

        def is_():
            h = mail_gonder(self.ayar, konu, govde)
            self.olay('mail', ('Mail gönderildi (%s) -> %s' % (durum, self.ayar['alici'])) if h is None
                      else 'Mail gönderilemedi (%s): %s' % (durum, h))

        t = threading.Thread(target=is_, daemon=not bekle)
        t.start()
        if bekle:
            t.join(45)


# ---------------------------------------------------------------- konsol

def konsol_calistir(a):
    isci_durum = {'n': a.workers}
    girdi_basladi = []

    def olay(tur, veri):
        if tur == 'basladi':
            d = veri['d']
            print('PATI | %d ISCI | MOTOR %s | BASLANGIC %d BITIS %d | TAMAMLANDI %d' % (
                veri['isci'], veri['motor'], a.start, a.end, d['tamamlanan_sinir']), flush=True)
            print('TARAMA BASLAMA TARIHI:', d['tarama_baslama_tarihi'], '| BU OTURUM:', veri['oturum_baslama'], flush=True)
            print('SONUC KLASORU (P6, P7 ... P20, P21_PLUS):', veri['txtdir'], flush=True)
        elif tur == 'havuz_hazir':
            # Windows'ta stdin okuma bekleyen bir is parcacigi yeni islem acilmasini kilitleyebilir;
            # bu yuzden girdi ancak isciler acildiktan sonra okunur.
            if sys.stdin is not None and not girdi_basladi:
                girdi_basladi.append(True)
                threading.Thread(target=girdi_oku, daemon=True).start()
            print('Isci sayisini degistirmek icin sayi yazip Enter (1-%d). Durdurmak icin Ctrl+C.' % maks_isci(), flush=True)
        elif tur == 'isci':
            print('ISCI SAYISI: %d -> %d' % (veri['eski'], veri['yeni']), flush=True)
        elif tur == 'mail':
            print('MAIL:', veri, flush=True)
        elif tur == 'zincir':
            print(veri, flush=True)
        elif tur == 'kayit':
            d = veri['d']
            i = veri['ilerleme']
            s = d['sayac_tam_uzunluk']
            print('KAYDEDILDI: %s | Yeni asal %s | TOPLAM P10=%s P15=%s P20=%s P21+=%s | %%%.3f | %d isci%s | %s sayi/sn | %s asal/sn | kalan %s | tahmini bitis %s' % (
                f'{d["tamamlanan_sinir"]:,}', f'{veri["chunk_asil"]:,}', f'{s[10]:,}', f'{s[15]:,}', f'{s[20]:,}', f'{s[21]:,}',
                i['yuzde'], i['isci'], (' | GPU payi %%%.0f' % i['gpu_payi']) if 'gpu_payi' in i else '', f'{i["hiz"]:,.0f}', f'{i["asal_hiz"]:,.0f}',
                sure_yaz(i['kalan']) if i['kalan'] is not None else '-',
                i['tahmini_bitis'] or '-'), flush=True)
        elif tur == 'durdu':
            print('\nDURDURULDU. Son TAMAMLANAN ve kalıcı sınır:', veri['tamamlanan_sinir'], flush=True)
        elif tur == 'bitti':
            d = veri
            print('\nTARAMA TAMAMLANDI. Toplam asallar:', d['asal_toplami'])
            for k in range(1, SON_TAM + 1):
                print('P%d =' % k, d['sayac_tam_uzunluk'][k])
            print('P%d+ =' % (SON_TAM + 1), d['sayac_tam_uzunluk'][SON_TAM + 1])
            print('ASAL DONGU =', d['dongu'])
            print('64 BIT USTU MR TESTI =', d['64_bit_ustu_mr_test'])
            print('TARAMA BASLAMA:', d.get('tarama_baslama_tarihi'), '| BITIS:', d.get('tarama_bitis_tarihi'), flush=True)
            print('TOPLAM CALISMA SURESI:', sure_yaz_sn(d.get('toplam_sure_sn', 0)), flush=True)

    dur = threading.Event()
    hata = []

    konsol_olay = olay
    if a.mail:
        ayar, mail_hatasi = mail_ayarlarini_oku()
        if mail_hatasi:
            print('MAIL KAPALI:', mail_hatasi, flush=True)
        else:
            konsol_olay = MailBildirici(ayar, olay)
            print('Mail raporu: her %g dakikada bir -> %s' % (ayar['dakika'], ayar['alici']), flush=True)

    def calis():
        try:
            tara(a.start, a.end, a.block, a.chunk, a.output, a.show_min, a.cooldown,
                 lambda: isci_durum['n'], konsol_olay, dur, a.python, not a.gpusuz)
        except Exception as e:
            if isinstance(konsol_olay, MailBildirici):
                konsol_olay.hata(str(e))
            hata.append(e)

    def girdi_oku():
        for satir in sys.stdin:
            satir = satir.strip()
            if satir.isdigit() and 1 <= int(satir) <= maks_isci():
                isci_durum['n'] = int(satir)
            elif satir:
                print('Gecersiz: 1 ile %d arasinda bir sayi yazin.' % maks_isci(), flush=True)

    t = threading.Thread(target=calis)
    t.start()
    while t.is_alive():
        try:
            t.join(0.5)
        except KeyboardInterrupt:
            dur.set()
    if hata:
        raise hata[0]


# ---------------------------------------------------------------- pencere

def pencere_calistir(a):
    import tkinter as tk
    from tkinter import messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    kok = tk.Tk()
    kok.geometry('980x800')
    kok.minsize(820, 600)
    stil = ttk.Style()
    try:
        stil.theme_use('vista')
    except tk.TclError:
        pass
    stil.configure('Yuzde.TLabel', font=('Segoe UI', 26, 'bold'))
    stil.configure('Baslik.TLabel', font=('Segoe UI', 10, 'bold'))
    stil.configure('Deger.TLabel', font=('Consolas', 11))

    olaylar = queue.Queue()
    dur = threading.Event()
    durum = {'calisiyor': False, 'kapat': False}
    sure_durum = {'t0': None, 'baz': 0, 'son': None}  # calisirken her 200 ms'de gecen sure yenilenir

    # --- ust cubuk
    ust = ttk.Frame(kok, padding=(12, 10))
    ust.pack(fill='x')
    ttk.Label(ust, text='Çekirdek (işçi):').pack(side='left')
    isci_ust_sinir = max(maks_isci(), a.workers)
    isci_durum = {'n': a.workers}
    isci_var = tk.StringVar(value=str(a.workers))
    isci_kutu = ttk.Spinbox(ust, from_=1, to=isci_ust_sinir, width=5, textvariable=isci_var)
    isci_kutu.pack(side='left', padx=(6, 4))
    ttk.Label(ust, text='/ %d  (çalışırken değiştirilebilir)' % isci_ust_sinir).pack(side='left', padx=(0, 18))
    gpu_var = tk.BooleanVar(value=not a.gpusuz and not a.python)
    gpu_kutu = ttk.Checkbutton(ust, text='GPU kullan', variable=gpu_var, command=lambda: motoru_goster())
    gpu_kutu.pack(side='left', padx=(0, 18))

    def isci_degisti(*_):
        # Gecerli bir sayi yazilinca tarama bir sonraki gorevde yeni degeri kullanir.
        try:
            n = int(isci_var.get())
        except ValueError:
            return
        if 1 <= n <= isci_ust_sinir:
            isci_durum['n'] = n

    isci_var.trace_add('write', isci_degisti)
    baslat_dugme = ttk.Button(ust, text='▶ Başlat', width=12)
    baslat_dugme.pack(side='left')
    durdur_dugme = ttk.Button(ust, text='■ Durdur', width=12, state='disabled')
    durdur_dugme.pack(side='left', padx=6)
    ttk.Button(ust, text='Sonuç klasörünü aç',
               command=lambda: (secili['output'].mkdir(parents=True, exist_ok=True),
                                os.startfile(secili['output']))).pack(side='right')

    # --- tarama araligi: her aralik kendi klasorunde (P6 ... P20, P21_PLUS alt klasorleriyle)
    aralik_cubugu = ttk.Frame(kok, padding=(12, 0, 12, 6))
    aralik_cubugu.pack(fill='x')
    ttk.Label(aralik_cubugu, text='Başlangıç:').pack(side='left')
    bas_var = tk.StringVar(value=nokta(a.start))
    bas_kutu = ttk.Entry(aralik_cubugu, width=24, textvariable=bas_var, font=('Consolas', 10))
    bas_kutu.pack(side='left', padx=(6, 14))
    ttk.Label(aralik_cubugu, text='Bitiş:').pack(side='left')
    bit_var = tk.StringVar(value=nokta(a.end))
    bit_kutu = ttk.Entry(aralik_cubugu, width=24, textvariable=bit_var, font=('Consolas', 10))
    bit_kutu.pack(side='left', padx=(6, 14))
    uygula_dugme = ttk.Button(aralik_cubugu, text='Aralığı uygula', width=14)
    uygula_dugme.pack(side='left')
    ttk.Label(aralik_cubugu, text='Önceki taramalar:').pack(side='left', padx=(18, 6))
    onceki_kutu = ttk.Combobox(aralik_cubugu, state='readonly', width=30)
    onceki_kutu.pack(side='left', fill='x', expand=True)

    # --- mail bildirimi (ayarlar MAIL_AYARLARI.txt dosyasinda)
    mail_cubugu = ttk.Frame(kok, padding=(12, 0, 12, 6))
    mail_cubugu.pack(fill='x')
    mail_var = tk.BooleanVar(value=False)
    mail_kutu = ttk.Checkbutton(mail_cubugu, text='Sayaçları maille gönder, her', variable=mail_var)
    mail_kutu.pack(side='left')
    mail_dk_var = tk.StringVar(value='15')
    mail_dk_kutu = ttk.Spinbox(mail_cubugu, from_=1, to=1440, width=5, textvariable=mail_dk_var)
    mail_dk_kutu.pack(side='left', padx=(6, 4))
    ttk.Label(mail_cubugu, text='dakikada bir').pack(side='left', padx=(0, 14))
    mail_test_dugme = ttk.Button(mail_cubugu, text='Test maili gönder')
    mail_test_dugme.pack(side='left')
    mail_ayar_dugme = ttk.Button(mail_cubugu, text='Mail ayarları')
    mail_ayar_dugme.pack(side='left', padx=6)
    mail_durum = ttk.Label(mail_cubugu, text='')
    mail_durum.pack(side='left', padx=(10, 0))
    secili = {'start': a.start, 'end': a.end,
              'output': a.output if a.output is not None else aralik_klasoru(a.start, a.end)}

    def onceki_taramalar():
        ciftler = []
        if a.output is None and TARAMALAR_KLASORU.is_dir():
            for k in sorted(TARAMALAR_KLASORU.glob('ARALIK_*')):
                try:
                    s, e = (sayi_oku(x) for x in k.name[len('ARALIK_'):].split('_'))
                    ciftler.append((s, e))
                except ValueError:
                    pass
        return sorted(ciftler)

    def onceki_listesini_yenile():
        onceki_kutu['values'] = ['%s – %s' % (nokta(s), nokta(e)) for s, e in onceki_taramalar()]

    onceki_kutu.configure(postcommand=onceki_listesini_yenile)

    def onceki_secildi(_):
        s, e = (x.strip() for x in onceki_kutu.get().split('–'))
        bas_var.set(s)
        bit_var.set(e)
        araligi_yukle()

    # --- ilerleme
    ilerleme_kutu = ttk.Frame(kok, padding=(12, 4))
    ilerleme_kutu.pack(fill='x')
    yuzde_etiket = ttk.Label(ilerleme_kutu, text='%0.000', style='Yuzde.TLabel')
    yuzde_etiket.pack(anchor='w')
    cubuk = ttk.Progressbar(ilerleme_kutu, maximum=100, mode='determinate')
    cubuk.pack(fill='x', pady=(2, 8))

    # --- bilgi ve sayaclar
    orta = ttk.Frame(kok, padding=(12, 0))
    orta.pack(fill='x')
    bilgi = ttk.LabelFrame(orta, text='Durum', padding=8)
    bilgi.pack(side='left', fill='both', expand=True)
    sayac_cerceve = ttk.LabelFrame(orta, text='Sayaçlar (kaydedilmiş)', padding=8)
    sayac_cerceve.pack(side='left', fill='both', padx=(10, 0))

    bilgi_alanlari = {}
    for satir, (anahtar, baslik) in enumerate((
            ('konum', 'Taranan sınır'), ('kalici', 'Son kalıcı kayıt'), ('motor', 'Hesap motoru'),
            ('isci', 'Aktif işçi'), ('gpu', 'GPU payı'), ('hiz', 'Hız (son 30 sn)'), ('asal_hiz', 'Test edilen asal'),
            ('kalan', 'Kalan süre'), ('tahmini', 'Tahmini bitiş'),
            ('baslama', 'Tarama başlangıcı'), ('oturum', 'Bu oturum başlangıcı'),
            ('bitis', 'Tarama bitişi'), ('oturum_sure', 'Bu oturumda geçen'),
            ('toplam_sure', 'Toplam çalışma süresi'))):
        ttk.Label(bilgi, text=baslik + ':', style='Baslik.TLabel').grid(row=satir, column=0, sticky='w', pady=1)
        etiket = ttk.Label(bilgi, text='-', style='Deger.TLabel')
        etiket.grid(row=satir, column=1, sticky='w', padx=(10, 0), pady=1)
        bilgi_alanlari[anahtar] = etiket

    sayac_alanlari = {}
    sayac_basliklari = ['P%d' % k for k in range(1, SON_TAM + 1)] + ['P%d+' % (SON_TAM + 1), 'Döngü', 'Asal toplamı']
    for i, baslik in enumerate(sayac_basliklari):
        satir, sutun = i % 8, (i // 8) * 2
        ttk.Label(sayac_cerceve, text=baslik + ':', style='Baslik.TLabel').grid(row=satir, column=sutun, sticky='w', padx=(0 if sutun == 0 else 16, 0))
        etiket = ttk.Label(sayac_cerceve, text='0', style='Deger.TLabel')
        etiket.grid(row=satir, column=sutun + 1, sticky='e', padx=(8, 0))
        sayac_alanlari[baslik] = etiket

    # --- gunluk
    alt_cerceve = ttk.LabelFrame(kok, text='P%d ve üzeri zincirler / olaylar' % a.show_min, padding=6)
    alt_cerceve.pack(fill='both', expand=True, padx=12, pady=10)
    kayit_kutusu = ScrolledText(alt_cerceve, font=('Consolas', 10), height=12, state='disabled', wrap='none')
    kayit_kutusu.pack(fill='both', expand=True)
    durum_cubugu = ttk.Label(kok, text='Hazır.', relief='sunken', anchor='w', padding=(8, 2))
    durum_cubugu.pack(fill='x', side='bottom')

    def kayda_ekle(metin):
        kayit_kutusu.configure(state='normal')
        kayit_kutusu.insert('end', metin if metin.endswith('\n') else metin + '\n')
        satir_sayisi = int(kayit_kutusu.index('end-1c').split('.')[0])
        if satir_sayisi > 5000:
            kayit_kutusu.delete('1.0', '%d.0' % (satir_sayisi - 4000))
        kayit_kutusu.see('end')
        kayit_kutusu.configure(state='disabled')

    def yuzde_goster(konum):
        yuzde = 100 * (konum - secili['start']) / (secili['end'] - secili['start'])
        yuzde_etiket.configure(text='%%%.3f' % yuzde)
        cubuk['value'] = yuzde
        bilgi_alanlari['konum'].configure(text=f'{konum:,}')

    def checkpoint_goster(d):
        s = d['sayac_tam_uzunluk']
        for k in range(1, SON_TAM + 1):
            sayac_alanlari['P%d' % k].configure(text=f'{s[k]:,}')
        sayac_alanlari['P%d+' % (SON_TAM + 1)].configure(text=f'{s[SON_TAM + 1]:,}')
        sayac_alanlari['Döngü'].configure(text=f'{d["dongu"]:,}')
        sayac_alanlari['Asal toplamı'].configure(text=f'{d["asal_toplami"]:,}')
        bilgi_alanlari['kalici'].configure(text=f'{d["tamamlanan_sinir"]:,}')
        bilgi_alanlari['baslama'].configure(text=d.get('tarama_baslama_tarihi', '-'))
        bilgi_alanlari['bitis'].configure(text=d.get('tarama_bitis_tarihi', '-'))
        if sure_durum['t0'] is None:
            bilgi_alanlari['toplam_sure'].configure(text=sure_yaz_sn(d.get('toplam_sure_sn', 0)))

    def ilerleme_goster(i):
        yuzde_goster(i['konum'])
        bilgi_alanlari['isci'].configure(text=str(i['isci']))
        bilgi_alanlari['hiz'].configure(text=f'{i["hiz"]:,.0f} sayı/sn')
        bilgi_alanlari['asal_hiz'].configure(text=f'{i["asal_hiz"]:,.0f} asal/sn (zinciri incelenen)')
        bilgi_alanlari['gpu'].configure(text=('%%%.0f (asalların GPU\'da incelenen kısmı)' % i['gpu_payi'])
                                        if 'gpu_payi' in i else 'kullanılmıyor')
        bilgi_alanlari['kalan'].configure(text=sure_yaz(i['kalan']) if i['kalan'] is not None else '-')
        bilgi_alanlari['tahmini'].configure(text=i['tahmini_bitis'] or '-')

    def dugmeler(calisiyor):
        durum['calisiyor'] = calisiyor
        baslat_dugme.configure(state='disabled' if calisiyor else 'normal')
        durdur_dugme.configure(state='normal' if calisiyor else 'disabled')
        gpu_kutu.configure(state='disabled' if calisiyor or a.python else 'normal')
        # Tarama surerken aralik degistirilemez.
        for w in (bas_kutu, bit_kutu, uygula_dugme):
            w.configure(state='disabled' if calisiyor else 'normal')
        onceki_kutu.configure(state='disabled' if calisiyor else 'readonly')
        for w in (mail_kutu, mail_dk_kutu):
            w.configure(state='disabled' if calisiyor else 'normal')

    def gostergeleri_sifirla():
        for etiket in sayac_alanlari.values():
            etiket.configure(text='0')
        for etiket in bilgi_alanlari.values():
            if etiket is not bilgi_alanlari['motor']:
                etiket.configure(text='-')

    def araligi_yukle(*_):
        """Kutulardaki araligi okur, klasorunu secer ve o aralikta kayit varsa gosterir.
        Gecerliyse True doner."""
        if durum['calisiyor']:
            return False
        try:
            s, e = sayi_oku(bas_var.get()), sayi_oku(bit_var.get())
        except ValueError as hata:
            durum_cubugu.configure(text=str(hata))
            baslat_dugme.configure(state='disabled')
            return False
        hata = aralik_hatasi(s, e)
        if hata:
            durum_cubugu.configure(text=hata)
            baslat_dugme.configure(state='disabled')
            return False
        degisti = (s, e) != (secili['start'], secili['end'])
        secili.update(start=s, end=e, output=a.output if a.output is not None else aralik_klasoru(s, e))
        bas_var.set(nokta(s))
        bit_var.set(nokta(e))
        kok.title('PATİ KED Taraması (Clang + GPU) | %s – %s' % (nokta(s), nokta(e)))
        gostergeleri_sifirla()
        yuzde_goster(s)
        motoru_goster()
        baslat_dugme.configure(state='normal')
        d, hata = checkpoint_oku_sessiz(secili['output'], s, e, a.chunk, a.block)
        if hata:
            durum_cubugu.configure(text='Checkpoint sorunu: ' + hata)
            kayda_ekle('Checkpoint sorunu: ' + hata)
        elif d:
            checkpoint_goster(d)
            yuzde_goster(d['tamamlanan_sinir'])
            if d['tamamlanan_sinir'] >= e:
                baslat_dugme.configure(state='disabled')
                durum_cubugu.configure(text='Bu aralık zaten tamamlanmış.')
            else:
                durum_cubugu.configure(text='Kayıt bulundu. Başlat ile kaldığı yerden devam eder.')
        else:
            durum_cubugu.configure(text='Yeni tarama. Başlat ile başlar.')
        if degisti or not _:
            kayda_ekle('Aralık: %s – %s | klasör: %s' % (nokta(s), nokta(e), secili['output']))
        return True

    def baslat():
        try:
            isci = int(isci_var.get())
        except ValueError:
            isci = 0
        if not 1 <= isci <= isci_ust_sinir:
            messagebox.showerror('PATİ', 'Çekirdek sayısı 1 ile %d arasında olmalı.' % isci_ust_sinir)
            return
        if not araligi_yukle('baslat') or baslat_dugme['state'] == 'disabled':
            return
        isci_durum['n'] = isci
        dur.clear()
        dugmeler(True)
        durum_cubugu.configure(text='Başlatılıyor (%d işçi)...' % isci)
        t_bas, t_bit, cikti = secili['start'], secili['end'], secili['output']
        bildirici = lambda tur, veri: olaylar.put((tur, veri))
        if mail_var.get():
            ayar, mail_hatasi = mail_ayarlarini_oku()
            dakika = mail_dakikasi()
            if mail_hatasi or dakika is None:
                dugmeler(False)
                messagebox.showerror('PATİ', mail_hatasi or 'Mail aralığı 1 ile 1440 dakika arasında olmalı.')
                return
            bildirici = MailBildirici(ayar, bildirici, dakika)
            kayda_ekle('Mail raporu: her %g dakikada bir -> %s' % (dakika, ayar['alici']))

        def calis():
            try:
                tara(t_bas, t_bit, a.block, a.chunk, cikti, a.show_min, a.cooldown,
                     lambda: isci_durum['n'], bildirici, dur, a.python,
                     gpu_var.get())
            except Exception as e:
                olaylar.put(('hata', str(e)))
                if isinstance(bildirici, MailBildirici):
                    bildirici.hata(str(e))
            olaylar.put(('cikti', None))

        threading.Thread(target=calis, daemon=True).start()

    def durdur():
        dur.set()
        durdur_dugme.configure(state='disabled')
        durum_cubugu.configure(text='Durduruluyor... (yarım kalan 1 milyarlık bölüm kaydedilmez)')

    def oturum_suresini_dondur():
        if sure_durum['t0'] is not None:
            sure_durum['son'] = time.monotonic() - sure_durum['t0']
        sure_durum['t0'] = None

    def olaylari_isle():
        try:
            while True:
                tur, veri = olaylar.get_nowait()
                if tur == 'basladi':
                    sure_durum.update(t0=time.monotonic(), baz=veri['d'].get('toplam_sure_sn', 0))
                    checkpoint_goster(veri['d'])
                    yuzde_goster(veri['d']['tamamlanan_sinir'])
                    bilgi_alanlari['oturum'].configure(text=veri['oturum_baslama'])
                    bilgi_alanlari['isci'].configure(text=str(veri['isci']))
                    bilgi_alanlari['motor'].configure(text=veri['motor'])
                    durum_cubugu.configure(text='Çalışıyor.')
                    kayda_ekle('%s | Oturum başladı, kaldığı yer %s, %d işçi, motor %s' % (
                        veri['oturum_baslama'], f'{veri["d"]["tamamlanan_sinir"]:,}', veri['isci'], veri['motor']))
                elif tur == 'isci':
                    bilgi_alanlari['isci'].configure(text=str(veri['yeni']))
                    kayda_ekle('%s | İşçi sayısı %d -> %d' % (simdi(), veri['eski'], veri['yeni']))
                elif tur == 'ilerleme':
                    ilerleme_goster(veri)
                elif tur == 'kayit':
                    checkpoint_goster(veri['d'])
                    ilerleme_goster(veri['ilerleme'])
                    durum_cubugu.configure(text='Kaydedildi: %s  (%s)' % (f'{veri["d"]["tamamlanan_sinir"]:,}', simdi()))
                elif tur == 'zincir':
                    kayda_ekle(veri)
                elif tur == 'mail':
                    kayda_ekle('%s | %s' % (simdi(), veri))
                    mail_durum.configure(text=veri[:90])
                elif tur == 'durdu':
                    oturum_suresini_dondur()
                    checkpoint_goster(veri)
                    yuzde_goster(veri['tamamlanan_sinir'])
                    kayda_ekle('%s | Durduruldu. Son kalıcı sınır %s' % (simdi(), f'{veri["tamamlanan_sinir"]:,}'))
                    durum_cubugu.configure(text='Durduruldu. Yeniden başlatınca son kalıcı kayıttan devam eder.')
                elif tur == 'bitti':
                    oturum_suresini_dondur()
                    checkpoint_goster(veri)
                    yuzde_goster(veri['tamamlanan_sinir'])
                    bilgi_alanlari['kalan'].configure(text='-')
                    kayda_ekle('%s | TARAMA TAMAMLANDI' % simdi())
                    durum_cubugu.configure(text='Tarama tamamlandı. Bitiş: %s' % veri.get('tarama_bitis_tarihi', '-'))
                    baslat_dugme.configure(state='disabled')
                elif tur == 'hata':
                    oturum_suresini_dondur()
                    kayda_ekle('HATA: ' + veri)
                    durum_cubugu.configure(text='HATA: ' + veri)
                    messagebox.showerror('PATİ', veri)
                elif tur == 'cikti':
                    son_durum = str(durum_cubugu['text'])
                    dugmeler(False)
                    if durum['kapat']:
                        kok.destroy()
                        return
                    # Dugmeleri ve gostergeleri kayitli duruma gore yenile, son mesaji koru.
                    araligi_yukle('bitti')
                    if sure_durum['son'] is not None:  # son oturumun suresi ekranda kalsin
                        bilgi_alanlari['oturum_sure'].configure(text=sure_yaz_sn(sure_durum['son']))
                    if not son_durum.startswith('HATA'):
                        durum_cubugu.configure(text=son_durum)
        except queue.Empty:
            pass
        if sure_durum['t0'] is not None:
            gecen = time.monotonic() - sure_durum['t0']
            bilgi_alanlari['oturum_sure'].configure(text=sure_yaz_sn(gecen))
            bilgi_alanlari['toplam_sure'].configure(text=sure_yaz_sn(sure_durum['baz'] + gecen))
        kok.after(200, olaylari_isle)

    def kapat():
        if durum['calisiyor']:
            if not messagebox.askyesno('PATİ', 'Tarama çalışıyor. Durdurup kapatılsın mı?\n'
                                                '(Yarım kalan 1 milyarlık bölüm kaydedilmez.)'):
                return
            durum['kapat'] = True
            durdur()
        else:
            kok.destroy()

    def mail_dakikasi():
        try:
            dk = float(mail_dk_var.get().replace(',', '.'))
        except ValueError:
            return None
        return dk if 1 <= dk <= 1440 else None

    def mail_ayarlarini_ac():
        _, hata = mail_ayarlarini_oku()  # yoksa sablonu olusturur
        os.startfile(mail_ayar_yolu())
        if hata:
            mail_durum.configure(text='Ayar dosyasını doldurup kaydedin.')

    def test_maili():
        ayar, hata = mail_ayarlarini_oku()
        if hata:
            messagebox.showerror('PATİ', hata)
            return
        mail_durum.configure(text='Test maili gönderiliyor...')
        govde = ('PATİ KED programından test maili.\n\nGönderen: %s\nAlıcı: %s\nZaman: %s\n'
                 % (ayar['gonderen'], ayar['alici'], simdi()))

        def gonder():
            h = mail_gonder(ayar, 'PATİ KED | test maili', govde)
            olaylar.put(('mail', ('Test maili gönderildi -> %s' % ayar['alici']) if h is None
                         else 'Test maili gönderilemedi: ' + h))

        threading.Thread(target=gonder, daemon=True).start()

    mail_test_dugme.configure(command=test_maili)
    mail_ayar_dugme.configure(command=mail_ayarlarini_ac)
    baslat_dugme.configure(command=baslat)
    durdur_dugme.configure(command=durdur)
    kok.protocol('WM_DELETE_WINDOW', kapat)

    def motoru_goster():
        c_var = not a.python and c_cekirdegi_yukle() is not None
        metin = 'C (%s)' % C_DLL_ADI if c_var else 'Python'
        if c_var and gpu_var.get():
            gpu_ok, gpu_adi = gpu_hazirla()
            metin = 'C + GPU (%s)' % gpu_adi if gpu_ok else 'C (GPU kullanılamadı)'
            if not gpu_ok and not durum.get('gpu_uyarildi'):
                durum['gpu_uyarildi'] = True
                kayda_ekle('GPU kullanılamadı, yalnız CPU ile çalışılacak: ' + gpu_adi[:500])
        bilgi_alanlari['motor'].configure(text=metin)
        return c_var

    for kutu in (bas_kutu, bit_kutu):
        kutu.bind('<Return>', araligi_yukle)
    uygula_dugme.configure(command=lambda: araligi_yukle('dugme'))
    onceki_kutu.bind('<<ComboboxSelected>>', onceki_secildi)
    onceki_listesini_yenile()

    if not motoru_goster() and not a.python:
        kayda_ekle('%s yüklenemedi; hesap Python ile yapılacak (daha yavaş). derle.bat ile derleyin.' % C_DLL_ADI)
    araligi_yukle()

    kok.update_idletasks()
    kok.minsize(max(820, kok.winfo_reqwidth()), 600)
    olaylari_isle()
    kok.mainloop()


def main():
    p=argparse.ArgumentParser(description='PATİ çok çekirdekli 5–10 trilyon güvenli P6+ kayıt (pencereli)')
    p.add_argument('--start',type=int,default=BASLANGIC)
    p.add_argument('--end',type=int,default=BITIS)
    p.add_argument('--block',type=int,default=ELEK_BLOGU)
    p.add_argument('--chunk',type=int,default=KAYIT_ADIMI)
    p.add_argument('--output',type=Path,default=None,
                   help='Sonuç klasörü; verilmezse PATI_TARAMALAR\\ARALIK_<baslangic>_<bitis>')
    p.add_argument('--show-min',type=int,default=6,help='Ekrana basılan minimum uzunluk, varsayilan P6')
    p.add_argument('--cooldown',type=float,default=0,help='Her kayıt adımından sonra dinlenme süresi saniye')
    p.add_argument('--workers',type=int,default=ISCI_SAYISI,help='Paralel işçi (çekirdek) sayısı, varsayılan 16')
    p.add_argument('--konsol',action='store_true',help='Pencere açmadan konsolda çalış')
    p.add_argument('--mail',action='store_true',help='Konsolda sayaçları MAIL_AYARLARI.txt ile periyodik maille gönder')
    p.add_argument('--python',action='store_true',help='C çekirdeği (ked_cekirdek.dll) olsa bile Python ile hesapla')
    p.add_argument('--gpusuz',action='store_true',help='Ekran kartını (GPU) kullanma, yalnız CPU')
    a=p.parse_args()
    if (aralik_hatasi(a.start, a.end) or a.block<=0 or a.chunk<=0 or a.chunk%a.block or a.cooldown<0 or
            a.show_min<1 or a.workers<1):
        p.error(aralik_hatasi(a.start, a.end) or 'Geçersiz parametreler')
    if a.konsol:
        if a.output is None:
            a.output = aralik_klasoru(a.start, a.end)
        konsol_calistir(a)
    else:
        pencere_calistir(a)


if __name__=='__main__':
    main()
