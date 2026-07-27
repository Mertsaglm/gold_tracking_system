"""FRED önbelleği — başarısızlığı da tutmalı.

Bu testleri doğuran ölçüm: `_FRED_CACHE` yalnız BAŞARIYI tutuyordu. FRED
2026-07-07'den beri üretimde hiç yanıt vermiyor (ADR #006), ve seriyi aynı
süreç içinde 3 ayrı tüketici çağırıyor (report.py'nin paneli, signals.py'nin
kadran_uzlasisi'i, backtest._fred_aligned'ın rejim etiketleyicisi). Önbellek
başarısızlığı tutmadığı için üçü de bağımsız 15sn×2 deneme ödüyordu.

Uçtan uca gerçek `daily_job.run()` koşusuyla ölçüldü (2026-07-26,
Telegram kapalı): düzeltme öncesi 165.9s, sonrası 70.1s — kalan süre tek bir
DFII10+DTWEXBGS çiftinin (ilk tüketicinin) ilk kez ödediği bedel.

Ağa çıkmaz: `requests.get` monkeypatch'li.
"""
import pytest

from src import indicators as ind, util

CFG = util.load_config()


@pytest.fixture(autouse=True)
def _temiz_cache(monkeypatch):
    """Her test kendi önbelleğiyle başlasın; retry backoff'u gerçekten uyumasın."""
    ind._FRED_CACHE.clear()
    monkeypatch.setattr(ind.time, "sleep", lambda *_a, **_k: None)
    yield
    ind._FRED_CACHE.clear()


def _zaman_asimi(*_a, **_k):
    import requests
    raise requests.exceptions.Timeout("test: FRED ölü")


def test_basarisizlik_onbelleklenir_ikinci_cagri_agi_denemez(monkeypatch):
    """KİLİT TEST. İlk çağrı başarısız olur (2 deneme). İkinci çağrı — AYNI
    süreçte, farklı bir tüketiciymiş gibi — ağa HİÇ çıkmamalı."""
    cagri_sayaci = {"n": 0}

    def sayan_zaman_asimi(*_a, **_k):
        cagri_sayaci["n"] += 1
        raise __import__("requests").exceptions.Timeout("test: FRED ölü")

    monkeypatch.setattr("src.indicators.requests.get", sayan_zaman_asimi)
    monkeypatch.setitem(CFG["indicators"], "fred_retry", 1)   # 2 deneme

    r1 = ind._fred_csv(CFG, "DFII10")
    ilk_deneme_sayisi = cagri_sayaci["n"]
    assert r1 is None
    assert ilk_deneme_sayisi == 2                # config: retry=1 → 2 deneme

    r2 = ind._fred_csv(CFG, "DFII10")             # İKİNCİ tüketici, aynı süreç
    assert r2 is None
    assert cagri_sayaci["n"] == ilk_deneme_sayisi, (
        "önbellek başarısızlığı tutmuyor — ikinci çağrı ağa tekrar çıktı")


def test_farkli_seri_ayri_onbelleklenir(monkeypatch):
    """DFII10'un ölü olması DTWEXBGS'in de denenmeyeceği anlamına gelmez —
    önbellek seri bazında, global bir 'FRED öldü' bayrağı değil."""
    cagrilar = []

    def kaydeden(url, **_k):
        cagrilar.append(url)
        raise __import__("requests").exceptions.Timeout("test")

    monkeypatch.setattr("src.indicators.requests.get", kaydeden)
    monkeypatch.setitem(CFG["indicators"], "fred_retry", 0)   # 1 deneme

    ind._fred_csv(CFG, "DFII10")
    ind._fred_csv(CFG, "DTWEXBGS")
    assert len(cagrilar) == 2                     # iki farklı seri, iki deneme
    ind._fred_csv(CFG, "DFII10")
    ind._fred_csv(CFG, "DTWEXBGS")
    assert len(cagrilar) == 2                     # üçüncü/dördüncü çağrı önbellekten


def test_basari_da_onbelleklenmeye_devam_eder(monkeypatch):
    """Regresyon koruması: bu düzeltme başarı önbelleğini bozmamalı."""
    cagri_sayaci = {"n": 0}

    class SahteYanit:
        text = "DATE,VALUE\n2026-01-01,1.23\n2026-01-02,1.45\n"
        def raise_for_status(self): pass

    def basarili(*_a, **_k):
        cagri_sayaci["n"] += 1
        return SahteYanit()

    monkeypatch.setattr("src.indicators.requests.get", basarili)
    r1 = ind._fred_csv(CFG, "DFII10")
    r2 = ind._fred_csv(CFG, "DFII10")
    assert r1 == r2 == [("2026-01-01", 1.23), ("2026-01-02", 1.45)]
    assert cagri_sayaci["n"] == 1                 # ikinci çağrı ağa çıkmadı


def test_bos_yanit_basarisizlik_sayilir_ve_onbelleklenir(monkeypatch):
    """Boş CSV (yalnız başlık) de 'başarısız' sayılmalı — None döner ve
    önbelleğe düşer, sürekli aynı boş yanıtı tekrar tekrar parse etmesin."""
    cagri_sayaci = {"n": 0}

    class BosYanit:
        text = "DATE,VALUE\n"
        def raise_for_status(self): pass

    def bos(*_a, **_k):
        cagri_sayaci["n"] += 1
        return BosYanit()

    monkeypatch.setattr("src.indicators.requests.get", bos)
    assert ind._fred_csv(CFG, "DFII10") is None
    assert ind._fred_csv(CFG, "DFII10") is None
    assert cagri_sayaci["n"] == 1
