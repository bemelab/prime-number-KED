/* PATI KED GPU denemesi (ana programdan bagimsiz).
 * Bir araliktaki asallari CPU'da eler, her asal icin zincirin ilk adimini (KED + asallik testi)
 *   (a) CPU'da 24 is parcacigiyla (referans_cekirdek.c, ana programin C cekirdeginin kopyasi),
 *   (b) GPU'da OpenCL ile
 * hesaplar; sonuclari birebir karsilastirir ve surelerini yazar.
 * OpenCL.dll calisma aninda yuklenir: CUDA Toolkit veya OpenCL SDK gerekmez.
 * Kullanim: gpu_deneme.exe [baslangic] [uzunluk]   (varsayilan 7000000000000 2000000000)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <windows.h>
#include <omp.h>
#include "referans_cekirdek.c"

/* ---- OpenCL: yalnizca gereken tanimlar ---- */
typedef int32_t cl_int;
typedef uint32_t cl_uint;
typedef uint64_t cl_ulong;
typedef void *cl_platform_id, *cl_device_id, *cl_context, *cl_command_queue, *cl_program, *cl_kernel, *cl_mem;
#define CL_DEVICE_TYPE_GPU (1u << 2)
#define CL_PLATFORM_NAME 0x0902
#define CL_DEVICE_NAME 0x102B
#define CL_DEVICE_MAX_COMPUTE_UNITS 0x1002
#define CL_MEM_READ_WRITE (1u << 0)
#define CL_MEM_READ_ONLY (1u << 2)
#define CL_MEM_COPY_HOST_PTR (1u << 5)
#define CL_PROGRAM_BUILD_LOG 0x1183

#define CL_FN(ret, ad, args) typedef ret(__stdcall *ad##_t) args; static ad##_t ad;
CL_FN(cl_int, clGetPlatformIDs, (cl_uint, cl_platform_id *, cl_uint *))
CL_FN(cl_int, clGetPlatformInfo, (cl_platform_id, cl_uint, size_t, void *, size_t *))
CL_FN(cl_int, clGetDeviceIDs, (cl_platform_id, cl_ulong, cl_uint, cl_device_id *, cl_uint *))
CL_FN(cl_int, clGetDeviceInfo, (cl_device_id, cl_uint, size_t, void *, size_t *))
CL_FN(cl_context, clCreateContext, (const intptr_t *, cl_uint, const cl_device_id *, void *, void *, cl_int *))
CL_FN(cl_command_queue, clCreateCommandQueue, (cl_context, cl_device_id, cl_ulong, cl_int *))
CL_FN(cl_program, clCreateProgramWithSource, (cl_context, cl_uint, const char **, const size_t *, cl_int *))
CL_FN(cl_int, clBuildProgram, (cl_program, cl_uint, const cl_device_id *, const char *, void *, void *))
CL_FN(cl_int, clGetProgramBuildInfo, (cl_program, cl_device_id, cl_uint, size_t, void *, size_t *))
CL_FN(cl_kernel, clCreateKernel, (cl_program, const char *, cl_int *))
CL_FN(cl_mem, clCreateBuffer, (cl_context, cl_ulong, size_t, void *, cl_int *))
CL_FN(cl_int, clSetKernelArg, (cl_kernel, cl_uint, size_t, const void *))
CL_FN(cl_int, clEnqueueNDRangeKernel, (cl_command_queue, cl_kernel, cl_uint, const size_t *, const size_t *, const size_t *, cl_uint, const void *, void *))
CL_FN(cl_int, clEnqueueReadBuffer, (cl_command_queue, cl_mem, cl_uint, size_t, size_t, void *, cl_uint, const void *, void *))
CL_FN(cl_int, clEnqueueWriteBuffer, (cl_command_queue, cl_mem, cl_uint, size_t, size_t, const void *, cl_uint, const void *, void *))
CL_FN(cl_int, clFinish, (cl_command_queue))

static void dur(const char *mesaj, cl_int kod)
{
    fprintf(stderr, "HATA: %s (kod %d)\n", mesaj, kod);
    exit(1);
}
#define KONTROL(ifade, mesaj) do { cl_int _k = (ifade); if (_k != 0) dur(mesaj, _k); } while (0)

static int opencl_yukle(void)
{
    HMODULE m = LoadLibraryA("OpenCL.dll");
    if (!m)
        return 0;
#define YUKLE(ad) if (!(ad = (ad##_t)GetProcAddress(m, #ad))) return 0;
    YUKLE(clGetPlatformIDs) YUKLE(clGetPlatformInfo) YUKLE(clGetDeviceIDs) YUKLE(clGetDeviceInfo)
    YUKLE(clCreateContext) YUKLE(clCreateCommandQueue) YUKLE(clCreateProgramWithSource) YUKLE(clBuildProgram)
    YUKLE(clGetProgramBuildInfo) YUKLE(clCreateKernel) YUKLE(clCreateBuffer) YUKLE(clSetKernelArg)
    YUKLE(clEnqueueNDRangeKernel) YUKLE(clEnqueueReadBuffer) YUKLE(clEnqueueWriteBuffer) YUKLE(clFinish)
    return 1;
}

static double saat(void)
{
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t);
    return (double)t.QuadPart / (double)f.QuadPart;
}

static char *dosya_oku(const char *ad)
{
    FILE *f = fopen(ad, "rb");
    if (!f)
        return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *s = (char *)malloc(n + 1);
    fread(s, 1, n, f);
    s[n] = 0;
    fclose(f);
    return s;
}

/* Ana programla ayni tek sayi elegi; bloklar paralel elenir, asallar sirayla birlestirilir. */
static uint64_t *asallari_ele(uint64_t alt, uint64_t ust, uint64_t blok, int64_t *adet_cikti)
{
    uint64_t kok = 1;
    while ((kok + 1) * (kok + 1) <= ust - 1)
        kok++;
    uint8_t *e = (uint8_t *)calloc(kok + 1, 1);
    uint32_t *taban = (uint32_t *)malloc(sizeof(uint32_t) * (kok / 2 + 2));
    int64_t ntaban = 0;
    for (uint64_t i = 2; i <= kok; i++) {
        if (e[i])
            continue;
        if (i > 2)
            taban[ntaban++] = (uint32_t)i;
        for (uint64_t j = i * i; j <= kok; j += i)
            e[j] = 1;
    }
    free(e);
    int64_t nblok = (int64_t)((ust - alt + blok - 1) / blok);
    uint64_t **parca = (uint64_t **)calloc(nblok, sizeof(uint64_t *));
    int64_t *padet = (int64_t *)calloc(nblok, sizeof(int64_t));
#pragma omp parallel
    {
        uint8_t *elek = (uint8_t *)malloc(blok / 2 + 2);
#pragma omp for schedule(dynamic, 4)
        for (int64_t b = 0; b < nblok; b++) {
            uint64_t sa = alt + (uint64_t)b * blok, su = sa + blok < ust ? sa + blok : ust;
            uint64_t ilk = sa | 1;
            if (su <= ilk)
                continue;
            uint64_t adet = (su - ilk + 1) / 2;
            memset(elek, 1, adet);
            for (int64_t j = 0; j < ntaban; j++) {
                uint64_t p = taban[j], pp = p * p;
                if (pp >= su)
                    break;
                uint64_t k0 = (ilk + p - 1) / p * p;
                if (k0 < pp)
                    k0 = pp;
                if (!(k0 & 1))
                    k0 += p;
                if (k0 >= su)
                    continue;
                for (uint64_t k = (k0 - ilk) / 2; k < adet; k += p)
                    elek[k] = 0;
            }
            int64_t say = 0;
            for (uint64_t i = 0; i < adet; i++)
                say += elek[i];
            parca[b] = (uint64_t *)malloc(sizeof(uint64_t) * (say ? say : 1));
            say = 0;
            for (uint64_t i = 0; i < adet; i++)
                if (elek[i])
                    parca[b][say++] = ilk + 2 * i;
            padet[b] = say;
        }
        free(elek);
    }
    int64_t toplam = 0;
    for (int64_t b = 0; b < nblok; b++)
        toplam += padet[b];
    uint64_t *asallar = (uint64_t *)malloc(sizeof(uint64_t) * toplam);
    int64_t yer = 0;
    for (int64_t b = 0; b < nblok; b++) {
        memcpy(asallar + yer, parca[b], sizeof(uint64_t) * padet[b]);
        yer += padet[b];
        free(parca[b]);
    }
    free(parca);
    free(padet);
    free(taban);
    *adet_cikti = toplam;
    return asallar;
}

static uint8_t cpu_ilk_adim(uint64_t p)
{
    uint64_t n;
    if (!ked64(p, &n))
        return 3;
    if (n == p)
        return 2;
    return asal64(n) ? 1 : 0;
}

int main(int argc, char **argv)
{
    uint64_t alt = argc > 1 ? _strtoui64(argv[1], NULL, 10) : 7000000000000ULL;
    uint64_t uzunluk = argc > 2 ? _strtoui64(argv[2], NULL, 10) : 2000000000ULL;
    uint64_t ust = alt + uzunluk;
    int is_parcacigi = omp_get_max_threads();
    ked_hazirla();
    printf("Aralik: %llu - %llu (%llu sayi), CPU is parcacigi: %d\n", alt, ust, uzunluk, is_parcacigi);

    /* --- 1. elek (CPU) --- */
    double t0 = saat();
    int64_t adet;
    uint64_t *asallar = asallari_ele(alt, ust, 2000000, &adet);
    double t_elek = saat() - t0;
    printf("Elek (CPU, %d is): %.3f sn, %lld asal\n", is_parcacigi, t_elek, adet);

    /* --- 2. ilk adim CPU'da --- */
    uint8_t *cpu = (uint8_t *)malloc(adet), *gpu = (uint8_t *)malloc(adet);
    t0 = saat();
#pragma omp parallel for schedule(dynamic, 65536)
    for (int64_t i = 0; i < adet; i++)
        cpu[i] = cpu_ilk_adim(asallar[i]);
    double t_cpu = saat() - t0;
    int64_t sayim[4] = {0};
    for (int64_t i = 0; i < adet; i++)
        sayim[cpu[i]]++;
    printf("Ilk adim (CPU, %d is): %.3f sn | P1-bilesik %lld, devam %lld, sabit %lld, 64bit-tasma %lld\n",
           is_parcacigi, t_cpu, sayim[0], sayim[1], sayim[2], sayim[3]);

    /* --- 3. zincirin geri kalani (yalniz 'devam' olanlar, CPU) --- */
    t0 = saat();
    int64_t uzun = 0;
#pragma omp parallel for schedule(dynamic, 4096) reduction(+ : uzun)
    for (int64_t i = 0; i < adet; i++) {
        if (cpu[i] == 1) {
            uint64_t z[MAKS_ZINCIR];
            int durum;
            uzun += zincir(asallar[i], z, &durum) >= 6;
        }
    }
    double t_kalan = saat() - t0;
    printf("Zincirin kalani (CPU, yalniz %%%.1f'i): %.3f sn, P6+ zincir %lld\n", 100.0 * sayim[1] / adet, t_kalan, uzun);

    /* --- 4. ilk adim GPU'da --- */
    if (!opencl_yukle())
        dur("OpenCL.dll yuklenemedi", -1);
    cl_platform_id platformlar[8];
    cl_uint np = 0;
    KONTROL(clGetPlatformIDs(8, platformlar, &np), "platform yok");
    cl_device_id cihaz = NULL;
    char ad[256];
    for (cl_uint i = 0; i < np && !cihaz; i++) {
        cl_uint nd = 0;
        if (clGetDeviceIDs(platformlar[i], CL_DEVICE_TYPE_GPU, 1, &cihaz, &nd) != 0 || !nd)
            cihaz = NULL;
        else {
            clGetDeviceInfo(cihaz, CL_DEVICE_NAME, sizeof(ad), ad, NULL);
            if (!strstr(ad, "NVIDIA") && i + 1 < np) /* once NVIDIA karti tercih et */
                cihaz = NULL;
        }
    }
    if (!cihaz)
        dur("GPU bulunamadi", -1);
    cl_uint cu;
    clGetDeviceInfo(cihaz, CL_DEVICE_MAX_COMPUTE_UNITS, sizeof(cu), &cu, NULL);
    printf("GPU: %s (%u hesap birimi)\n", ad, cu);
    cl_int h;
    cl_context bag = clCreateContext(NULL, 1, &cihaz, NULL, NULL, &h);
    KONTROL(h, "baglam");
    cl_command_queue kuyruk = clCreateCommandQueue(bag, cihaz, 0, &h);
    KONTROL(h, "kuyruk");
    char *kaynak = dosya_oku("gpu_cekirdek.cl");
    if (!kaynak)
        dur("gpu_cekirdek.cl okunamadi (programi GPU_DENEME klasorunde calistirin)", -1);
    cl_program prog = clCreateProgramWithSource(bag, 1, (const char **)&kaynak, NULL, &h);
    KONTROL(h, "program");
    if (clBuildProgram(prog, 1, &cihaz, "", NULL, NULL) != 0) {
        static char log[65536];
        clGetProgramBuildInfo(prog, cihaz, CL_PROGRAM_BUILD_LOG, sizeof(log), log, NULL);
        fprintf(stderr, "%s\n", log);
        dur("GPU programi derlenemedi", -1);
    }
    cl_kernel cek = clCreateKernel(prog, "ilk_adim", &h);
    KONTROL(h, "cekirdek");
    cl_mem m_ked5 = clCreateBuffer(bag, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(KED5), KED5, &h);
    cl_mem m_ters = clCreateBuffer(bag, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(KUCUK_TERS), KUCUK_TERS, &h);
    cl_mem m_sinir = clCreateBuffer(bag, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(KUCUK_SINIR), KUCUK_SINIR, &h);
    const int64_t PARTI = 1 << 24; /* 16M asal = 128 MB */
    cl_mem m_asal = clCreateBuffer(bag, CL_MEM_READ_ONLY, sizeof(uint64_t) * PARTI, NULL, &h);
    KONTROL(h, "asal tamponu");
    cl_mem m_bay = clCreateBuffer(bag, CL_MEM_READ_WRITE, PARTI, NULL, &h);
    KONTROL(h, "bayrak tamponu");

    /* isinma (derleme/ilk calistirma maliyeti olcume girmesin) */
    for (int tur = 0; tur < 2; tur++) {
        double t_aktar = 0, t_cek = 0;
        t0 = saat();
        for (int64_t bas = 0; bas < adet; bas += PARTI) {
            int64_t n = adet - bas < PARTI ? adet - bas : PARTI;
            if (tur == 0 && bas > 0)
                break;
            double a = saat();
            KONTROL(clEnqueueWriteBuffer(kuyruk, m_asal, 1, 0, sizeof(uint64_t) * n, asallar + bas, 0, NULL, NULL), "yazma");
            double b = saat();
            cl_ulong nn = (cl_ulong)n;
            clSetKernelArg(cek, 0, sizeof(cl_mem), &m_asal);
            clSetKernelArg(cek, 1, sizeof(cl_mem), &m_bay);
            clSetKernelArg(cek, 2, sizeof(cl_ulong), &nn);
            clSetKernelArg(cek, 3, sizeof(cl_mem), &m_ked5);
            clSetKernelArg(cek, 4, sizeof(cl_mem), &m_ters);
            clSetKernelArg(cek, 5, sizeof(cl_mem), &m_sinir);
            size_t yerel = 256, genel = ((size_t)n + yerel - 1) / yerel * yerel;
            KONTROL(clEnqueueNDRangeKernel(kuyruk, cek, 1, NULL, &genel, &yerel, 0, NULL, NULL), "cekirdek calistirma");
            KONTROL(clFinish(kuyruk), "bekleme");
            double c = saat();
            KONTROL(clEnqueueReadBuffer(kuyruk, m_bay, 1, 0, n, gpu + bas, 0, NULL, NULL), "okuma");
            double d = saat();
            t_aktar += (b - a) + (d - c);
            t_cek += c - b;
        }
        double t_gpu = saat() - t0;
        if (tur == 1)
            printf("Ilk adim (GPU): %.3f sn toplam = %.3f sn hesap + %.3f sn veri aktarimi\n", t_gpu, t_cek, t_aktar);
        if (tur == 1) {
            int64_t fark = 0, ilk_fark = -1;
            for (int64_t i = 0; i < adet; i++)
                if (cpu[i] != gpu[i]) {
                    if (ilk_fark < 0)
                        ilk_fark = i;
                    fark++;
                }
            if (fark)
                printf("DOGRULUK: %lld FARK VAR! ilk: p=%llu cpu=%d gpu=%d\n", fark, asallar[ilk_fark], cpu[ilk_fark], gpu[ilk_fark]);
            else
                printf("DOGRULUK: GPU ve CPU %lld asalin hepsinde ayni sonucu verdi.\n", adet);
            printf("\nOZET (bu aralik icin):\n");
            printf("  CPU hatti   : elek %.2f + ilk adim %.2f + kalan %.2f = %.2f sn\n", t_elek, t_cpu, t_kalan, t_elek + t_cpu + t_kalan);
            printf("  GPU'lu hat  : elek %.2f + ilk adim(GPU) %.2f + kalan %.2f = %.2f sn (sirali)\n", t_elek, t_gpu, t_kalan, t_elek + t_gpu + t_kalan);
            printf("  Ilk adim hizlanmasi (GPU/CPU): %.2fx\n", t_cpu / t_gpu);
        }
    }

    /* --- 5. zincirin TAMAMI: CPU (24 is) ve GPU --- */
    uint16_t *cpu_z = (uint16_t *)malloc(sizeof(uint16_t) * adet), *gpu_z = (uint16_t *)malloc(sizeof(uint16_t) * adet);
    t0 = saat();
#pragma omp parallel for schedule(dynamic, 65536)
    for (int64_t i = 0; i < adet; i++) {
        uint64_t z[MAKS_ZINCIR];
        int durum, uz = zincir(asallar[i], z, &durum);
        cpu_z[i] = (uint16_t)(uz | (durum << 8));
    }
    double t_cpu_tam = saat() - t0;
    cl_kernel cek2 = clCreateKernel(prog, "tam_zincir", &h);
    KONTROL(h, "tam_zincir cekirdegi");
    cl_mem m_son = clCreateBuffer(bag, CL_MEM_READ_WRITE, sizeof(uint16_t) * PARTI, NULL, &h);
    KONTROL(h, "sonuc tamponu");
    double t_gpu_tam = 0;
    for (int tur = 0; tur < 2; tur++) {
        t0 = saat();
        for (int64_t bas = 0; bas < adet; bas += PARTI) {
            int64_t n = adet - bas < PARTI ? adet - bas : PARTI;
            if (tur == 0 && bas > 0)
                break;
            KONTROL(clEnqueueWriteBuffer(kuyruk, m_asal, 1, 0, sizeof(uint64_t) * n, asallar + bas, 0, NULL, NULL), "yazma");
            cl_ulong nn = (cl_ulong)n;
            clSetKernelArg(cek2, 0, sizeof(cl_mem), &m_asal);
            clSetKernelArg(cek2, 1, sizeof(cl_mem), &m_son);
            clSetKernelArg(cek2, 2, sizeof(cl_ulong), &nn);
            clSetKernelArg(cek2, 3, sizeof(cl_mem), &m_ked5);
            clSetKernelArg(cek2, 4, sizeof(cl_mem), &m_ters);
            clSetKernelArg(cek2, 5, sizeof(cl_mem), &m_sinir);
            size_t yerel = 256, genel = ((size_t)n + yerel - 1) / yerel * yerel;
            KONTROL(clEnqueueNDRangeKernel(kuyruk, cek2, 1, NULL, &genel, &yerel, 0, NULL, NULL), "tam_zincir calistirma");
            KONTROL(clEnqueueReadBuffer(kuyruk, m_son, 1, 0, sizeof(uint16_t) * n, gpu_z + bas, 0, NULL, NULL), "okuma");
        }
        t_gpu_tam = saat() - t0;
    }
    int64_t fark = 0;
    int64_t uzunluk_say[70] = {0};
    for (int64_t i = 0; i < adet; i++) {
        if (cpu_z[i] != gpu_z[i])
            fark++;
        uzunluk_say[cpu_z[i] & 0xff]++;
    }
    printf("\nZINCIRIN TAMAMI:\n  CPU (%d is): %.3f sn\n  GPU        : %.3f sn (veri aktarimi dahil)\n  Hizlanma   : %.2fx\n",
           is_parcacigi, t_cpu_tam, t_gpu_tam, t_cpu_tam / t_gpu_tam);
    printf("  DOGRULUK: %s (%lld asal)\n", fark ? "FARK VAR!" : "GPU ve CPU her zincirde ayni uzunluk ve sonlanma", adet);
    printf("  Uzunluklar:");
    for (int k = 1; k < 70; k++)
        if (uzunluk_say[k])
            printf(" P%d=%lld", k, uzunluk_say[k]);
    printf("\n  Tahmini hat (elek CPU'da, zincir GPU'da, ikisi ayni anda): %.2f sn  <->  bugunku CPU hatti %.2f sn\n",
           t_elek > t_gpu_tam ? t_elek : t_gpu_tam, t_elek + t_cpu_tam);
    return 0;
}
