/* PATI KED taramasi icin C hesap cekirdegi.
 * PATI_5_10_TRILYON_HIZLI_UI.py bu DLL'i ctypes ile cagirir; arayuz, dosyalar ve checkpoint Python'dadir.
 * Elek, KED ve asallik testi Python surumuyle BIREBIR ayni sonucu verir:
 *   - elek: ayni tek sayi elegi (alt|1'den baslar, p*p'den once silmez)
 *   - asallik: n < 2^64 icin ayni 7 tabanli kesin Miller-Rabin (Montgomery carpimiyla)
 *   - KED degeri 64 biti asarsa zincir Python'a birakilir (durum 3); orada orijinal test ve sayac kullanilir.
 * Istege bagli GPU: ked_gpu_hazirla() basarili olursa ked_aralik_gpu() zincirleri ekran kartinda
 * (OpenCL, ked_gpu.cl) hesaplar; GPU mesgulse ya da hata verirse ayni gorevi CPU'da yapar.
 * Derleme: derle.bat
 */
#include <windows.h>
#include <stdio.h>
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

/* ======================================================================= GPU (OpenCL, istege bagli)
 * OpenCL.dll calisma aninda yuklenir (CUDA Toolkit / OpenCL SDK gerekmez). GPU tek ortak kaynaktir:
 * bir gorev GPU'yu bos bulursa kullanir, mesgulse zincirleri kendisi CPU'da hesaplar. Boylece is
 * CPU ile GPU arasinda kendiliginden bolunur. */

typedef int32_t cl_int;
typedef uint32_t cl_uint;
typedef uint64_t cl_ulong;
typedef void *cl_platform_id, *cl_device_id, *cl_context, *cl_command_queue, *cl_program, *cl_kernel, *cl_mem;
#define CL_DEVICE_TYPE_GPU (1u << 2)
#define CL_DEVICE_NAME 0x102B
#define CL_MEM_READ_WRITE (1u << 0)
#define CL_MEM_READ_ONLY (1u << 2)
#define CL_MEM_COPY_HOST_PTR (1u << 5)
#define CL_PROGRAM_BUILD_LOG 0x1183

#define CL_FN(ret, ad, args) typedef ret(__stdcall *ad##_t) args; static ad##_t ad;
CL_FN(cl_int, clGetPlatformIDs, (cl_uint, cl_platform_id *, cl_uint *))
CL_FN(cl_int, clGetDeviceIDs, (cl_platform_id, cl_ulong, cl_uint, cl_device_id *, cl_uint *))
CL_FN(cl_int, clGetDeviceInfo, (cl_device_id, cl_uint, size_t, void *, size_t *))
CL_FN(cl_context, clCreateContext, (const intptr_t *, cl_uint, const cl_device_id *, void *, void *, cl_int *))
CL_FN(cl_command_queue, clCreateCommandQueue, (cl_context, cl_device_id, cl_ulong, cl_int *))
CL_FN(cl_program, clCreateProgramWithSource, (cl_context, cl_uint, const char **, const size_t *, cl_int *))
CL_FN(cl_int, clBuildProgram, (cl_program, cl_uint, const cl_device_id *, const char *, void *, void *))
CL_FN(cl_int, clGetProgramBuildInfo, (cl_program, cl_device_id, cl_uint, size_t, void *, size_t *))
CL_FN(cl_kernel, clCreateKernel, (cl_program, const char *, cl_int *))
CL_FN(cl_mem, clCreateBuffer, (cl_context, cl_ulong, size_t, void *, cl_int *))
CL_FN(cl_int, clReleaseMemObject, (cl_mem))
CL_FN(cl_int, clSetKernelArg, (cl_kernel, cl_uint, size_t, const void *))
CL_FN(cl_int, clEnqueueNDRangeKernel, (cl_command_queue, cl_kernel, cl_uint, const size_t *, const size_t *, const size_t *, cl_uint, const void *, void *))
CL_FN(cl_int, clEnqueueReadBuffer, (cl_command_queue, cl_mem, cl_uint, size_t, size_t, void *, cl_uint, const void *, void *))
CL_FN(cl_int, clEnqueueWriteBuffer, (cl_command_queue, cl_mem, cl_uint, size_t, size_t, const void *, cl_uint, const void *, void *))

static volatile LONG gpu_hazir = 0;
/* GPU yuvalari: her biri kendi kuyrugu, cekirdek nesnesi ve tamponlariyla; birkac gorev GPU'yu
 * ayni anda besleyebilir (biri veri aktarirken digeri hesaplar). */
#define GPU_YUVA 4
static CRITICAL_SECTION gpu_kilit[GPU_YUVA];
static cl_context g_bag;
static cl_command_queue g_kuyruk[GPU_YUVA];
static cl_kernel g_cek[GPU_YUVA];
static cl_mem g_ked5, g_ters, g_sinir, g_asal[GPU_YUVA], g_son[GPU_YUVA];
static size_t g_kapasite[GPU_YUVA];
static volatile LONG64 g_gpu_asal = 0, g_cpu_asal = 0;
static volatile LONG g_yuva_sinir = GPU_YUVA; /* sicaklik denetimi icin; 0 = GPU kullanilmaz */

static int opencl_yukle(void)
{
    HMODULE m = LoadLibraryA("OpenCL.dll");
    if (!m)
        return 0;
#define YUKLE(ad) if (!(ad = (ad##_t)GetProcAddress(m, #ad))) return 0;
    YUKLE(clGetPlatformIDs) YUKLE(clGetDeviceIDs) YUKLE(clGetDeviceInfo) YUKLE(clCreateContext)
    YUKLE(clCreateCommandQueue) YUKLE(clCreateProgramWithSource) YUKLE(clBuildProgram)
    YUKLE(clGetProgramBuildInfo) YUKLE(clCreateKernel) YUKLE(clCreateBuffer) YUKLE(clReleaseMemObject)
    YUKLE(clSetKernelArg) YUKLE(clEnqueueNDRangeKernel) YUKLE(clEnqueueReadBuffer) YUKLE(clEnqueueWriteBuffer)
#undef YUKLE
    return 1;
}

/* GPU'yu hazirlar. kaynak: ked_gpu.cl metni. ad: kart adi ya da hata metni yazilir.
 * Donus 1 = GPU kullanilabilir, 0 = kullanilamaz (program CPU ile devam eder). ked_hazirla()'dan sonra cagrilir. */
DISA int ked_gpu_hazirla(const char *kaynak, char *ad, int ad_boyu)
{
    cl_platform_id platformlar[8];
    cl_uint np = 0;
    cl_device_id cihaz = NULL;
    cl_program prog;
    cl_int h = 0;
    ad[0] = 0;
    if (gpu_hazir)
        return 1;
    if (!opencl_yukle()) {
        strncpy_s(ad, ad_boyu, "OpenCL.dll yuklenemedi", _TRUNCATE);
        return 0;
    }
    if (clGetPlatformIDs(8, platformlar, &np) != 0 || !np) {
        strncpy_s(ad, ad_boyu, "OpenCL platformu yok", _TRUNCATE);
        return 0;
    }
    /* Once NVIDIA/AMD gibi ayri karti, yoksa ilk GPU'yu sec. */
    for (int tur = 0; tur < 2 && !cihaz; tur++) {
        for (cl_uint i = 0; i < np && !cihaz; i++) {
            cl_device_id c;
            cl_uint nd = 0;
            char isim[256] = {0};
            if (clGetDeviceIDs(platformlar[i], CL_DEVICE_TYPE_GPU, 1, &c, &nd) != 0 || !nd)
                continue;
            clGetDeviceInfo(c, CL_DEVICE_NAME, sizeof(isim), isim, NULL);
            if (tur == 1 || strstr(isim, "NVIDIA") || strstr(isim, "AMD") || strstr(isim, "Radeon")) {
                cihaz = c;
                strncpy_s(ad, ad_boyu, isim, _TRUNCATE);
            }
        }
    }
    if (!cihaz) {
        strncpy_s(ad, ad_boyu, "GPU bulunamadi", _TRUNCATE);
        return 0;
    }
    g_bag = clCreateContext(NULL, 1, &cihaz, NULL, NULL, &h);
    if (h)
        goto hata;
    prog = clCreateProgramWithSource(g_bag, 1, &kaynak, NULL, &h);
    if (h)
        goto hata;
    if (clBuildProgram(prog, 1, &cihaz, "", NULL, NULL) != 0) {
        strncpy_s(ad, ad_boyu, "GPU programi derlenemedi: ", _TRUNCATE);
        size_t u = strlen(ad);
        clGetProgramBuildInfo(prog, cihaz, CL_PROGRAM_BUILD_LOG, (size_t)ad_boyu - u - 1, ad + u, NULL);
        return 0;
    }
    for (int y = 0; y < GPU_YUVA; y++) {
        g_kuyruk[y] = clCreateCommandQueue(g_bag, cihaz, 0, &h);
        if (h)
            goto hata;
        g_cek[y] = clCreateKernel(prog, "tam_zincir", &h);
        if (h)
            goto hata;
    }
    g_ked5 = clCreateBuffer(g_bag, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(KED5), KED5, &h);
    if (h)
        goto hata;
    g_ters = clCreateBuffer(g_bag, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(KUCUK_TERS), KUCUK_TERS, &h);
    if (h)
        goto hata;
    g_sinir = clCreateBuffer(g_bag, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(KUCUK_SINIR), KUCUK_SINIR, &h);
    if (h)
        goto hata;
    for (int y = 0; y < GPU_YUVA; y++)
        InitializeCriticalSection(&gpu_kilit[y]);
    InterlockedExchange(&gpu_hazir, 1);
    return 1;
hata:
    _snprintf_s(ad, ad_boyu, _TRUNCATE, "OpenCL hatasi %d", h);
    return 0;
}

/* Su ana kadar GPU'da ve CPU'da zinciri incelenen asal sayisi (GPU payini gostermek icin). */
DISA void ked_gpu_istatistik(uint64_t *gpu, uint64_t *cpu)
{
    *gpu = (uint64_t)g_gpu_asal;
    *cpu = (uint64_t)g_cpu_asal;
}

/* Ayni anda kullanilacak GPU yuvasi sayisi (0..GPU_YUVA); calisirken degistirilebilir, sonuclari etkilemez. */
DISA void ked_gpu_yuva_ayarla(int n)
{
    InterlockedExchange(&g_yuva_sinir, n < 0 ? 0 : n > GPU_YUVA ? GPU_YUVA : n);
}

/* Kilit tutulurken cagrilir. 0 = basarili. */
static int gpu_zincirle(int y, const uint64_t *asallar, int64_t adet, uint16_t *kod)
{
    cl_int h = 0;
    if ((size_t)adet > g_kapasite[y]) {
        if (g_asal[y])
            clReleaseMemObject(g_asal[y]);
        if (g_son[y])
            clReleaseMemObject(g_son[y]);
        g_asal[y] = g_son[y] = NULL;
        g_kapasite[y] = 0;
        size_t kap = (size_t)adet + (size_t)adet / 4;
        g_asal[y] = clCreateBuffer(g_bag, CL_MEM_READ_ONLY, sizeof(uint64_t) * kap, NULL, &h);
        if (h)
            return h;
        g_son[y] = clCreateBuffer(g_bag, CL_MEM_READ_WRITE, sizeof(uint16_t) * kap, NULL, &h);
        if (h)
            return h;
        g_kapasite[y] = kap;
    }
    if ((h = clEnqueueWriteBuffer(g_kuyruk[y], g_asal[y], 1, 0, sizeof(uint64_t) * adet, asallar, 0, NULL, NULL)))
        return h;
    cl_ulong n = (cl_ulong)adet;
    clSetKernelArg(g_cek[y], 0, sizeof(cl_mem), &g_asal[y]);
    clSetKernelArg(g_cek[y], 1, sizeof(cl_mem), &g_son[y]);
    clSetKernelArg(g_cek[y], 2, sizeof(cl_ulong), &n);
    clSetKernelArg(g_cek[y], 3, sizeof(cl_mem), &g_ked5);
    clSetKernelArg(g_cek[y], 4, sizeof(cl_mem), &g_ters);
    clSetKernelArg(g_cek[y], 5, sizeof(cl_mem), &g_sinir);
    size_t yerel = 256, genel = ((size_t)adet + yerel - 1) / yerel * yerel;
    if ((h = clEnqueueNDRangeKernel(g_kuyruk[y], g_cek[y], 1, NULL, &genel, &yerel, 0, NULL, NULL)))
        return h;
    return clEnqueueReadBuffer(g_kuyruk[y], g_son[y], 1, 0, sizeof(uint16_t) * adet, kod, 0, NULL, NULL);
}

/* ked_aralik ile ayni girdi/cikti ve ayni sonuc; zincirler GPU bossa GPU'da hesaplanir.
 * Ek donus: -3 = GPU ile CPU bir zincirde uyusmadi (olmamali; olursa tarama durur). */
DISA int ked_aralik_gpu(uint64_t alt, uint64_t ust, uint64_t blok, const uint32_t *taban, int64_t taban_adet,
                        uint64_t *sayac, uint64_t *cikti, int64_t kapasite, int64_t *cikti_uz)
{
    /* 1) Tum bloklari ayni elekle ele, asallari sirayla topla. */
    uint8_t *elek = (uint8_t *)malloc((size_t)(blok / 2 + 2));
    int64_t asal_kap = (int64_t)((ust - alt) / 8 + 1024), adet = 0, yer = 0;
    uint64_t *asallar = (uint64_t *)malloc(sizeof(uint64_t) * (size_t)asal_kap);
    uint16_t *kod = NULL;
    uint64_t z[MAKS_ZINCIR];
    int sonuc = 0;
    if (!elek || !asallar) {
        sonuc = -2;
        goto bitir;
    }
    for (uint64_t sa = alt; sa < ust; sa += blok) {
        uint64_t su = sa + blok < ust ? sa + blok : ust;
        uint64_t ilk = sa | 1;
        if (su <= ilk)
            continue;
        uint64_t adet_b = (su - ilk + 1) / 2;
        memset(elek, 1, (size_t)adet_b);
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
            for (uint64_t k = (ilk_kat - ilk) / 2; k < adet_b; k += p)
                elek[k] = 0;
        }
        for (uint64_t i = 0; i < adet_b; i++) {
            if (!elek[i])
                continue;
            if (adet == asal_kap) {
                uint64_t *yeni = (uint64_t *)realloc(asallar, sizeof(uint64_t) * (size_t)(asal_kap *= 2));
                if (!yeni) {
                    sonuc = -2;
                    goto bitir;
                }
                asallar = yeni;
            }
            asallar[adet++] = ilk + 2 * i;
        }
    }

    /* 2) GPU bossa zincirleri orada hesapla. */
    int yuva_sinir = (int)g_yuva_sinir;
    for (int y = 0; gpu_hazir && adet && y < yuva_sinir; y++) {
        if (!TryEnterCriticalSection(&gpu_kilit[y]))
            continue;
        kod = (uint16_t *)malloc(sizeof(uint16_t) * (size_t)adet);
        if (kod && (!gpu_hazir || gpu_zincirle(y, asallar, adet, kod) != 0)) {
            InterlockedExchange(&gpu_hazir, 0); /* GPU hatasi: bundan sonra yalniz CPU */
            free(kod);
            kod = NULL;
        }
        LeaveCriticalSection(&gpu_kilit[y]);
        break;
    }
    if (kod)
        InterlockedAdd64(&g_gpu_asal, adet);
    else
        InterlockedAdd64(&g_cpu_asal, adet);

    /* 3) Sayac ve kayitlar (ked_aralik ile ayni bicim ve sira). */
    memset(sayac, 0, (SON_TAM + 4) * sizeof(uint64_t));
    for (int64_t i = 0; i < adet; i++) {
        uint64_t p1 = asallar[i];
        int durum, uz;
        if (kod) {
            uz = kod[i] & 0xff;
            durum = kod[i] >> 8;
            if (durum != PYTHONA && (uz >= 6 || durum == DONGU)) {
                /* Kaydedilecek zincirin terimleri CPU'da hesaplanir ve GPU sonucuyla karsilastirilir. */
                int d2, u2 = zincir(p1, z, &d2);
                if (u2 != uz || d2 != durum) {
                    sonuc = -3;
                    goto bitir;
                }
            }
        } else
            uz = zincir(p1, z, &durum);
        if (durum == PYTHONA) {
            if (yer + 3 > kapasite) {
                sonuc = -1;
                goto bitir;
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
                sonuc = -1;
                goto bitir;
            }
            cikti[yer++] = p1;
            cikti[yer++] = (uint64_t)durum;
            cikti[yer++] = (uint64_t)uz;
            for (int k = 0; k < uz; k++)
                cikti[yer++] = z[k];
        }
    }
    *cikti_uz = yer;
bitir:
    free(elek);
    free(asallar);
    free(kod);
    return sonuc;
}
