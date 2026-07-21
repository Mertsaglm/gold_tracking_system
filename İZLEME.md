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
| 3 | Kapsama bantta mı? | Raporun "Veri Kalitesi" satırı | **%60-100** (Actions ritmine göre ölçülür) | Uyarı satırı çıkarsa (kesinti > 270 dk) Actions'a bak (#1) |
| 4 | Veri artıyor mu? | `data/archive/` CSV satır sayısı, `data/altin.sql` diff | Her gün büyüyor | Büyümüyorsa arşiv workflow'u duraklatılmış olabilir (#1) |
| 5 | Bildirim sayısı makul mü? | Telegram | Günde birkaç, tavan 6/gün | Fazlaysa `config.yaml alerts` eşiklerini gevşet |
| 6 | Z-skor arşivi ilerliyor mu? | Haftalık pazar raporu → "Arşiv İlerlemesi: N/60 gün" | Her geçerli gün +1 | Bkz. aşağıdaki bölüm |

Hepsi beklenen aralıktaysa: **hiçbir şey yapma.** Sistem çalışıyor.

---

## Actions cron ritmi — beklenen davranış

`archive.yml` cron'u `*/15` (günde 96 çalışma) yazar, ama GitHub düşük aktiviteli repolarda
zamanlanmış iş akışlarını kısıtlar. Ölçülen gerçek: **günde 10-17 çalışma, aralar 1-3.5 saat.**

Sağlık metrikleri bu gözlemlenen ritme göre kalibre edilmiştir
(`config.yaml alerts.archive_observed_freq_minutes: 90`), yani kapsama %60-100 normal banttır ve
uyarı ancak kesinti 270 dk'yı aşınca çıkar. Cron sıklığını artırmak sonucu değiştirmez —
kısıtlama GitHub tarafındadır.

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

Senin yapman gereken bir şey yok — kod hazır, yalnız arşivin dolmasını bekliyor. İlerlemeyi
haftalık pazar raporundaki "Arşiv İlerlemesi" satırından takip et.

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
| Bildirim durumu | `data/alert_state.json` (soğuma + günlük tavan sayacı) |
| Raporlar | `reports/rapor_YYYY-MM-DD.md` |

SQLite binary'si repoya girmez; dump sayesinde repo şişmez ve geçmiş diff'lenebilir kalır.

---

_İnşa dönemi kapandı. Artık sadece izliyorsun._
