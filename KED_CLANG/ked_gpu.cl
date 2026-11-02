/* PATI KED GPU cekirdegi (OpenCL). ked_cekirdek.dll bu dosyayi calisma aninda derler.
 * Her asal icin zincirin tamamini hesaplar; ked_cekirdek.c'deki zincir()/asal64/ked64 ile ayni sonuc.
 * GPU_DENEME klasorunde CPU ile birebir karsilastirildi. */

__constant uint KUCUK[45] = {3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73,
                             79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157,
                             163, 167, 173, 179, 181, 191, 193, 197, 199};
__constant ulong MR_TABAN[7] = {2UL, 325UL, 9375UL, 28178UL, 450775UL, 9780504UL, 1795265022UL};

inline ulong tek_ters(ulong n)
{
    ulong x = n;
    for (int i = 0; i < 5; i++)
        x *= 2UL - n * x;
    return x;
}

inline ulong mmul(ulong a, ulong b, ulong n, ulong nters)
{
    ulong alt = a * b, ust = mul_hi(a, b);
    ulong m = alt * nters, mu = mul_hi(m, n);
    return ust >= mu ? ust - mu : ust - mu + n;
}

inline ulong ekle_mod(ulong a, ulong b, ulong n) /* a,b < n */
{
    ulong s = a + b;
    return (s < a || s >= n) ? s - n : s;
}

int asal64(ulong n, __global const ulong *ters, __global const ulong *sinir)
{
    if (n < 2UL)
        return 0;
    if (!(n & 1UL))
        return n == 2UL;
    for (int i = 0; i < 45; i++) {
        if (n == (ulong)KUCUK[i])
            return 1;
        if (n * ters[i] <= sinir[i])
            return 0;
    }
    if (n < 199UL * 199UL)
        return 1;
    ulong nters = tek_ters(n);
    /* R = 2^64: bir = R mod n, R2 = R^2 mod n (64 kez ikiye katlayarak; 128 bit bolme gerekmez) */
    ulong bir = (0UL - n) % n;
    ulong r2 = bir;
    for (int i = 0; i < 64; i++)
        r2 = ekle_mod(r2, r2, n);
    ulong eksi_bir = n - bir;
    ulong m = n - 1UL, d = m;
    int s = 0;
    while (!(d & 1UL)) {
        d >>= 1;
        s++;
    }
    for (int t = 0; t < 7; t++) {
        ulong a = MR_TABAN[t] % n;
        if (a == 0UL)
            continue;
        ulong taban = mmul(a, r2, n, nters), x = bir;
        for (ulong e = d; e; e >>= 1) {
            if (e & 1UL)
                x = mmul(x, taban, n, nters);
            taban = mmul(taban, taban, n, nters);
        }
        if (x == bir || x == eksi_bir)
            continue;
        int r;
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

/* 0: sonuc 64 bite sigmiyor */
int ked64(ulong n, ulong *sonuc, __global const ulong *ked5)
{
    ulong s = 0, c = 1;
    while (n) {
        ulong parca = n % 100000UL;
        n /= 100000UL;
        ulong k = ked5[parca];
        if (mul_hi(k, c))
            return 0;
        ulong t = k * c, s2 = s + t;
        if (s2 < s)
            return 0;
        s = s2;
        if (n)
            c *= 100000UL;
    }
    *sonuc = s;
    return 1;
}

/* Zincirin TAMAMI (ked_cekirdek.c'deki zincir() ile ayni).
 * sonuc = uzunluk | (durum << 8); durum 0 bilesik, 1 sabit, 2 dongu, 3 64 bit tasma (uzunluk 0). */
__kernel void tam_zincir(__global const ulong *asallar, __global ushort *sonuc, ulong adet,
                         __global const ulong *ked5, __global const ulong *ters, __global const ulong *sinir)
{
    ulong i = get_global_id(0);
    if (i >= adet)
        return;
    ulong z[64];
    ulong p1 = asallar[i], n;
    int uz = 1, durum;
    z[0] = p1;
    if (!ked64(p1, &n, ked5)) {
        sonuc[i] = (ushort)(3 << 8);
        return;
    }
    for (;;) {
        int bulundu = 0;
        for (int k = 0; k < uz; k++)
            if (z[k] == n)
                bulundu = 1;
        if (bulundu) {
            if (n == p1 && uz == 1) {
                durum = 1;
                uz = 1;
            } else
                durum = 2;
            break;
        }
        if (!asal64(n, ters, sinir)) {
            durum = 0;
            break;
        }
        if (uz == 64) {
            durum = 3;
            uz = 0;
            break;
        }
        z[uz++] = n;
        if (!ked64(n, &n, ked5)) {
            durum = 3;
            uz = 0;
            break;
        }
    }
    sonuc[i] = (ushort)(uz | (durum << 8));
}
