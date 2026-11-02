# PATİ KED asal zincir taraması

Bir asal sayı `p`'den başlayıp **KED** değerini tekrar tekrar alan ve sonuç asal kaldıkça uzayan zincirleri tarar.

```
KED(n) = Σ (rakam²) · 10^konum
```

Rakam kareleri yan yana yazılmaz; her rakamın karesi kendi basamak değeriyle çarpılıp toplanır.
Örnek: `KED(23) = 2²·10 + 3²·1 = 49`.

Zincir `p1 → KED(p1) → KED(KED(p1)) …` asal kaldığı sürece uzar. Uzunluğu 6 ve üzeri olan zincirler (P6+) kaydedilir.

## Klasörler

| Klasör | İçerik |
|---|---|
| `KED/` | CPU sürümü: Python arayüzü + C hesap çekirdeği (`ked_cekirdek.dll`) |
| `KED_GPU/` | GPU sürümü: aynı program, zincirler ayrıca ekran kartında (OpenCL) hesaplanır |
| `KED_GPU/GPU_DENEME/` | GPU'yu CPU ile karşılaştıran bağımsız deneme programı |
| `*/PATI_TARAMALAR/ARALIK_<baş>_<bit>/` | Tarama sonuçları (aşağıya bakın) |

İki sürüm birbirinden bağımsızdır; sonuçlarını kendi `PATI_TARAMALAR` klasörlerine yazar.

## Çalıştırma

Gereken: Windows, Python 3.9+ (ek paket yok). GPU sürümü için OpenCL destekli bir ekran kartı (NVIDIA sürücüsü yeterli; CUDA Toolkit gerekmez).

```
python KED\PATI_5_10_TRILYON_HIZLI_UI.py          (CPU sürümü, pencereli)
python KED_GPU\PATI_5_10_TRILYON_HIZLI_UI.py      (GPU sürümü, pencereli)
```

Konsol penceresi olmadan açmak için `PATI_BASLAT.pyw` dosyasını `pythonw` ile çalıştırın.

Pencerede:
- **Başlangıç / Bitiş** aralığı elle girilir. Her aralık kendi klasörüne kaydedilir.
- **Çekirdek (işçi)** sayısı tarama sürerken değiştirilebilir.
- **Durdur** ile durdurulan tarama, Başlat'a basınca son kaydedilen 1 milyarlık bölümden devam eder.
- İsteğe bağlı olarak sayaçlar her N dakikada bir maille gönderilir (`MAIL_AYARLARI.txt`, Gmail uygulama şifresi; bu dosya depoya yüklenmez).

Konsol: `--konsol`, `--start`, `--end`, `--workers`, `--mail`, `--python` (C çekirdeği yerine saf Python), GPU sürümünde `--gpusuz`.

C çekirdeğini yeniden derlemek için: `derle.bat` (Visual Studio 2022 Build Tools).

## Sonuç dosyaları

```
PATI_TARAMALAR\ARALIK_5.000.000.000.000_10.000.000.000.000\
  SAYACLAR.txt          P1 … P20, P21+, döngü, asal toplamı (okunur özet)
  PATI_CHECKPOINT.txt   kaldığı yer + sayaçlar + son bölümün SHA256 doğrulaması
  CALISMA_GUNLUGU.txt   oturumlar, işçi değişiklikleri
  P6\ P7\ … P20\ P21_PLUS\ DONGU\   her 1 milyarlık bölüm için bir dosya (hizalı tablo)
```

Depoda yer kaplamaması için `P6` ve `P7` zincir dosyaları yüklenmez; `P8` ve üzeri yüklenir.

## Doğruluk

Her değişiklikten sonra çıktılar, `KED/PATI_5_10_TRILYON_ESKI_USUL_EKRAN_VE_TXT (1).py` (orijinal tek çekirdekli program) ile küçük aralıklarda birebir karşılaştırıldı: zincir dosyaları ve tüm sayaçlar aynı.
Asallık testi 64 bit için kesin (7 tabanlı Miller–Rabin). KED değeri 64 biti aşan nadir zincirler orijinal Python yöntemiyle incelenir.

## Hız (Intel Core Ultra 9 285K, NVIDIA RTX 2000 Ada)

| Sürüm | İşçi | Saniyede sayı | 5 trilyon |
|---|---|---|---|
| Orijinal (tek çekirdek, Python) | 1 | 6 milyon | ~9,7 gün |
| Python, çok işlem | 24 | 127 milyon | ~11 saat |
| C çekirdeği (`KED`) | 24 | 3,46 milyar | ~24 dk |
| C + GPU (`KED_GPU`) | 28 | 5,65 milyar | ~15 dk |

## Sonuçlar

5–10 trilyon (CPU sürümü, 2 Kasım 2026): 168.773.875.190 asal incelendi; en uzun zincirler **P10 (6 adet)**, P9: 91, P8: 1.358. P11 ve üzeri ile döngü bulunmadı. Ayrıntı: `KED/PATI_TARAMALAR/ARALIK_5.000.000.000.000_10.000.000.000.000/SAYACLAR.txt`.
