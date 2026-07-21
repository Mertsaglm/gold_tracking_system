# İZLEME — İzleme Dönemi El Kitabı

İnşa dönemi bitti. Sistem GitHub Actions'ta kendi kendine çalışıyor. Bu belge senin için
haftalık **5 dakikalık kontrol listesi** + sorun çıkarsa ne yapacağın.

> Kural: Yerelde bir şey çalıştırmadan önce **her zaman `git pull`** (bot 15 dk'da bir commit atıyor).

---

## Haftalık 5 dakikalık kontrol

| # | Kontrol | Nerede | Beklenen | Sorun görürsen |
|---|---|---|---|---|
| 1 | Actions yeşil mi? | GitHub → Actions sekmesi | "Altin arsivleyici" ve "Gunluk otonom rapor" son çalışmalar ✅ yeşil | Kırmızı çalışmaya tıkla, log'a bak; genelde geçici (kaynak erişimi) — sonraki tur düzelir |
| 2 | Günlük rapor düştü mü? | Telegram | Her akşam ~18:45 TR bir rapor | 1 gün gelmezse Actions "Gunluk otonom rapor" son çalışmasına bak |
| 3 | Kapsama % bantta mı? | Raporun "Veri Kalitesi" satırı | **%60-100 normal** (Actions ritmine göre ölçülür) | Uyarı satırı çıkarsa (kesinti > 270 dk) Actions'a bak (bkz. #1) |
| 4 | Veri artıyor mu? | Repo → `data/archive/` CSV satır sayısı, `data/altin.sql` diff | Her gün büyüyor | Büyümüyorsa arşiv workflow'u durmuş olabilir (#1) |
| 5 | Bildirim sayısı makul mü? | Telegram | Günde birkaç, spam yok (tavan 6/gün) | Spam varsa `config.yaml alerts` eşiklerini gevşet |
| 6 | Z-skor doluyor mu? | Haftalık rapor (pazar) "Arşiv İlerlemesi: X/60 gün" | Her gün ~+1 ilerliyor | ~60'a ulaşınca z-skor bildirimleri kendiliğinden açılır |

Hepsi yeşilse: **hiçbir şey yapma.** Sistem çalışıyor.

### ⚠️ Actions cron'u yazdığından çok daha seyrek çalışır — bu normal

`archive.yml` cron'u `*/15` (günde 96 çalışma) diyor, ama GitHub düşük aktiviteli repolarda
zamanlanmış iş akışlarını **kısıtlıyor**. 12-21 Temmuz 2026 ölçümü:

| Gün | Çalışma |
|---|---|
| 13 Tem | 10 |
| 14-17 Tem | 14-15 |
| 18 Tem | 17 |
| 19 Tem | 16 |
| 20 Tem | 11 |

Yani **günde 10-17 çalışma, aralar 1-3.5 saat.** Bu bir arıza değil, GitHub'ın kısıtlaması.
Sağlık metrikleri (`config.yaml alerts.archive_observed_freq_minutes: 90`) buna göre kalibre
edildi. **Arıza uyarısı ancak kesinti 270 dk'yı aşınca çıkar.**

Daha sık veri istiyorsan tek gerçek çözüm Oracle'a (7/24 collector) geçmek — Actions'ta
cron sıklığını artırmak işe yaramıyor, GitHub yine kısıtlıyor.

---

## İlk hafta sonu (11-13 Temmuz 2026) neye benzemeli?

İlk gerçek hafta sonu sınavı. **Endişelenme, şunlar NORMAL:**
- **Cumartesi-Pazar anomali bildirimi GELMEZ** — ons piyasası kapalı, durum makinesi
  `CLOSED_WEEKEND`'e geçer, anomali bildirimleri bastırılır. Bu doğru davranış.
- Hafta sonu en fazla **1 "pazartesi beklentisi" mesajı/gün** gelebilir (Kapalıçarşı fiyatının
  donmuş teoriğe göre sapması = piyasanın pazartesi için fiyatladığı hareket).
- **Pazartesi (14 Temmuz) raporu** ilk kez şu ek bölümü içermeli:
  **"Hafta Sonu Beklentisi vs Gerçekleşme"** — hafta sonu beklenti ortalaması + pazartesi
  gerçekleşen prim + fark. (Hafta içi bu bölüm görünmez; veri yoksa sessiz kalır.)
- Pazar akşamı günlük yerine **haftalık derin rapor** gelir (hafta dekompozisyonu + z-skor ilerlemesi).

Bunlar olmazsa Actions log'una bak; olursa sistem hafta sonu mantığını doğru işletiyor demektir.

---

## Acil durdurma

Sistem yanlış davranırsa (spam, hatalı veri):
1. GitHub → **Actions** sekmesi
2. Sol menüden workflow'u seç (**"Altin arsivleyici"** ve/veya **"Gunluk otonom rapor"**)
3. Sağ üst **"⋯" → "Disable workflow"**
4. Düzelttikten sonra aynı menü → **"Enable workflow"**

Bu, hiçbir veriyi silmez — sadece otomatik çalışmayı durdurur.

---

## Oracle'a geçiş günü checklist'i (hesabı açarsan)

Amaç: **çift veri olmasın** (Actions + Oracle aynı anda toplamasın).

1. **Actions'ı kapat:** yukarıdaki "Acil durdurma" ile her iki workflow'u Disable et.
2. **Kodu taşı:** `git clone https://github.com/Mertsaglm/gold_tracking_system.git altin`
3. **DB'yi kur:** `python -m src.restore_db` (repodaki `data/altin.sql` dump'ından SQLite'ı kurar —
   tüm geçmiş arşiv gelir).
4. **`.env` oluştur:** EVDS + Telegram (repoda yok, elle).
5. **systemd:** README "Oracle Cloud kurulumu" adımları (collector + bot + evds.timer + report.timer).
6. **Doğrula:** ilk collector tick'i düştü mü, Telegram raporu geldi mi.

Böylece Oracle canlı arşivi Actions'ın bıraktığı yerden devralır; **interaktif bot komutları**
(`/durum`, `/net`, `/aipaket`) da ilk kez 7/24 çalışır (Actions'ta bunlar yoktu).

---

## Sonraki temas noktaları
- **14 Temmuz Pazartesi:** ilk hafta sonu sınavının sonucu (pazartesi raporu + hafta sonu bölümü).
- **~60. gün:** z-skor arşivi dolunca prim z-skor bildirimleri kendiliğinden devreye girer.
- **Oracle hesabı açılırsa:** yukarıdaki geçiş checklist'i.

_İnşa dönemi kapandı. Artık sadece izliyorsun._
