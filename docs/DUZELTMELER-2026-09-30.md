# Yerel yayın hazırlığı — 2026-09-30

25 Eylül yeni hesap/aday revizyonu üretimde henüz yok. Mevcut yerel değişiklikler
korunarak ortak çekirdek BIST ile eşitlendi; 33 modül hash'i aynı. Commit/push/deploy
yapılmadı, üretim defterine veya SQL'e yazılmadı, bildirim gönderilmedi.

- Aktif/eski/aday hesabı okuyan audit düzeltildi; ücret borcu bağımsız hesaplanır.
- SQL yazan daily/archive/portfolio işleri `repo-commit` + `queue: max` kullanır;
  iptal kapalıdır, kuyruktan çıkan iş güncel `main` dalını alır. Varsayılan tek
  bekleyen kuyruğun günlük işi ezmesi bu nedenle geri gelmez.
- Kaynak telafisi hatası çevrim/kalıcı kayıt sonrasında workflow'u başarısız yapar;
  kurtarma artifact'i hem advisor verisini hem SQL'i içerir.
- requests/curl_cffi ağ yasağı uygulamanın yakalayamayacağı pytest ihlalidir.
  Bu koruma altın panel testindeki mock'suz Google Trends çağrısını yakaladı.
- Ortak kapanış düzeltmesi gece yarısından sonra son tamamlanan seansı kullanır.

2026-09-30: testlerde 998 geçti/8 atlandı; panelde 10 geçti. Güncel sayı için
`.venv/bin/python -m pytest -q -rs` ve `npm --prefix dashboard test` çalıştırılır.
Üretimin sabit arşiv kopyasında yeni 50.000 TL hesap/dört aday, iki offline çevrim,
eski defter hash korunumu, muhasebe, model refit ve yedekten dönüş doğrulandı.
Kanıt: `reports/duzeltmeler-2026-09-30/gold-integration.json` ve aynı dizindeki
`gold-fixed-audit.json`, `tests.log`. Deney, gerçek emir veya canlı başarı değildir.

Yayın kapsamı yalnız bu son dosyalar değil, bekleyen 25 Eylül revizyonunun tamamıdır.
AGENTS.md §10 gereği commit/push için açık yetki beklenir. Yayından sonra güncel
veri, yeni hesap/sürüm ve eski defter eşliği kontrol edilir. Dış scheduler ayarı,
gerçek gözlem ritmi ve alıcıya Telegram teslimi bu yerel testlerle kanıtlanmaz.
Kuyruk kaynağı (2026-09-30):
https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
