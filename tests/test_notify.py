"""Bildirim motoru saf çekirdek testleri: eşik değerlendirme + soğuma/tavan."""
from src import notify, util

CFG = util.load_config()


def _ctx(**kw):
    base = {"all_fresh": True, "prim": 0.0, "prim_z": None, "spread": None,
            "spread_p90": None, "daily_move": None, "atr": None, "quarter_z": None}
    base.update(kw)
    return base


def test_prim_threshold_fires():
    al = notify.evaluate_thresholds(_ctx(prim=2.0), CFG)
    assert any(a["tip"] == "prim_sapma" for a in al)


def test_prim_within_band_no_fire():
    al = notify.evaluate_thresholds(_ctx(prim=0.5), CFG)
    assert not any(a["tip"] == "prim_sapma" for a in al)


def test_zscore_threshold():
    al = notify.evaluate_thresholds(_ctx(prim_z=2.5), CFG)
    assert any(a["tip"] == "prim_z" for a in al)


def test_spread_p90():
    al = notify.evaluate_thresholds(_ctx(spread=0.5, spread_p90=0.3), CFG)
    assert any(a["tip"] == "makas" for a in al)


def test_daily_move_atr():
    al = notify.evaluate_thresholds(_ctx(daily_move=100, atr=40), CFG)  # 100 > 2*40
    assert any(a["tip"] == "gunluk_hareket" for a in al)


def test_weekend_suppresses_anomaly():
    # üç bacak FRESH değil -> anomali bildirimi yok
    al = notify.evaluate_thresholds(_ctx(all_fresh=False, prim=5.0, prim_z=9.0), CFG)
    assert al == []


def test_each_alert_has_triple():
    al = notify.evaluate_thresholds(_ctx(prim=2.0), CFG)[0]
    assert al["kural"] and al["gerekce"] and al["gecersizlik"]


# ---------- soğuma / tavan ----------
def test_cooldown_blocks_repeat():
    alerts = [{"tip": "prim_sapma", "kural": "k", "deger": 2, "gerekce": "g", "gecersizlik": "x"}]
    # 1 saat önce gönderilmiş, soğuma 24s -> engellenir
    state = {"last_sent": {"prim_sapma": "2026-07-07T10:00:00+00:00"}, "daily": {}}
    to_send, _ = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 6)
    assert to_send == []


def test_cooldown_allows_after_window():
    alerts = [{"tip": "prim_sapma", "kural": "k", "deger": 2, "gerekce": "g", "gecersizlik": "x"}]
    state = {"last_sent": {"prim_sapma": "2026-07-06T10:00:00+00:00"}, "daily": {}}
    # 25 saat sonra -> geçer
    to_send, ns = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 6)
    assert len(to_send) == 1
    assert ns["last_sent"]["prim_sapma"] == "2026-07-07T11:00:00+00:00"


def test_daily_cap():
    alerts = [{"tip": f"t{i}", "kural": "k", "deger": 1, "gerekce": "g", "gecersizlik": "x"}
              for i in range(10)]
    state = {"last_sent": {}, "daily": {}}
    to_send, ns = notify.apply_cooldown(alerts, state, "2026-07-07T11:00:00+00:00", 24, 3)
    assert len(to_send) == 3            # tavan
    assert ns["daily"]["2026-07-07"] == 3


# ---------- ATR / günlük hareket referansı: BUGÜN dışlanmalı ----------
def _db_ile_history(tmp_path, satirlar):
    import copy

    from src import db
    c = copy.deepcopy(CFG)
    c["paths"]["db"] = str(tmp_path / "t.sqlite")
    c["paths"]["db_dump"] = str(tmp_path / "t.sql")
    con = db.connect(c)
    for d, fiyat in satirlar:
        con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                    "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, 4000.0, 47.0, fiyat, "test"))
    con.commit()
    return c, con


def test_atr_bugunun_yarim_barini_saymaz(tmp_path):
    """`update_recent` hafta içi bugünün YARIM barını da yazıyor; ATR onu saymamalı.

    Yarım bar hem ATR'yi bozar hem gün içinde her koşumda değiştirir → eşik
    kayan hedefe döner.
    """
    from datetime import date, timedelta
    bugun = util.local_today()
    b = date.fromisoformat(bugun)
    # 20 kapanmış gün: her gün +10₺ → ATR ≈ 10
    satirlar = [((b - timedelta(days=20 - i)).isoformat(), 6000.0 + 10 * i)
                for i in range(20)]
    c, con = _db_ile_history(tmp_path, satirlar)
    atr_temiz = notify._atr_from_history(con)
    # şimdi bugünün YARIM barı gelsin — uçuk bir sıçramayla
    con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                (bugun, 4000.0, 47.0, 9999.0, "yarim"))
    con.commit()
    assert notify._atr_from_history(con) == atr_temiz, "yarım bar ATR'ye sızdı"
    con.close()


def test_gunluk_hareket_bugunun_kendi_kapanisiyla_karsilastirmaz(tmp_path):
    """Rapor koştuktan sonra alarm fiyatı KENDİSİYLE karşılaştırıp ~0 buluyordu."""
    from datetime import date, timedelta
    bugun = util.local_today()
    b = date.fromisoformat(bugun)
    satirlar = [((b - timedelta(days=20 - i)).isoformat(), 6000.0 + 10 * i)
                for i in range(20)]
    c, con = _db_ile_history(tmp_path, satirlar)
    dun_kapanis = satirlar[-1][1]
    # bugünün yarım barı, güncel fiyata ÇOK yakın yazılıyor (gerçek durum)
    guncel = 6300.0
    con.execute("INSERT OR REPLACE INTO history_daily(date,ons_usd,usdtry,"
                "gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                (bugun, 4000.0, 47.0, guncel, "yarim"))
    con.commit()
    row = con.execute("SELECT gram_teorik FROM history_daily WHERE date < ? "
                      "ORDER BY date DESC LIMIT 1", (bugun,)).fetchone()
    con.close()
    assert row["gram_teorik"] == dun_kapanis
    assert abs(guncel - row["gram_teorik"]) > 100, "referans dünkü kapanış olmalı"


# ---------- KİLİT TEST: Telegram HTML teslim sözleşmesi (L-018) ----------
# 2026-07-29 → 08-10 arası 13 gün, 125 Actions koşusu boyunca HİÇBİR anomali
# bildirimi gitmedi. Sebep: `prim_sapma`'nın geçersizlik metnindeki `(|%|<1.5)`
# Telegram'ın HTML ayrıştırıcısına etiket başlangıcı gibi geldi → 400 Bad Request.
# O gün 12 test vardı ve HEPSİ saf eşik fonksiyonlarına bakıyordu; hiçbiri
# `_format_alert`'ün ÜRETTİĞİ metni görmüyordu. Bu blok o boşluğu kapatır.
import re as _re

_ETIKET_RE = _re.compile(
    r"</?(?:%s)(?:\s[^<>]*)?>" % "|".join(notify.TG_HTML_ETIKETLERI))
_GECERLI_ENTITY = _re.compile(r"&(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);")


def tg_html_ihlalleri(s: str) -> list[str]:
    """Telegram parse_mode=HTML sözleşmesi: desteklenen etiketler DIŞINDA
    `<`, `>` ve çıplak `&` bulunamaz. Bulunursa API 400 döner ve mesaj HİÇ gitmez.
    """
    kalan = _GECERLI_ENTITY.sub("", _ETIKET_RE.sub("", s))
    ihlal = []
    if "<" in kalan:
        ihlal.append(f"kaçırılmamış '<' → {kalan[max(0, kalan.find('<') - 25):][:60]!r}")
    if ">" in kalan:
        ihlal.append(f"kaçırılmamış '>' → {kalan[max(0, kalan.find('>') - 25):][:60]!r}")
    if "&" in kalan:
        ihlal.append(f"çıplak '&' → {kalan[max(0, kalan.find('&') - 25):][:60]!r}")
    return ihlal


def _tum_bildirimler():
    """Her eşik kuralını AYNI ANDA tetikleyen bağlam — beşi de üretilmeli."""
    al = notify.evaluate_thresholds(
        _ctx(prim=2.5, prim_z=3.0, spread=0.5, spread_p90=0.3,
             daily_move=400, atr=40, quarter_z=3.5), CFG)
    tipler = {a["tip"] for a in al}
    beklenen = {"prim_sapma", "prim_z", "makas", "gunluk_hareket", "ceyrek_prim"}
    # Kurgu tetiklemiyorsa test "vacuous" geçerdi (L-016): önce tetiği doğrula.
    assert beklenen <= tipler, f"kurgu tüm kuralları tetiklemedi: {tipler}"
    return al


def test_her_bildirim_gecerli_telegram_html_uretir():
    """KİLİT: üretimdeki GERÇEK metinler Telegram HTML'i bozmamalı."""
    for al in _tum_bildirimler():
        msg = notify._format_alert(al)
        assert not tg_html_ihlalleri(msg), (
            f"{al['tip']} bildirimi Telegram'da 400 alır: {tg_html_ihlalleri(msg)}")


def test_prim_bildirimlerinin_kucuktur_isareti_kacirilir():
    """Hattı 13 gün kıran İKİ metnin nokta atışı testi."""
    for al in _tum_bildirimler():
        if al["tip"] not in ("prim_sapma", "prim_z"):
            continue
        msg = notify._format_alert(al)
        assert "&lt;" in msg, f"{al['tip']}: '<' kaçırılmamış — 400 gelir"
        assert not tg_html_ihlalleri(msg)


def test_kacis_gelecekteki_metinleri_de_korur():
    """Düzeltme metne değil MEKANİZMAYA yapıldı: uydurma bir eşik metni de güvenli."""
    al = {"tip": "uydurma", "kural": "a < b & c > d",
          "gerekce": "<script>alert(1)</script> & <b>kalın</b>",
          "gecersizlik": "x<y ve p&q"}
    msg = notify._format_alert(al)
    assert not tg_html_ihlalleri(msg)
    assert "<script>" not in msg


def test_bildirim_govdesi_hala_kalin_ve_italik_kullaniyor():
    """Kaçış her şeyi düz metne çevirmemeli — şablon etiketleri AYAKTA kalmalı."""
    al = _tum_bildirimler()[0]
    msg = notify._format_alert(al)
    assert msg.startswith("🔔 <b>") and "</b>" in msg
    assert "<i>Geçersizlik:" in msg and "</i>" in msg


# ---------- KİLİT TEST: tek hata partiyi öldürmemeli ----------
def test_bir_gonderim_patlarsa_digerleri_yine_gider():
    """`prim_sapma` sırada BİRİNCİ; patlayınca arkasındakiler de hiç denenmiyordu."""
    gonderilen = []

    def sahte_send(cfg, text, parse_mode=None):
        # Üretimdeki gerçek vaka: SADECE prim_sapma 400 alıyor (metninde `<` var).
        if "teorik değerden saptı" in text:
            raise RuntimeError("400 Client Error: Bad Request")
        gonderilen.append(text)
        return 1

    to_send = _tum_bildirimler()
    assert to_send[0]["tip"] == "prim_sapma", "prim_sapma sırada birinci olmalı"
    ok, hatalar = notify._gonder(CFG, to_send, sahte_send)
    assert [h["tip"] for h in hatalar] == ["prim_sapma"]
    assert ok == len(to_send) - 1, "prim_sapma'dan SONRAKİ bildirimler gitmeliydi"
    assert len(gonderilen) == ok
    # Kesintinin özü buydu: makas ve gunluk_hareket hiç denenmiyordu.
    assert any("Makas" in t for t in gonderilen)
    assert any("Günlük hareket" in t for t in gonderilen)


def test_basarisiz_bildirimin_damgasi_geri_alinir():
    """Damga geri alınmazsa 24s soğuma gönderilemeyen bildirimi bir daha DENEMEZ."""
    alerts = [{"tip": "prim_sapma", "kural": "k", "deger": 2,
               "gerekce": "g", "gecersizlik": "x"}]
    onceki = {"last_sent": {}, "daily": {}}
    to_send, yeni = notify.apply_cooldown(alerts, onceki, "2026-08-11T10:00:00+00:00", 24, 6)
    assert yeni["last_sent"]["prim_sapma"]           # damga atıldı
    geri = notify.damgayi_geri_al(onceki, yeni, ["prim_sapma"], "2026-08-11")
    assert "prim_sapma" not in geri["last_sent"], "damga geri alınmadı → 24s sessizlik"
    assert geri["daily"]["2026-08-11"] == 0, "tavan sayacı da geri alınmalı"
    # ve 1 dk sonra YENİDEN denenebilmeli
    tekrar, _ = notify.apply_cooldown(alerts, geri, "2026-08-11T10:01:00+00:00", 24, 6)
    assert len(tekrar) == 1, "geri alınan damga yeniden denemeyi engelledi"


def test_basarili_damga_geri_alinmaz():
    onceki = {"last_sent": {"makas": "2026-08-01T00:00:00+00:00"}, "daily": {}}
    yeni = {"last_sent": {"makas": "2026-08-11T10:00:00+00:00",
                          "prim_sapma": "2026-08-11T10:00:00+00:00"},
            "daily": {"2026-08-11": 2}}
    geri = notify.damgayi_geri_al(onceki, yeni, ["prim_sapma"], "2026-08-11")
    assert geri["last_sent"]["makas"] == "2026-08-11T10:00:00+00:00"
    assert "prim_sapma" not in geri["last_sent"]
    assert geri["daily"]["2026-08-11"] == 1


# ---------- KİLİT TEST: arıza GÖRÜNÜR olmalı ----------
def test_saglik_defteri_ardisik_hatayi_sayar():
    st = {}
    for i in range(1, 4):
        st = notify.saglik_guncelle(st, f"2026-08-1{i}T10:00:00+00:00", 1,
                                    [{"tip": "prim_sapma", "hata": "HTTPError: 400"}])
        assert st["saglik"]["ardisik_hata"] == i
    assert "400" in st["saglik"]["son_hata"]


def test_saglik_defteri_basarida_sifirlanir():
    st = notify.saglik_guncelle({}, "2026-08-11T10:00:00+00:00", 1,
                                [{"tip": "makas", "hata": "boom"}])
    assert st["saglik"]["ardisik_hata"] == 1
    st = notify.saglik_guncelle(st, "2026-08-11T11:00:00+00:00", 1, [])
    assert st["saglik"]["ardisik_hata"] == 0
    assert "son_hata" not in st["saglik"]
    assert st["saglik"]["son_basari_utc"]


def test_gonderilecek_yokken_saglik_bozulmaz():
    """Sessiz gün (tetik yok) 'iyileşme' sayılmamalı — açık arıza gizlenmesin."""
    st = notify.saglik_guncelle({}, "2026-08-11T10:00:00+00:00", 1,
                                [{"tip": "makas", "hata": "boom"}])
    st2 = notify.saglik_guncelle(st, "2026-08-11T11:00:00+00:00", 0, [])
    assert st2["saglik"]["ardisik_hata"] == 1, "tetik yokken arıza silinmemeli"


# ---------- ENTEGRASYON: run() hata alsa bile defteri YAZAR ----------
def test_run_gonderim_patlasa_bile_state_kaydeder(izole_kok, ag_kapali,
                                                  ag_susturuldu, monkeypatch):
    """KİLİT TEST — sessiz kesintinin ikinci mekanizması.

    Eski kodda istisna `_save_state`'e ulaşmadan dışarı çıkıyordu: arıza ne
    diske, ne repoya, ne rapora yazılıyordu. `continue-on-error: true` de
    Actions'ı yeşil bırakınca kesinti 13 gün görünmez kaldı.
    """
    from src import db as _db, telegram_bot
    cfg, kok = izole_kok
    con = _db.connect(cfg)
    con.execute("INSERT INTO prim_history(ts_utc,ons_usd,usdtry,theoretical,"
                "market_has,gram_retail,prim_pct,prim_pct_naive,spread_pct,"
                "quarter_prim_pct,indicative,weekend,holiday,reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,0,0,0,'')",
                (util.utcnow().isoformat(), 4000.0, 47.0, 6100.0, 5980.0,
                 6000.0, -2.5, -2.0, 0.02, -1.0))
    con.commit()
    con.close()

    def patlayan_send(cfg, text, parse_mode=None):
        raise RuntimeError("400 Client Error: Bad Request")
    monkeypatch.setattr(telegram_bot, "send_message", patlayan_send)

    sonuc = notify.run(cfg)                       # İSTİSNA FIRLATMAMALI
    assert sonuc["hatalar"], "hata yutulup görünmez olmuş"
    assert sonuc["gonderildi"] == 0

    st = util.read_json(cfg["alerts"]["state_file"], None)
    assert st is not None, "arıza defteri diske hiç yazılmadı"
    assert st["saglik"]["ardisik_hata"] >= 1
    assert "400" in st["saglik"]["son_hata"]
    # ve damga geri alındığı için bir sonraki koşum YENİDEN denemeli
    assert "prim_sapma" not in st.get("last_sent", {})

    # rapor bu defteri okuyup BAĞIRMALI
    from src import report
    assert "BİLDİRİM HATTI ARIZALI" in report.bildirim_hatti_satiri(cfg)


def test_run_basarili_gonderimde_defter_temiz(izole_kok, ag_kapali,
                                              ag_susturuldu, monkeypatch):
    from src import db as _db, telegram_bot
    cfg, kok = izole_kok
    con = _db.connect(cfg)
    con.execute("INSERT INTO prim_history(ts_utc,ons_usd,usdtry,theoretical,"
                "market_has,gram_retail,prim_pct,prim_pct_naive,spread_pct,"
                "quarter_prim_pct,indicative,weekend,holiday,reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,0,0,0,'')",
                (util.utcnow().isoformat(), 4000.0, 47.0, 6100.0, 5980.0,
                 6000.0, -2.5, -2.0, 0.02, -1.0))
    con.commit()
    con.close()
    monkeypatch.setattr(telegram_bot, "send_message", lambda *a, **k: 1)
    sonuc = notify.run(cfg)
    assert not sonuc["hatalar"] and sonuc["gonderildi"] >= 1
    st = util.read_json(cfg["alerts"]["state_file"], {})
    assert st["saglik"]["ardisik_hata"] == 0
    from src import report
    assert report.bildirim_hatti_satiri(cfg) == "", "sağlıklı hatta yanlış alarm"


def test_ariza_defteri_SESSIZ_KOSUMDA_SILINMEZ(izole_kok, ag_kapali,
                                               ag_susturuldu, monkeypatch):
    """KİLİT TEST — görünürlük katmanı kendi korumaya çalıştığı hataya kurban gitti.

    ÜRETİMDE yakalandı (2026-08-11): `apply_cooldown` state'i sıfırdan kuruyor
    ve `saglik` anahtarını düşürüyordu. Sonuç: hat kırıkken bir arıza kaydedilse
    bile, gönderilecek bildirim olmayan İLK sessiz koşumda (soğuma/tavan) kayıt
    siliniyor ve rapordaki "BİLDİRİM HATTI ARIZALI" uyarısı kendiliğinden
    kayboluyordu.

    Buradaki asıl ders L-018'in tekrarı: önceki testim (`saglik_guncelle`'yi
    doğrudan çağıran birim testi) GEÇİYORDU çünkü boru hattını hiç görmüyordu.
    Bu test `run()` üzerinden gider.
    """
    from src import db as _db, report, telegram_bot
    cfg, _ = izole_kok
    con = _db.connect(cfg)
    con.execute("INSERT INTO prim_history(ts_utc,ons_usd,usdtry,theoretical,"
                "market_has,gram_retail,prim_pct,prim_pct_naive,spread_pct,"
                "quarter_prim_pct,indicative,weekend,holiday,reason) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,0,0,0,'')",
                (util.utcnow().isoformat(), 4000.0, 47.0, 6100.0, 5980.0,
                 6000.0, -2.5, -2.0, 0.02, -1.0))
    con.commit()
    con.close()

    # 1) Gönderim patlar → arıza defteri dolar
    monkeypatch.setattr(telegram_bot, "send_message",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("400")))
    notify.run(cfg)
    st = util.read_json(cfg["alerts"]["state_file"], {})
    assert st["saglik"]["ardisik_hata"] >= 1
    assert "BİLDİRİM HATTI ARIZALI" in report.bildirim_hatti_satiri(cfg)

    # 2) Damga geri alındığı için bildirim yeniden denenir; bu kez HİÇ tetik
    #    olmayan bir koşum kur (prim bandın içinde) → gönderilecek bir şey yok.
    con = _db.connect(cfg)
    con.execute("UPDATE prim_history SET prim_pct = -0.2, spread_pct = 0.0")
    con.commit()
    con.close()
    sonuc = notify.run(cfg)
    assert sonuc["gonderildi"] == 0 and not sonuc["hatalar"], "kurgu sessiz olmalı"

    # 3) KİLİT: sessiz koşum arıza kaydını SİLMEMELİ
    st2 = util.read_json(cfg["alerts"]["state_file"], {})
    assert st2.get("saglik", {}).get("ardisik_hata", 0) >= 1, (
        "sessiz koşum arıza defterini sildi → rapordaki uyarı kaybolur")
    assert "BİLDİRİM HATTI ARIZALI" in report.bildirim_hatti_satiri(cfg)


def test_apply_cooldown_state_anahtarlarini_dusurmez():
    """`apply_cooldown` state'i sıfırdan kurmamalı — bilmediği alanları korumalı."""
    st = {"last_sent": {}, "daily": {}, "saglik": {"ardisik_hata": 7},
          "gelecekteki_alan": "korunmalı"}
    _, yeni = notify.apply_cooldown([], st, "2026-08-11T10:00:00+00:00", 24, 6)
    assert yeni["saglik"] == {"ardisik_hata": 7}
    assert yeni["gelecekteki_alan"] == "korunmalı"
