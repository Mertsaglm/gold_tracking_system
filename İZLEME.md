# İZLEME — İzleme Dönemi El Kitabı

İnşa dönemi bitti. Sistem GitHub Actions'ta kendi kendine çalışıyor. Bu belge haftalık
**5 dakikalık kontrol listesi** ve karşılaşabileceğin durumların ne anlama geldiğidir.

> Kural: Yerelde bir şey çalıştırmadan önce **her zaman `git pull`** (sistem 15 dk'da bir commit atıyor).

---

## Haftalık 5 dakikalık kontrol

| # | Kontrol | Nerede | Beklenen | Sapma varsa |
|---|---|---|---|---|
| 1 | Actions yeşil mi? | GitHub → Actions | "Altin arsivleyici" ve "Gunluk otonom rapor" son çalışmalar ✅ | Kırmızı çalışmanın log'una bak; kaynak erişimi kaynaklıysa sonraki tur düzelir |
| 2 | Günlük rapor düştü mü? | Telegram | Her akşam ~18:45 TR bir rapor | 1 gün gelmezse "Gunluk otonom rapor" son çalışmasına bak |
| 3 | Kapsama bantta mı? | Raporun "Veri Kalitesi" satırı | **%60-100** (Actions ritmine göre ölçülür) | ⚠️ çıkarsa Actions'a bak (#1); ℹ️ çıkarsa bir şey yapma (aşağıya bak) |
| 4 | Veri artıyor mu? | `data/archive/` CSV satır sayısı, `data/altin.sql` diff | Her gün büyüyor | Büyümüyorsa arşiv workflow'u duraklatılmış olabilir (#1) |
| 5 | Bildirim sayısı makul mü? | Telegram | Günde birkaç, tavan 6/gün | Fazlaysa `config.yaml alerts` eşiklerini gevşet |
| 6 | Z-skor arşivi ilerliyor mu? | Haftalık pazar raporu → "Arşiv İlerlemesi: N/60 gün" | Her geçerli gün +1 | Bkz. aşağıdaki bölüm |
| 7 | **Tahmin kaydı birikiyor mu?** | `grep -c "INTO predictions(" data/altin.sql` | Her gün **+6** (3 ufuk × 2 kol) | Sayı durduysa `daily_job` adım 3d patlıyordur — Actions log'unda `tahmin hata` ara |
| 8 | **HÜKÜM raporun başında mı?** | Telegram günlük raporu | İlk ekranda "🎯 HÜKÜM" bloğu | Yoksa `karar.enabled` kapalı ya da blok hata almış (`hukum blogu hata`) |
| 9 | **Dump şişmiyor mu?** | `wc -l data/altin.sql` | Günde ~**+15-20 satır** (yeni gözlemler) | Günde binlerce satır artıyorsa tick tekilliği kopmuş — `grep -c "INTO ticks(" data/altin.sql` ile karşılaştır (ADR #009-C) |
| 10 | 🔴 **"PRİM ÖLÇÜM TAŞIMIYOR" satırı var mı?** | Raporun **en üstü** | Satır **YOK** | Varsa prim bir kimliğe çökmüş: teorik bacak ile piyasa bacağı bağımsız değil. **Prim, prim z-skoru ve hafta sonu beklentisi o gün karar taşımaz.** Bkz. ADR #014 |
| 11 | ⚠️ **"GÜNLÜK İŞ EKSİK ÇALIŞTI" satırı var mı?** | Raporun en üstü | Satır **YOK** | Varsa kritik olmayan bir adım (evds/ohlc/history/tahmin/grafik…) patlamış ve Actions **yeşil kalmış**. Satır hangi adım olduğunu yazar; Actions log'una bak |

> **Not:** dump `INSERT OR IGNORE` yazar; eski `grep -c "INSERT INTO ..."`
> komutları **0 döner**. Yukarıdaki `"INTO tablo("` biçimini kullan.

Hepsi beklenen aralıktaysa: **hiçbir şey yapma.** Sistem çalışıyor.

> **#7 neden var:** Ekim'deki taktik kapı kararının tek dayanağı bu birikimdir.
> Kayıt sessizce dururca aylar sonra "karne boş" diye fark edilirdi — ADR #004'teki
> `history_daily` donmasının aynısı. **Ama dikkat:** kaydın birikmesi karnenin
> ÖLÇTÜĞÜ anlamına gelmez; bugün karne "tabana fark / gram etkisi" üretemiyor
> (ADR #008) ve bunu raporda açıkça yazıyor.

---

## Actions cron ritmi — beklenen davranış

`archive.yml` cron'u `*/15` (günde 96 çalışma) yazar, ama GitHub düşük aktiviteli repolarda
zamanlanmış iş akışlarını kısıtlar. Ölçülen gerçek: **günde 10-17 çalışma, aralar 1-3.5 saat.**

Sağlık metrikleri bu gözlemlenen ritme göre kalibre edilmiştir
(`config.yaml alerts.archive_observed_freq_minutes: 90`), yani kapsama %60-100 normal banttır ve
uyarı ancak boşluk 270 dk'yı aşınca çıkar. Cron sıklığını artırmak sonucu değiştirmez —
kısıtlama GitHub tarafındadır.

⚠️ **Ritim çok oynak — 2026-08-28 ölçümü:** 08-25 ~30, 08-26 **24**, ama 08-27 ve
08-28 **yalnız 2 çalışma/gün**. Koşumlar başarısız değil, **hiç tetiklenmiyor**;
`gh run list` hepsini `success` gösterir. Rapor bu durumu "N ardışık çalışma
başarısız" diye yazıyor — **kelime yanlış**, koşmadılar. Gün sayacı etkilenmez
(günde 2 kayıt da o günü sayar) ama gün-içi ölçüm gücü düşer: bağımsızlık
nöbetçisi 5 kayıttan az günde hüküm veremez ve komşu günün hükmünü taşır.
`archive_observed_freq_minutes: 90` bu dalgalanmaya göre yeniden kalibre
edilmedi — payda bayat, metrik gerilemeleri gizleyebilir (açık iş).

### İki boşluk türü karıştırılmamalı

Rapor iki farklı şeyi ayrı ayrı yazar; hangisinin çıktığına bak:

| Satır | Ne ölçer | Ne yapmalısın |
|---|---|---|
| **çekim** boşluğu | Actions gerçekten çalıştı mı | ⚠️ uyarı çıkarsa Actions'a bak |
| **prim** boşluğu | Prim hesaplanabilen kayıtlar arası boşluk — kaynak (Truncgil) boş dönerse Actions sorunsuz çalışsa da büyür | ℹ️ satırı çıkarsa **bir şey yapma**; kaynak-retry devrede, sonraki tur toparlar |

Yani "545 dk prim boşluğu" tek başına arıza demek değildir; Actions o sırada tam zamanında
çalışmış olabilir. Rapor bunu kendisi ayırt edip doğru ikonu koyar.

---

## Prim z-skoru — arşiv birikimi

Prim z-skoru, sistemin kendi biriktirdiği veriye dayanan tek sinyalidir. Kapalıçarşı priminin
tarihsel dağılımı hazır satılmadığı için arşiv **7 Temmuz 2026'da sıfırdan** başladı.

**Kapı gün sayar, kayıt değil.** Arşiv gün içinde ~10 örnek alır; bunlar birbirinin tekrarı
olduğundan kayıt saymak bağımsız gözlem sayısını şişirir ve z-skoru "2 haftalık ortalamadan sapma"
ölçmeye indirger. Kapı bu yüzden geçerli **gün** sayısına bakar (hafta sonu ve `indicative`
kayıtlar hariç).

| Durum | Ne görürsün |
|---|---|
| Kapı kapalıyken | Sinyal `veri_bekliyor`; rapor `⏳ arşiv birikiyor (N/60 gün)` |
| Eşik | 60 geçerli gün (`config.yaml stats.zscore_min_samples`) |
| Kapı açıldığında | Prim z-skor sinyali ve `z > 2` bildirimi **kendiliğinden** devreye girer |

İlerlemeyi haftalık pazar raporundaki "Arşiv İlerlemesi" satırından takip et.

### 🔴 Kapı ne zaman açılır? — SAYAÇ ŞU AN DURDU (2026-08-28, ADR #014)

**Eski tahmin (~12 Eylül, sonra ~2 Ekim) GEÇERSİZ.** Bağımsızlık nöbetçisi
2026-08-17 sonrası günleri `turetilmis` işaretlediği için geçerli gün
**30 → 19** düştü ve ileriye dönük **yeni geçerli gün üretilmiyor**.

Sebebi: ons ile gramın ikisi de Truncgil'den gelince ons prim formülünde
sadeleşiyor; prim artık piyasayı değil satıcının saflık çarpanını ölçüyor
(ölçüldü: varyansın **%99.81'i** iki USD beslemesinin oranı). Sayaç ilerleseydi
kapı bir **kimlik** üzerinden açılırdı.

**Bu bir arıza değil, nöbetçinin doğru çalışması.** Sayaç ancak bağımsız bir
spot ons kaynağı devreye girince yeniden ilerler — o karar `ai/STATE.md` →
**Sıradaki 3 İş** → 1 numaralı satırda, sende.

⚠️ Kapı yeniden açılmaya başladığında taban **sıfırdan** kurulmalı: kalan 19 gün
eski yfinance rejiminden ve o rejim yenisiyle aynı dağılım değil (F=11.73,
ortalama farkı −0.139p).

**Kapı açılmadan ~1 hafta önce yapılacak kritik iş:** `data/zskor_prova.jsonl`
okunup z'nin hangi tabanda hesaplanacağına karar verilmeli (aşağıya bak).
⚠️ Karar **kanal başına** verilmeli — ölçüldü 2026-08-28: prim kanalında iki
taban **0/34** uyuşmazlık, **çeyrek kanalında 6/34**. "İki taban aynı kararı
veriyor" iddiası yalnız prim için doğru. Tam liste `ai/STATE.md` → **TAKVİM**.

### Kuru prova (dry-run) nedir, neden var?

Kapı açıldığı gün `z > 2` bildirimi **ilk kez** ateşlenecek ve o ana dek hiç
denenmemiş olacak. Kalibrasyonsuz açılırsa beklenmedik sıklıkta alarm günlük tavanı
(6) doldurup diğer bildirimleri bastırabilir.

Bu yüzden sistem her gün "z ne olurdu" sorusunu hesaplayıp `data/zskor_prova.jsonl`'a
yazıyor — **bildirim göndermeden.** Prova iki tabanı karşılaştırıyor:

| Taban | Nedir | 2026-07-25 ölçümü |
|---|---|---|
| **kayıt** | tüm prim kayıtları (mevcut hesap) | prim z=+0.92 · çeyrek z=−0.85 |
| **gün** | günlük ortalamalar (kapıyla tutarlı) | prim z=**+1.36** · çeyrek z=**−1.38** |

Gün tabanında std daha küçük (gün içi tekrar örnekleme ortalanıyor) → aynı sapma
daha büyük z üretiyor, yani **daha sık tetikler**. Hangisinin kullanılacağı kapı
açılmadan, birikmiş prova verisine bakılarak kararlaştırılacak.

---

## Hafta sonu davranışı

Hafta sonları ons piyasası kapalıdır, durum makinesi `CLOSED_WEEKEND`'e geçer:

- **Anomali bildirimi gelmez** — üç bacak FRESH olmadığı için bastırılır. Doğru davranış.
- Günde en fazla **1 "pazartesi beklentisi" mesajı** gelebilir (Kapalıçarşı fiyatının donmuş
  teoriğe göre sapması = piyasanın pazartesi için fiyatladığı hareket).
- **Pazartesi raporu** "Hafta Sonu Beklentisi vs Gerçekleşme" bölümünü içerir: hafta sonu beklenti
  ortalaması + pazartesi gerçekleşen prim + fark. Hafta içi bu bölüm görünmez.
- **Pazar akşamı** günlük yerine haftalık derin rapor gelir (hafta dekompozisyonu + arşiv ilerlemesi).

---

## Sistemi duraklatma

1. GitHub → **Actions** sekmesi
2. Sol menüden workflow'u seç ("Altin arsivleyici" ve/veya "Gunluk otonom rapor")
3. Sağ üst **"⋯" → "Disable workflow"**
4. Devam etmek için aynı menü → **"Enable workflow"**

Bu hiçbir veriyi silmez — yalnız otomatik çalışmayı durdurur.

---

## Veri nerede duruyor

| Ne | Nerede |
|---|---|
| Canlı arşiv (ham) | `data/archive/YYYY-MM.csv` — her Actions çalışması bir satır ekler |
| Ana veritabanı | `data/altin.sql` (metin dump, commit'lenir) → `src/restore_db.py` ile SQLite'a açılır |
| Bildirim durumu | `data/alert_state.json` — soğuma + günlük tavan sayacı + **sağlık defteri**: `saglik.ardisik_hata` (bildirim hattı, ADR #011) ve `saglik.gunluk_adimlar` (günlük işin patlayan adımları, ADR #014). Raporun en üstündeki kırmızı satırlar buradan okunur |
| Giden Telegram mesajları | `data/telegram_outbox.jsonl` — bota gönderilen her rapor/alarm (denetim için; Telegram export'una gerek yok) |
| Z-skor kuru provası | `data/zskor_prova.jsonl` — günde 1 satır; kapı açılmadan "z ne olurdu" kaydı (bildirim göndermez) |
| Türetilmiş prim işareti | `prim_history.reason = 'turetilmis'` (DB) — bağımsızlık nöbetçisinin kapı dışına aldığı kayıtlar. Kayıt **silinmez**, yalnız `indicative=1` olur (ADR #014) |
| Raporlar | `reports/rapor_YYYY-MM-DD.md` |

SQLite binary'si repoya girmez; dump sayesinde repo şişmez ve geçmiş diff'lenebilir kalır.

---

## Bir şeyi değiştirmek gerekirse (ya da bir AI'a yaptırırsan)

Proje 800+ testle korunuyor (ADR #009). Değişiklikten sonra tek komut yeterli:

```bash
.venv/bin/python -m pytest -q      # ~5 sn, ağa çıkmaz, gerçek DB'ye dokunmaz
```

**Kırmızı bir test neredeyse daima haklıdır** — testlerin çoğu bir kararı
(ADR) ya da bir dersi (LESSONS) kilitliyor ve gerekçesi testin docstring'inde
yazılı. Önce onu oku; testi susturmak, korumayı sessizce kaldırmakla aynı şey.

Sık karşılaşacakların:

| Test der ki | Anlamı |
|---|---|
| "önceden kayıtlı eşik gevşetilmiş" | `config.yaml`'da bir kapı/eşik düşürülmüş — bu ancak ADR ile yapılır |
| "şemada olup dump'a girmeyen tablo" | Yeni tablo `dbdump._TABLES`'a eklenmemiş → Actions'ta her gün silinir |
| "karar katmanına ağ girdi" | Hesap/karar koduna `requests`/`yfinance` eklenmiş → replay ile canlı ayrışır |
| "ikinci asof yolu" | `history_daily` üzerinde ikinci bir `MAX(date)` → L-011'in tekrarı |
| "tekrar eden tick" | Tekillik koruması kopmuş → dump her gün şişer (L-013) |

---

_İnşa dönemi kapandı. Artık sadece izliyorsun._
