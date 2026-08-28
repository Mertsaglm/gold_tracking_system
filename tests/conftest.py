"""Paylaşılan test altyapısı — regresyon zırhının temeli.

Bu dosya YENİ bir kural getirmez; var olan testlerin tekrar tekrar yazdığı üç
şeyi tek yere toplar:

1. **İzole kök** (`izole_kok`): `util.ROOT`'u `tmp_path`'e çeker. Projede
   bazı yollar config'ten gelir (`paths.db`, `reports_dir`) ama bazıları KODA
   GÖMÜLÜ ve config'i hiç sormaz — `data/archive`, `data/gram_engeli.json`,
   `logs/`. Yalnız config'i değiştiren bir test gerçek repoya yazabilir.
   `ROOT`'u çekmek hepsini birden izole eder.
2. **Sentetik DB** (`sentetik_db`): gerçekçi ama tamamen üretilmiş bir veri
   tabanı. Testler ASLA `data/altin.sqlite`'a dokunmaz.
3. **Ağ kapısı** (`ag_kapali`): soket seviyesinde ağı kapatır. "Bu kod yolu
   ağa çıkmamalı" iddiası ancak böyle KANITLANIR; mock'lamak yalnız bilinen
   çağrıları yakalar, yenisini yakalamaz.

Neden bu kadar önemli: bu repo bilinçli olarak araç-bağımsız (ADR #001/#002) ve
ileride daha zayıf modellerle geliştirilecek. Testler o modellerin yapabileceği
en yaygın hasarı — "sessizce çalışan ama artık doğru olmayan kod" — yakalamak
için var.
"""
from __future__ import annotations

import copy
import json
import socket
import ssl  # noqa: F401 — ağ kapatılmadan ÖNCE yüklenmeli (bkz. ag_kapali)
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src import util

KOK = Path(__file__).resolve().parent.parent
CFG_GERCEK = util.load_config()

# Ağ çekicileri: "bu fonksiyon ağa çıkar" listesi. İzole testlerde hepsi
# susturulur. Yeni bir ağ çekicisi eklenirse buraya da eklenmeli —
# `test_ag_izolasyonu.py` bu listenin eksiksizliğini ayrıca denetler.
AG_CEKICILERI = (
    ("src.indicators", "_fred_csv"),
    ("src.indicators", "_yf_series"),
    ("src.indicators", "gld_tonnes_now"),
    ("src.indicators", "ons_gma_signal"),
    ("src.trends", "fetch_interest_df"),
    ("src.history", "_yf_ons_daily"),
    ("src.ohlc_hist", "_yf_daily_ohlc"),
)


# ---------------------------------------------------------------- config
def cfg_kopya(**ustyaz) -> dict:
    """Gerçek `config.yaml`'ın derin kopyası — testler kaynağı bozmasın.

    Gerçek config kullanılır (sahte bir sözlük değil): eşiklerin gerçek
    değerleriyle test etmek, config ile kod arasındaki sözleşmeyi de sınar.
    """
    c = copy.deepcopy(CFG_GERCEK)
    for yol, deger in ustyaz.items():
        parcalar = yol.split(".")
        d = c
        for p in parcalar[:-1]:
            d = d.setdefault(p, {})
        d[parcalar[-1]] = deger
    return c


@pytest.fixture
def izole_kok(tmp_path, monkeypatch):
    """`util.ROOT` → tmp_path. Koda gömülü yollar da dahil her şey izole.

    Döner: (cfg, tmp_path). cfg'de telegram kapalı, grafik kapalı — testler
    dışarıya tek bayt göndermez.
    """
    (tmp_path / "data" / "archive").mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    # MarketCalendar tatil dosyasını `paths.holidays_file` üzerinden okur ve
    # abspath ile çözer → izole kökte de bulunmalı.
    for ad in ("holidays_tr.yaml", "config.yaml"):
        (tmp_path / ad).write_text((KOK / ad).read_text(encoding="utf-8"),
                                   encoding="utf-8")
    monkeypatch.setattr(util, "ROOT", tmp_path)
    cfg = cfg_kopya(**{"telegram.enabled": False,
                       "chart.gorsel.gunluk_gonder": False})
    return cfg, tmp_path


# ---------------------------------------------------------------- ağ
class AgKapaliHatasi(RuntimeError):
    pass


@pytest.fixture
def ag_kapali(monkeypatch):
    """Bağlantı kurmayı kapatır: bu fixture'ı alan test ağa ÇIKAMAZ.

    `socket.socket` SINIFI değiştirilmiyor, yalnız bağlantı kuran metotları:
    sınıfı bir fonksiyonla değiştirmek, o an henüz import edilmemiş `ssl`
    modülünün `class SSLSocket(socket)` satırını patlatıyor (gerçek bir
    tuzak — hata ağ değil import hatası olarak görünür ve teşhisi yanıltır).

    DNS de kapatılır: adres çözemeyen bir çağrı zaten ağa çıkmaya çalışmıştır.
    """
    def _yasak(*a, **k):
        raise AgKapaliHatasi("test ağa çıkmaya çalıştı")

    monkeypatch.setattr(socket.socket, "connect", _yasak)
    monkeypatch.setattr(socket.socket, "connect_ex", _yasak)
    monkeypatch.setattr(socket, "create_connection", _yasak)
    monkeypatch.setattr(socket, "getaddrinfo", _yasak)
    return _yasak


# Üretimin gerçek anı: Perşembe 15:35 UTC = 18:35 TR (daily.yml cron'u).
# Perşembe seçilmesi kasıtlı: Pazartesi (mutabakat) ve Pazar (haftalık rapor)
# özel dallar; uçtan uca test SIRADAN bir iş günü koşumunu ölçsün.
SABIT_AN = datetime(2026, 7, 23, 15, 35, tzinfo=timezone.utc)


@pytest.fixture
def sabit_zaman(monkeypatch):
    """`util.utcnow`'u sabitler → `local_today`, asof kapısı ve rapor başlığı
    deterministik olur. Tüm modüller `util.utcnow()` üzerinden okuduğu için tek
    yamalama yeterli (doğrudan `datetime.now` çağıran kod yalnız `archive_fetch`
    ve `trends`; ikisi de bu testlerde devrede değil)."""
    monkeypatch.setattr(util, "utcnow", lambda: SABIT_AN)
    return SABIT_AN


@pytest.fixture
def ag_susturuldu(monkeypatch):
    """Ağ çekicilerini "veri yok" dönecek şekilde susturur (çökmeden).

    Ağı kapatmak yeterli olmaz: `_fred_csv` başarısızlıkta `time.sleep` ile
    yeniden dener; testin 4 saniye beklemesi gereksiz.
    """
    from src import indicators, trends

    monkeypatch.setattr(indicators, "_fred_csv", lambda *a, **k: None)
    monkeypatch.setattr(indicators, "_yf_series", lambda *a, **k: None)
    monkeypatch.setattr(indicators, "gld_tonnes_now", lambda *a, **k: None)
    monkeypatch.setattr(
        indicators, "ons_gma_signal",
        lambda cfg: indicators.Signal("Ons 50/200 GMA", indicators.YOK, "test"))
    monkeypatch.setattr(trends, "fetch_interest_df", lambda cfg: (None, None))


# ---------------------------------------------------------------- veri
def is_gunleri(n: int, bitis: date | None = None) -> list[str]:
    """`bitis`te (dahil değil) biten n adet ISO iş günü — hafta sonu YOK.

    Hafta sonu üretilmez: `ohlc_daily`'de meşru hafta sonu barı yoktur
    (ADR #008-G, 5401 barın 0'ı) ve `prim_history` hafta sonunu geçersiz
    sayar. Sentetik veri üretimin kuralına uymalı, yoksa test gerçeği
    değil kendi kurgusunu doğrular.
    """
    bitis = bitis or date.fromisoformat(util.local_today())
    out, g = [], bitis - timedelta(days=1)
    while len(out) < n:
        if g.weekday() < 5:
            out.append(g.isoformat())
        g -= timedelta(days=1)
    return sorted(out)


def sentetik_db(cfg: dict, gun: int = 400, prim_gun: int = 0,
                prim_ornek: int = 3, tarihler: list[str] | None = None):
    """Gerçekçi sentetik DB kurar ve (con, tarihler) döner.

    Seri kurgusu ölçüme uygun seçildi: gram TL yukarı sürüklenir (TL değer
    kaybı), kur sürünür — üretimdeki rejimin aynısı (ADR #007-G). `gram_teorik`
    DAİMA `calc.theoretical_gram`'dan üretilir; elle uydurulmuş bir gram
    değeri, veri bütünlüğü testlerini kendi hatasıyla doğrulardı.
    """
    from src import calc, db

    troy = cfg["instruments"]["troy_ounce_gram"]
    ons_sym = cfg["chart"]["ohlc"]["symbols"]["ons"]
    kur_sym = cfg["chart"]["ohlc"]["symbols"]["kur"]
    ev = cfg["sources"]["evds"]["series"]
    tarihler = tarihler or is_gunleri(gun)
    con = db.connect(cfg)
    for i, d in enumerate(tarihler):
        ons = 2000.0 * (1.0004 ** i)
        kur = 30.0 * (1.0008 ** i)
        con.execute("INSERT OR REPLACE INTO history_daily("
                    "date,ons_usd,usdtry,gram_teorik,ons_source) VALUES(?,?,?,?,?)",
                    (d, ons, kur, calc.theoretical_gram(ons, kur, troy), "test"))
        for sym, p in ((ons_sym, ons), (kur_sym, kur)):
            con.execute("INSERT OR REPLACE INTO ohlc_daily("
                        "date,symbol,o,h,l,c,v,source) VALUES(?,?,?,?,?,?,?,?)",
                        (d, sym, p, p * 1.004, p * 0.996, p, 0.0, "test"))
        con.execute("INSERT OR REPLACE INTO evds_daily(date,series_code,value) "
                    "VALUES(?,?,?)", (d, ev["usdtry_sell"], kur))
        if i % 21 == 0:
            for kod, v in ((ev["mevduat_3ay"], 45.0), (ev["mevduat_1yil"], 47.0),
                           (ev["aofm_politika"], 40.0), (ev["enf_bek_12ay"], 24.0)):
                con.execute("INSERT OR REPLACE INTO evds_daily("
                            "date,series_code,value) VALUES(?,?,?)", (d, kod, v))
    # prim arşivi (canlı 15 dk toplayıcının izdüşümü).
    # Prim GÜNDEN GÜNE değişmeli: sabit prim serisinde std=0 olur ve z-skor
    # "flat" döner — testler kodun hatasını değil fixture'ın düzlüğünü ölçer.
    for gi, d in enumerate(tarihler[-prim_gun:] if prim_gun else []):
        for k in range(prim_ornek):
            ts = f"{d}T{9 + k * 3:02d}:00:00+00:00"
            theo = con.execute("SELECT gram_teorik FROM history_daily WHERE date=?",
                               (d,)).fetchone()["gram_teorik"]
            gun_sapmasi = ((gi * 7919) % 23 - 11) / 11_000.0     # ±%0.1, deterministik
            piyasa = theo * (1 + 0.004 + 0.0004 * k + gun_sapmasi)
            db.insert_prim(con, ts_utc=ts, ons_usd=1.0, usdtry=1.0,
                           theoretical=theo, market_has=piyasa,
                           gram_retail=piyasa * 1.005,
                           prim_pct=calc.prim_pct(piyasa, theo),
                           prim_pct_naive=calc.prim_pct(piyasa * 1.005, theo),
                           spread_pct=0.02 + 0.001 * k,
                           quarter_prim_pct=1.2 + 0.05 * k,
                           indicative=0, weekend=0, holiday=0, reason="test")
    con.commit()
    return con, tarihler


def yaz_engel_onbellegi(cfg: dict, taban_pct: float = -1.99) -> dict:
    """`data/gram_engeli.json` önbelleğini ÜRETİCİDEN türeterek yazar.

    Elle sözlük yazmak L-012'nin ta kendisi olurdu: fixture üreticiden sapar,
    ona dayanan testler yeşil kalarak gerçekliğini kaybeder. Bu yüzden şekil
    `gram.engel_ozet`'ten geliyor.
    """
    from src import gram

    ham = {"ilk": "2016-01-04", "son": "2026-07-24", "n_gun": 2561, "ufuklar": {}}
    for ad, h in cfg["karar"]["ufuklar_gun"].items():
        ham["ufuklar"][ad] = {
            "gun": h, "n_bagimsiz": 121, "ortalama": taban_pct,
            "kazanma_pct": 36.0, "maliyet_sonrasi_kazanma_pct": 28.0,
            "en_kotu": -36.2, "yeterli": True}
    ozet = gram.engel_ozet(cfg, ham)
    util.write_json(util.abspath(gram.ENGEL_CACHE), ozet)
    return ozet


def arsiv_csv_yaz(kok: Path, satir_sayisi: int = 5) -> Path:
    """Sentetik arşiv CSV'si — `import_actions` ve `notify` bunu okur."""
    from src.archive_fetch import FIELDS

    gun = date.fromisoformat(util.local_today()) - timedelta(days=1)
    while gun.weekday() >= 5:                    # hafta içi olmalı (indicative=0)
        gun -= timedelta(days=1)
    yol = kok / "data" / "archive" / f"{gun.strftime('%Y-%m')}.csv"
    yol.parent.mkdir(parents=True, exist_ok=True)
    with open(yol, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(FIELDS) + "\n")
        for i in range(satir_sayisi):
            ons, kur = 4000.0 + i, 47.0
            teorik = ons / 31.1034768 * kur
            # Prim gün içinde OYNAMALI. Eskiden sabit çarpandı (teorik × 1.0045)
            # ve bu, piyasa bacağının teorik bacaktan TÜRETİLDİĞİ bir seri
            # üretiyordu — yani ölçülmesi imkânsız bir prim. Bağımsızlık
            # nöbetçisi (denetim 2026-08-28) bunu haklı olarak yakaladı.
            # Sentetik veri rejimsizse koruma testleri vacuous geçer
            # (AGENTS.md §5): gerçek arşivde gün-içi CV 3e-04…6e-03.
            p = 1.004 + 0.0005 * (i % 3)        # %0.40 … %0.50 arası salınım
            f.write(",".join([
                f"{gun.isoformat()}T{10 + i:02d}:15:00+00:00",
                f"{ons}", f"{kur}",
                f"{teorik * (p + 0.002):.2f}", f"{teorik * (p + 0.0025):.2f}",
                f"{teorik * p:.2f}", f"{teorik * (p + 0.0005):.2f}",
                f"{teorik * 1.804 * 0.916 * 1.02:.2f}",
                f"{teorik * 1.804 * 0.916 * 1.025:.2f}",
                f"{kur - 0.01}", f"{kur}"]) + "\n")
    return yol


def kaynak(modul) -> str:
    """Bir modülün kaynak metni — yapısal (AST/metin) denetimler için."""
    import inspect
    return inspect.getsource(modul)


def jsonl_oku(yol: Path) -> list[dict]:
    return [json.loads(s) for s in yol.read_text(encoding="utf-8").splitlines() if s]
