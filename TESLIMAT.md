# TESLIMAT — Faz 1 Kapanışı + Canlıya Alma

Güncelleme: 2026-07-07 · Ortam: Windows (geliştirme), Python 3.12.4, .venv

## Kapsam değişikliği (kullanıcı kararı)
- **C. Windows 7/24 kalıcı çalıştırma: İPTAL.** 7/24 çalıştırma sonraki fazda GitHub Actions'a verildi.
  Kurulan Windows artefaktları temizlendi (aşağıda kanıt).
- **D. GitHub yedeği: ertelendi (opsiyonel).** Bu fazda biriken veri yok → acil değil.
  Yedekleme kodu repoda hazır (`backup_db.py`). Kalıcı çözüm sonraki fazda `data/altin.sql`
  dump'ının repoya commit'lenmesiyle geldi.

## Özet durum

| Bölüm | Durum |
|---|---|
| A. Telegram canlı | ✅ gerçek mesajlar gönderildi (bağlantı testi, rapor, /durum HTML) |
| B. EVDS canlı | ✅ 12 kod teyit, 5 yıl backfill (7531 satır), günlük job, rapor bağlamı |
| C. Windows 7/24 | ⛔ iptal (kullanıcı) — temizlendi |
| D. Yedekleme | ⏸️ ertelendi — kod hazır (`backup_db.py`, `backup.sh`) |
| E. Rapor zenginleştirme | ✅ dolar-bazlı getiri + kadran paneli + EVDS bağlam + kapsama satırı |
| F. Dokümantasyon | ✅ README, PROJE-REHBERI (rejim D + backlog), bu dosya |
| Testler | ✅ **31/31 geçti** (22 mevcut + 9 yeni gösterge) |

---

## A. Telegram (gerçek gönderim kanıtı)

Bot: `<bot_adı>` · chat_id `<chat_id>` (doğrulandı).

- **Bağlantı testi:** `sendMessage ok=True, message_id=19 -> chat_id <chat_id>` (HTML).
- **Gün sonu raporu:** `telegram: 1 parça gönderildi (chat=<chat_id>, mode=plain)` — tam rapor düz metin.
- **/durum (HTML):** gönderildi, 1 parça. `_` içeren metin (`tum_bacaklar_taze`) `<i>` içinde güvenli:
  ```
  <b>Anlık Durum</b> (20:02 TR) 🟢 geçerli
  Ons: <code>4154.20$</code> · USD/TRY: <code>46.8332</code>
  Teorik has gram: <code>6255.07₺</code> · Piyasa has gram: <code>6213.29₺</code>
  <b>Prim: -0.668%</b> · Makas: 0.015% · Çeyrek primi: -0.17%
  ```
- **Tuzak çözümleri:** raporlar **düz metin** (Markdown/HTML kaçış tuzağı yok), /durum **HTML** +
  `html.escape`; 4096 sınırı için satır-sınırında bölme; `/start` chat_id'si loglanıp `.env` ile
  karşılaştırılıyor (uyuşmazlıkta uyarı). Bot watchdog altında çökerse yeniden başlar.

## B. EVDS (canlı, teyit + backfill)

**Endpoint düzeltmesi:** eski `evds2/service/evds` artık SPA'ya yönleniyor. Doğru servis:
`https://evds3.tcmb.gov.tr/igmevdsms-dis`. **Değer ayrıştırma düzeltmesi:** EVDS değerleri
nokta-ondalıklı (`46.8204`), TR virgül değil → ayrı parser (yoksa 10× hata).

### Teyit tablosu

| Amaç | Kod | Frekans | Durum |
|---|---|---|---|
| USD alış/satış | TP.DK.USD.A.YTL / .S.YTL | günlük | ✅ |
| EUR alış | TP.DK.EUR.A.YTL | günlük | ✅ |
| TÜFE endeksi | TP.FE.OKTG01 | aylık | ✅ |
| **Külçe altın (Kapalıçarşı proxy)** | **TP.MK.KUL.YTL** | aylık | ✅ kritik hedef |
| Cumhuriyet altını | TP.MK.CUM.YTL | aylık | ✅ |
| Politika faizi (AOFM proxy) | TP.APIFON4 | günlük | ✅ |
| Mevduat 1ay/3ay/6ay/1yıl | TP.TRY.MT02/03/04/06 | haftalık | ✅ |
| 12 ay TÜFE beklentisi (piyasa) | TP.ENFBEK.PKA12ENF | aylık | ✅ |

**Bulunamayan:** saf "1 hafta repo politika faizi" tek serisi.
Denenen kodlar: `TP.PY.P01`, `TP.APIFON1` (400 Bad Request), `TP.MEVDUATTL` (400).
Çözüm: **TP.APIFON4 (AOFM = ağırlıklı ort. fonlama maliyeti, şu an %40)** politika faizi proxy'si
olarak kullanılıyor — pratikte efektif politika faizidir.

### Backfill (yıl-yıl chunk; EVDS ~1000 satır/istek sınırını aşar) — evds_daily = 7531 satır
```
USD satış (TP.DK.USD.S.YTL)      2897   2015-2026 (günlük)
AOFM     (TP.APIFON4)            2890   2015-2026 (günlük)
TÜFE     (TP.FE.OKTG01)           132   2015-2026 (aylık)
Külçe    (TP.MK.KUL.YTL)          137   2015-2026 (aylık)
Cumhuriyet (TP.MK.CUM.YTL)        137   2015-2026 (aylık)
Mevduat 3ay/1yıl (TP.TRY.MT03/06) 600 + 600  2015-2026 (haftalık)
12 ay beklenti (TP.ENFBEK.PKA12ENF) 138  2015-2026 (aylık)
```
Yıl-yıl kapsama doğrulandı (ör. USD ~252/yıl × 12 yıl). **Keşif:** 597 altın + 2080 faiz +
1845 anket serisi → `evds_series.json`.

## E. Rapor zenginleştirme

Üretilen raporda (`reports/rapor_2026-07-07.md`) yeni bölümler:

- **Dolar bazlı gram getirisi** satırı (dekompozisyonda): `= ons + prim` (kur etkisi çıkarılmış).
  "TL eridiği için mi kazandım?" sorusunun cevabı.
- **Makro Bağlam (EVDS):** politika %40.00 · 1 yıl mevduat brüt 47.43 → **net 40.32** ·
  TÜFE (yıllık) 30.89 · 12 ay beklenti 23.81 · **reel net mevduat +13.33%**.
- **Gösterge Uzlaşı Paneli** (canlı):
  ```
  ABD 10Y reel faiz    🔴 olumsuz  2.07% → 2.26% (+19bps/~1ay)
  Dolar endeksi (DXY)  🔴 olumsuz  +1.39% (~1ay)
  Ons 50/200 GMA       🔴 olumsuz  fiyat 4157 · 50G 4407 · 200G 4461
  TL reel net mevduat  🔴 olumsuz  +13.3%
  SPDR GLD tonaj       ➖ veri yok  (paydadan çıkarıldı)
  Uzlaşı: 🔴 olumsuz — skor -4/4 (normalize -1.00)
  ```
  Eşikler `config.yaml`'da; etiketleme mantığı **9 birim testle** doğrulandı.
- **Kapsama satırı:** "son 24s veri kapsaması %X, en uzun kesinti Y dk"; %80 altında uyarı +
  "z-skor yalnız FRESH kayıtları sayar" notu (boşluklar tarihçeyi bozmaz).

### Süreçte çözülen 2 gerçek hata
1. **Non-ASCII yol SSL hatası:** proje yolu `altın` içerdiği için `curl_cffi` cacert'i açamıyordu
   (yfinance GMA/GLD çekimi kırık). `util._ensure_ascii_cert()` cacert'i ASCII temp yola kopyalayıp
   env ayarlıyor. ASCII yolda devreye girmez.
2. **yfinance `period=300d` geçersiz** → `1y` + fallback ticker.

## C. Windows 7/24 — iptal & temizlik kanıtı
- 6 çalışan süreç durduruldu (çift supervisor dahil).
- Zamanlanmış görevler silindi: AltinRapor, AltinReconcile, AltinBackup (`SUCCESS ... deleted`).
- Startup VBS silindi. Kalan `src.*` süreç: **0**.
- (Not: `supervisor.py` tek-instance kilidiyle repoda kaldı — çapraz platform, opsiyonel.
  Üretimde bu işi Actions'ın her çalışmayı sıfırdan başlatması üstlenir.)

## Testler
```
$ .venv/Scripts/python.exe -m pytest -q
...............................   31 passed
```
Yeni: `tests/test_indicators.py` (9) — reel faiz/DXY/GMA/GLD/mevduat etiketleme + uzlaşı
(veri-yok paydadan çıkarma, yön eşiği).

## Dağıtım (F)
`deploy/` systemd birimleri: collector, bot, **evds.timer (15:30 UTC)**, report.timer (15:45 UTC =
18:45 TR), backup.timer (opsiyonel). Shape planı: **Ampere A1 (ARM64)**, kapasite yoksa
**AMD E2.1.Micro**. "VM gelince taşınma" adımları README'de (repo + DB kopyası + systemd).

## Bilinen eksikler / v2'ye kalanlar
- **SPDR GLD tonaj CSV** ayrıştırılamadı (URL güncel format vermedi) → gösterge "veri yok",
  uzlaşı paydasından çıkıyor (tasarım gereği). v2: doğru GLD kaynağı.
- 1 hafta repo saf serisi yok → AOFM proxy (yeterli).
- 7/24 çalıştırma sonraki fazda GitHub Actions'a verildi.
- Sinyal/bildirim motoru, backtest, AI katmanı: v2/v3 (bkz. PROJE-REHBERI backlog).

## Tekrar üretmek
```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m src.evds_job backfill      # 7531 satır
.venv/Scripts/python.exe -m src.evds_job context       # makro bağlam
.venv/Scripts/python.exe -m src.report                 # rapor + Telegram
```
