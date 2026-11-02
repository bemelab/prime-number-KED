# -*- coding: utf-8 -*-
"""PATİ: 5–10 trilyon / TEK ISLEM / P6+ EKRANDA VE TXT / güvenli checkpoint.
Python 3.9+, ek paket gerekmez. Eski 5–5.5T checkpointini ve zincirlerini OKUMAZ/DEĞİŞTİRMEZ.
Sadece tamamlanan 1 milyarlik bölümlerin kayıtları kalıcıdır; yarım bölüm yeniden taranır.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

BASLANGIC = 5_000_000_000_000
BITIS = 10_000_000_000_000  # hariç
ELEK_BLOGU = 2_000_000
KAYIT_ADIMI = 1_000_000_000
RAPOR_ARALIGI = 100_000_000
MR_BASES_64 = (2, 325, 9375, 28178, 450775, 9780504, 1795265022)
MR_BASES_BUYUK = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
KARELER = tuple(i*i for i in range(10))
SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
FORMAT = 'PATI_5_10_TAM_KAYIT_v1'


def ked(n):
    sonuc = 0
    basamak = 1
    while n:
        n, rakam = divmod(n, 10)
        sonuc += KARELER[rakam] * basamak
        basamak *= 10
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


def zinciri_incele(p1):
    zincir = [p1]
    gorulen = {p1}
    n = p1
    buyuk_mr = 0
    while True:
        n = ked(n)
        if n in gorulen:
            # Asal sabit nokta özel P1 durumu. Gerçek döngüler ayrı sayılır.
            if n == p1 and len(zincir) == 1:
                return 1, zincir, 'sabit', buyuk_mr
            return len(zincir), zincir, 'dongu', buyuk_mr
        asal, buyuk = asal_mr(n)
        if buyuk:
            buyuk_mr += 1
        if not asal:
            return len(zincir), zincir, 'bilesik', buyuk_mr
        gorulen.add(n)
        zincir.append(n)


def elekteki_asallar(alt, ust, temel_asallar):
    ilk_tek = alt | 1
    adet = max(0, (ust - ilk_tek + 1) // 2)
    if adet == 0:
        return
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
    for i, isprime in enumerate(elek):
        if isprime:
            yield ilk_tek + 2*i


def atomic_json(path, data):
    temp = path.with_suffix(path.suffix+'.tmp')
    with open(temp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def new_counts():
    return [0]*12  # P1–P10 TAM uzunluk, P11+ birlikte, indeks 0 kullanılmaz


def get_chunk_path(folder, alt, ust):
    return folder/'ZINCIRLER_P6_PLUS' / ('P6_PLUS_%d_%d.jsonl' % (alt,ust))


def txt_path(folder, alt, ust):
    return folder / 'P6_TUM_TERIMLER_TXT' / ('P6_ZINCIRLER_%d_%d.txt' % (alt, ust))


def zincir_metni(p1, length, chain, status):
    satirlar = ['=' * 56, 'P%d ZINCIRI BULUNDU' % length,
                'Baslangic: %d' % p1, 'Uzunluk: %d' % length]
    for i, n in enumerate(chain, 1):
        satirlar.append('p%d = %d' % (i, n))
    satirlar.append('Sonlanma: ' + status)
    satirlar.append('')
    return '\n'.join(satirlar) + '\n'


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
    if not isinstance(counts,list) or len(counts)!=12 or any(type(n)!=int or n<0 for n in counts):
        raise RuntimeError('Checkpoint sayaçları geçersiz.')
    latest=d.get('son_dosya')
    if limit>start:
        if not isinstance(latest,dict):
            raise RuntimeError('Checkpoint son kayıt kanıtı eksik.')
        path=folder/'ZINCIRLER_P6_PLUS'/latest['ad']
        if not path.is_file():
            raise RuntimeError('Checkpoint var ama zincir kayıt dosyası EKSİK: '+str(path))
        dig=hashlib.sha256(path.read_bytes()).hexdigest()
        if dig != latest.get('sha256'):
            raise RuntimeError('Son kaydedilen zincir dosyasının SHA256 doğrulaması başarısız.')
        last_txt = folder / 'P6_TUM_TERIMLER_TXT' / latest.get('txt_ad', '')
        if not last_txt.is_file():
            raise RuntimeError('Checkpoint var ama P6+ TXT kaydı eksik: ' + str(last_txt))
        if hashlib.sha256(last_txt.read_bytes()).hexdigest() != latest.get('txt_sha256'):
            raise RuntimeError('TXT dosyası doğrulaması başarısız; kayıtlar değiştirilmiş olabilir.')
    return limit


def tara(start,end,block,chunk,report_every,output,show_min,cooldown):
    if output.exists() and not output.is_dir():
        raise RuntimeError('Çıktı klasörü yerine bir dosya var: '+str(output))
    output.mkdir(parents=True,exist_ok=True)
    chunksdir=output/'ZINCIRLER_P6_PLUS'
    chunksdir.mkdir(exist_ok=True)
    txtdir=output/'P6_TUM_TERIMLER_TXT'
    txtdir.mkdir(exist_ok=True)
    ckpath=output/'PATI_CHECKPOINT.json'
    if ckpath.is_file():
        with open(ckpath,'r',encoding='utf-8') as f:
            d=json.load(f)
        alt=check_checkpoint(d,start,end,chunk,block,output)
    else:
        oldfiles=list(chunksdir.glob('P6_PLUS_*.jsonl'))
        if oldfiles:
            raise RuntimeError('Checkpoint yok, fakat zincir kayıtları var! SİLMEYİN; önce kurtarma gerek.')
        alt=start
        d={'format':FORMAT,'baslangic':start,'bitis':end,'elek_blogu':block,
           'kayit_adimi':chunk,'tamamlanan_sinir':start,
           'sayac_tam_uzunluk':new_counts(),'asal_toplami':0,
           'dongu':0,'64_bit_ustu_mr_test':0,'son_dosya':None}
        atomic_json(ckpath,d)
    print('PATI | TEK ISLEM | BASLANGIC',start,'BITIS',end,'| TAMAMLANDI',alt,flush=True)
    print('P6+ TAM ZINCIRLER TXT KLASORU:',txtdir,flush=True)
    print('P6 VE UZERI BUTUN ZINCIRLER EKRANDA GORUNECEK!',flush=True)
    print('P1..P10 sayaclari TAM uzunluk; P11+ ayrı. ',flush=True)
    temel_asallar=temel_asallari_bul(math.isqrt(end-1))
    processed=0
    t0=time.monotonic()
    try:
        while alt < end:
            ust=min(alt+chunk,end)
            chunk_counts=new_counts()
            chunk_asil=0
            chunk_cycles=0
            chunk_prob=0
            tmp_path=get_chunk_path(output,alt,ust).with_suffix('.jsonl.tmp')
            final_path=get_chunk_path(output,alt,ust)
            final_txt=txt_path(output,alt,ust)
            temp_txt=final_txt.with_suffix('.txt.tmp')
            with open(tmp_path,'w',encoding='utf-8',buffering=1<<20) as f, open(temp_txt,'w',encoding='utf-8',buffering=1<<20) as ft:
                for subalt in range(alt,ust,block):
                    subust=min(subalt+block,ust)
                    for p1 in elekteki_asallar(subalt,subust,temel_asallar):
                        length,chain,status,nlarge=zinciri_incele(p1)
                        chunk_asil+=1
                        chunk_prob+=nlarge
                        if status=='dongu':
                            chunk_cycles+=1
                        else:
                            chunk_counts[min(length,11)]+=1
                        if length>=6 or status=='dongu':
                            item={'baslangic':p1,'uzunluk':length,'zincir':chain,
                                  'sonlanma':status,'asal_testi':'MR_olasi_64_ustu' if nlarge else 'MR_64bit_kesin'}
                            f.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')
                            if length >= 6:
                                metin=zincir_metni(p1,length,chain,status)
                                ft.write(metin)
                                if length>=show_min:
                                    print(metin,flush=True)
                f.flush()
                os.fsync(f.fileno())
                ft.flush()
                os.fsync(ft.fileno())
            os.replace(tmp_path,final_path)
            os.replace(temp_txt,final_txt)
            with open(final_path,'rb') as f:
                dig=hashlib.file_digest(f,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(f.read()).hexdigest()
            newd=dict(d)
            newd['tamamlanan_sinir']=ust
            newd['sayac_tam_uzunluk']=[x+y for x,y in zip(d['sayac_tam_uzunluk'],chunk_counts)]
            newd['asal_toplami']=d['asal_toplami']+chunk_asil
            newd['dongu']=d['dongu']+chunk_cycles
            newd['64_bit_ustu_mr_test']=d['64_bit_ustu_mr_test']+chunk_prob
            newd['son_dosya']={'ad':final_path.name,'sha256':dig,
                                 'txt_ad':final_txt.name,
                                 'txt_sha256':hashlib.sha256(final_txt.read_bytes()).hexdigest()}
            if sum(newd['sayac_tam_uzunluk'])+newd['dongu'] != newd['asal_toplami']:
                raise RuntimeError('Sayaçların asal toplamı ile uyuşmazlığı!')
            atomic_json(ckpath,newd)
            d=newd
            processed += (ust-alt)
            alt=ust
            print('KAYDEDILDI: %s | Yeni asal %s | TOPLAM P9=%s P10=%s P11+=%s | %0.1f%%'%(f'{ust:,}',f'{chunk_asil:,}',f'{d["sayac_tam_uzunluk"][9]:,}',f'{d["sayac_tam_uzunluk"][10]:,}',f'{d["sayac_tam_uzunluk"][11]:,}',100*(ust-start)/(end-start)),flush=True)
            if cooldown:
                time.sleep(cooldown)
    except KeyboardInterrupt:
        print('\nDURDURULDU. Son TAMAMLANAN ve kalıcı sınır:',d['tamamlanan_sinir'],flush=True)
        return
    print('\nTARAMA TAMAMLANDI. Checkpoint:',ckpath,'Toplam asallar:',d['asal_toplami'])
    for k in range(1,11):
        print('P%d ='%k,d['sayac_tam_uzunluk'][k])
    print('P11+ =',d['sayac_tam_uzunluk'][11])
    print('ASAL DONGU =',d['dongu'])
    print('64 BIT USTU MR TESTI =',d['64_bit_ustu_mr_test'])
    print('GECEN SURE saniye =',round(time.monotonic()-t0,1))


def main():
    p=argparse.ArgumentParser(description='PATİ tek işlemli 5–10 trilyon güvenli P6+ kayıt')
    p.add_argument('--start',type=int,default=BASLANGIC)
    p.add_argument('--end',type=int,default=BITIS)
    p.add_argument('--block',type=int,default=ELEK_BLOGU)
    p.add_argument('--chunk',type=int,default=KAYIT_ADIMI)
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'PATI_5_10_TRILYON_SONUCLAR')
    p.add_argument('--show-min',type=int,default=6,help='Ekrana basılan minimum uzunluk, varsayilan P6')
    p.add_argument('--cooldown',type=float,default=0,help='Her kayıt adımından sonra dinlenme süresi saniye')
    a=p.parse_args()
    if a.start <3 or a.start>=a.end or a.block<=0 or a.chunk<=0 or a.chunk%a.block or a.cooldown<0 or a.show_min<1:
        p.error('Geçersiz sınırlar veya parametreler')
    # Varsayılan dosya adı 5–10 trilyon için; özel --start/--end testleri ayrı klasörde kullanılmalıdır.
    tara(a.start,a.end,a.block,a.chunk,RAPOR_ARALIGI,a.output,a.show_min,a.cooldown)

if __name__=='__main__':
    main()
