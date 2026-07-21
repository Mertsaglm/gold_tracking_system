# TESLIMAT — Faz 7: Z-Skor Kapısının Gün Tabanına Alınması + Doküman Sadeleştirme

Tarih: 2026-07-21 · **137/137 test** (135 → +2)

## Tek cümle
Z-skor kapısı tasarım niyetine (gün) hizalandı ve üretim ortamı GitHub Actions olarak
sabitlendiği için dokümanlar tek bir çalıştırma modeli anlatacak şekilde sadeleştirildi.

| Bölüm | Durum |
|---|---|
| A. Z-skor kapısı: kayıt → gün | ✅ `db.count_valid_prim_days()` + 5 kapı noktası |
| B. Kapı davranışı doğrulandı | ✅ 13/60 gün → `veri_bekliyor` |
| C. Doküman sadeleştirme | ✅ README, İZLEME, PROJE-REHBERI, TESLIMAT 1-6 |
| D. Testler | ✅ **137/137** |

---

## A — Z-skor kapısı gün sayar, kayıt değil

Prim z-skoru, sistemin kendi biriktirdiği veriye dayanan tek sinyalidir; Kapalıçarşı priminin
tarihsel dağılımı hazır satılmadığı için arşiv 7 Temmuz 2026'da sıfırdan başladı.

`config.yaml`'daki eşik baştan beri **gün** cinsinden tanımlıydı
(`zscore_min_samples: 60  # arşiv < 60 gün ise yetersiz veri`) ve haftalık rapor da bunu
`N/60 gün` diye yazıyordu. Kapıyı yoklayan kod ise `count_valid_prim()` ile **kayıt** sayıyordu.

**Neden gün doğru birim:** arşiv gün içinde ~10 örnek alır ve bu örnekler birbirinin tekrarıdır
(otokorelasyon). Kayıt saymak bağımsız gözlem sayısını olduğundan büyük gösterir; z-skorun
dağılım tabanı gün cinsindendir. Kayıt tabanlı kapıda ölçüm:

| Birim | Değer |
|---|---|
| Geçerli kayıt | 134 |
| Bu kayıtların kapsadığı farklı gün | **13** |
| Eşik | 60 |

Yani sinyal 60 günlük dağılım yerine 13 günlük bir ortalamadan sapma ölçüyordu.

**Yapılan:** `db.count_valid_prim_days()` eklendi — `COUNT(DISTINCT date(ts_utc))`, hafta sonu ve
`indicative` kayıtlar hariç. Kapıyı yoklayan beş nokta buna geçirildi:

| Dosya | Rol |
|---|---|
| `signals.py` | z-skor sinyali + `evaluate_alerts` prim_z bildirimi |
| `notify.py` | Actions bildirim eşiği |
| `report.py` | günlük "Veri Kalitesi" + haftalık "Arşiv İlerlemesi" |
| `aipaket.py` | AI veri paketi z-skor durumu |

Kayıt sayısı silinmedi; rapor artık ikisini birlikte yazar
(`Prim kaydı: 200 (geçerli: 134 · 13 gün)`) — hacim ile bağımsız gözlem ayrımı görünür kalır.

## B — Doğrulama

```
kayit: 134 | gun: 13 | esik: 60
-> veri_bekliyor | Canlı prim arşivi yetersiz (13/60 gün).
   Geçersizlik: Arşiv 60 güne ulaşınca z-skor sinyali devreye girer.
Rapor: - Z-skor: ⏳ arşiv birikiyor (13/60 gün)
AI paketi: {'durum': 'veri_bekliyor', 'mevcut_gun': 13, 'gereken_gun': 60}
```

Eşik dolduğunda z-skor sinyali ve `z > 2` bildirimi **kendiliğinden** devreye girer; kod hazır,
ek iş gerekmez. İlerleme haftalık pazar raporundaki "Arşiv İlerlemesi" satırından izlenir.

**Yeni testler (2):**
- `test_valid_prim_days_counts_days_not_records` — 3 gün × 10 kayıt → `count_valid_prim() == 30`
  ama `count_valid_prim_days() == 3`.
- `test_valid_prim_days_excludes_indicative_and_weekend` — `indicative=1` ve `weekend=1` kayıtlar
  gün sayımına girmez.

## C — Doküman sadeleştirme

Üretim ortamı GitHub Actions olarak sabitlendi. Dokümanlar iki paralel çalıştırma modeli
(Actions + ayrı sunucu) anlatmayı bırakıp tek modeli anlatıyor; okuyanın "hangisi geçerli"
sorusunu sorması gereken yer kalmadı.

| Dosya | Değişiklik |
|---|---|
| `README.md` | Yeniden yazıldı: Actions üretim ortamı olarak en başta, kurulum/taşıma bölümleri kaldırıldı, prim z-skoru için ayrı bölüm eklendi |
| `İZLEME.md` | Yeniden yazıldı: haftalık kontrol + cron ritmi + z-skor ilerlemesi + hafta sonu davranışı + veri konumları |
| `PROJE-REHBERI.md` | Z-skor notu gün tabanlı kapıyı anlatacak şekilde güncellendi; backlog Actions'a göre düzeltildi |
| `TESLIMAT.md` … `TESLIMAT-FAZ6.md` | Tek çalıştırma modeline göre ifade düzeltmeleri (tarihsel ölçümler ve hükümler değişmedi) |
| `config.yaml`, `src/*.py` | Yorum satırlarında zamanlayıcı referansları Actions olarak netleştirildi |

## Tekrar üretmek
```bash
git pull --rebase
.venv/bin/python -m src.restore_db
.venv/bin/python -m pytest -q                    # 137 test
.venv/bin/python -m src.signals                  # prim_zskoru → veri_bekliyor (N/60 gün)
.venv/bin/python -m src.report                   # "Z-skor: ⏳ arşiv birikiyor (N/60 gün)"
```
