/* PATI KED taramasi icin C hesap cekirdegi.
 * PATI_5_10_TRILYON_HIZLI_UI.py bu DLL'i ctypes ile cagirir; arayuz, dosyalar ve checkpoint Python'dadir.
 * Elek, KED ve asallik testi Python surumuyle BIREBIR ayni sonucu verir:
 *   - elek: ayni tek sayi elegi (alt|1'den baslar, p*p'den once silmez)
 *   - asallik: n < 2^64 icin ayni 7 tabanli kesin Miller-Rabin (Montgomery carpimiyla)
 *   - KED degeri 64 biti asarsa zincir Python'a birakilir (durum 3); orada orijinal test ve sayac kullanilir.
 * Derleme: derle.bat
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <intrin.h>

#define DISA __declspec(dllexport)
#define MAKS_ZINCIR 64
#define SON_TAM 20 /* P1..P20 tam uzunluk; daha uzunlari P21+ (Python SON_TAM ile ayni) */

enum { BILESIK = 0, SABIT = 1, DONGU = 2, PYTHONA = 3 };

static uint64_t KED5[100000];
static const uint32_t KUCUK[] = {3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73,
                                 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157,
                                 163, 167, 173, 179, 181, 191, 193, 197, 199};
#define KUCUK_ADET ((int)(sizeof(KUCUK) / sizeof(KUCUK[0])))
static uint64_t KUCUK_TERS[KUCUK_ADET];  /* p^-1 mod 2^64 */
static uint64_t KUCUK_SINIR[KUCUK_ADET]; /* (2^64-1)/p: n*ters <= sinir ise p | n */
static const uint64_t MR_TABAN[] = {2, 325, 9375, 28178, 450775, 9780504, 1795265022};

static uint64_t tek_ters(uint64_t n) /* n tek; n^-1 mod 2^64 (Newton) */
{
    uint64_t x = n;
    for (int i = 0; i < 5; i++)
        x *= 2 - n * x;
    return x;
}

DISA int ked_hazirla(void)
{
    for (uint32_t k = 0; k < 100000; k++) {
        uint64_t s = 0, b = 1;
        for (uint32_t n = k; n; n /= 10, b *= 10)
            s += (uint64_t)(n % 10) * (n % 10) * b;
        KED5[k] = s;
    }
    for (int i = 0; i < KUCUK_ADET; i++) {
        KUCUK_TERS[i] = tek_ters(KUCUK[i]);
        KUCUK_SINIR[i] = UINT64_MAX / KUCUK[i];
    }
    return 1;
}

/* 0: sonuc 64 bite sigmiyor */
static int ked64(uint64_t n, uint64_t *sonuc)
{
    uint64_t s = 0, c = 1;
    while (n) {
        uint64_t parca = n % 100000, ust;
        n /= 100000;
        uint64_t t = _umul128(KED5[parca], c, &ust);
        if (ust)
            return 0;
        uint64_t s2 = s + t;
        if (s2 < s)
            return 0;
        s = s2;
        if (n)
            c *= 100000;
    }
    *sonuc = s;
    return 1;
}

static inline uint64_t redc(uint64_t ust, uint64_t alt, uint64_t n, uint64_t nters)
{
    uint64_t m = alt * nters, mu;
    _umul128(m, n, &mu); /* m*n'nin alt yarisi == alt */
    return ust >= mu ? ust - mu : ust - mu + n;
}

static inline uint64_t mmul(uint64_t a, uint64_t b, uint64_t n, uint64_t nters)
{
    uint64_t u, a0 = _umul128(a, b, &u);
    return redc(u, a0, n, nters);
}

static inline uint64_t mont(uint64_t a, uint64_t n) /* a*2^64 mod n, a < n */
{
    uint64_t kalan;
    _udiv128(a, 0, n, &kalan);
    return kalan;
}

static int asal64(uint64_t n)
{
    if (n < 2)
        return 0;
    if (!(n & 1))
        return n == 2;
    for (int i = 0; i < KUCUK_ADET; i++) {
        if (n == KUCUK[i])
            return 1;
        if (n * KUCUK_TERS[i] <= KUCUK_SINIR[i])
            return 0;
    }
    if (n < 199u * 199u)
        return 1;
    uint64_t nters = tek_ters(n);
    uint64_t bir = mont(1, n), eksi_bir = n - bir;
    uint64_t m = n - 1;
    unsigned long s;
    _BitScanForward64(&s, m);
    uint64_t d = m >> s;
    for (int t = 0; t < (int)(sizeof(MR_TABAN) / sizeof(MR_TABAN[0])); t++) {
        uint64_t a = MR_TABAN[t] % n;
        if (a == 0)
            continue;
        uint64_t taban = mont(a, n), x = bir;
        for (uint64_t e = d; e; e >>= 1) {
            if (e & 1)
                x = mmul(x, taban, n, nters);
            taban = mmul(taban, taban, n, nters);
        }
        if (x == bir || x == eksi_bir)
            continue;
        unsigned long r;
        for (r = 1; r < s; r++) {
            x = mmul(x, x, n, nters);
            if (x == eksi_bir)
                break;
        }
        if (r >= s)
            return 0;
    }
    return 1;
}

/* Python zinciri_incele ile ayni: donus uzunluk, *durum BILESIK/SABIT/DONGU/PYTHONA */
static int zincir(uint64_t p1, uint64_t *z, int *durum)
{
    int uz = 1;
    uint64_t n;
    z[0] = p1;
    if (!ked64(p1, &n)) {
        *durum = PYTHONA;
        return 0;
    }
    for (;;) {
        for (int i = 0; i < uz; i++) {
            if (z[i] == n) {
                if (n == p1 && uz == 1) {
                    *durum = SABIT;
                    return 1;
                }
                *durum = DONGU;
                return uz;
            }
        }
        if (!asal64(n)) {
            *durum = BILESIK;
            return uz;
        }
        if (uz == MAKS_ZINCIR) {
            *durum = PYTHONA;
            return 0;
        }
        z[uz++] = n;
        if (!ked64(n, &n)) {
            *durum = PYTHONA;
            return 0;
        }
    }
}

/* [alt, ust) araligini 'blok' boyutlu elek bloklariyla tarar (Python surumundeki bloklarla ayni).
 * sayac[1..SON_TAM]: tam uzunluk, sayac[SON_TAM+1]: P21+ (indeks 0 kullanilmaz);
 * sayac[SON_TAM+2]: asal toplami; sayac[SON_TAM+3]: dongu.
 * cikti: P6+, dongu ve Python'a birakilan her asal icin sirayla [p1, durum, uzunluk, zincir...].
 * Donus: 0 tamam, -1 cikti kapasitesi yetmedi (daha buyuk tamponla yeniden cagrilir), -2 bellek yok. */
DISA int ked_aralik(uint64_t alt, uint64_t ust, uint64_t blok, const uint32_t *taban, int64_t taban_adet,
                    uint64_t *sayac, uint64_t *cikti, int64_t kapasite, int64_t *cikti_uz)
{
    uint8_t *elek = (uint8_t *)malloc((size_t)(blok / 2 + 2));
    uint64_t z[MAKS_ZINCIR];
    int64_t yer = 0;
    if (!elek)
        return -2;
    memset(sayac, 0, (SON_TAM + 4) * sizeof(uint64_t));
    for (uint64_t sa = alt; sa < ust; sa += blok) {
        uint64_t su = sa + blok < ust ? sa + blok : ust;
        uint64_t ilk = sa | 1;
        if (su <= ilk)
            continue;
        uint64_t adet = (su - ilk + 1) / 2;
        memset(elek, 1, (size_t)adet);
        for (int64_t j = 0; j < taban_adet; j++) {
            uint64_t p = taban[j], pp = p * p;
            if (pp >= su)
                break;
            uint64_t ilk_kat = (ilk + p - 1) / p * p;
            if (ilk_kat < pp)
                ilk_kat = pp;
            if (!(ilk_kat & 1))
                ilk_kat += p;
            if (ilk_kat >= su)
                continue;
            for (uint64_t k = (ilk_kat - ilk) / 2; k < adet; k += p)
                elek[k] = 0;
        }
        for (uint64_t i = 0; i < adet; i++) {
            if (!elek[i])
                continue;
            uint64_t p1 = ilk + 2 * i;
            int durum, uz = zincir(p1, z, &durum);
            if (durum == PYTHONA) {
                if (yer + 3 > kapasite) {
                    free(elek);
                    return -1;
                }
                cikti[yer++] = p1;
                cikti[yer++] = PYTHONA;
                cikti[yer++] = 0;
                continue;
            }
            sayac[SON_TAM + 2]++;
            if (durum == DONGU)
                sayac[SON_TAM + 3]++;
            else
                sayac[uz <= SON_TAM ? uz : SON_TAM + 1]++;
            if (uz >= 6 || durum == DONGU) {
                if (yer + 3 + uz > kapasite) {
                    free(elek);
                    return -1;
                }
                cikti[yer++] = p1;
                cikti[yer++] = (uint64_t)durum;
                cikti[yer++] = (uint64_t)uz;
                for (int k = 0; k < uz; k++)
                    cikti[yer++] = z[k];
            }
        }
    }
    free(elek);
    *cikti_uz = yer;
    return 0;
}

/* Test icin: Python asal_64 ile karsilastirma */
DISA int ked_asal64(uint64_t n) { return asal64(n); }
DISA int ked_ked64(uint64_t n, uint64_t *s) { return ked64(n, s); }
