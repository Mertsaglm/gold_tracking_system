"""daily_job hata görünürlüğü — sessiz başarı bu projede somut bir risk.

ADR #004: `history_daily` 17 gün donuk kaldı ve HİÇBİR alarm çıkmadı. Aynı zemin
daily_job'da da vardı: altı adımın hepsi `except → log.warning` ile yutuluyor,
`logs/` gitignore'da olduğu için uyarı commit'lenmiyor, süreç daima 0 ile
çıkıyordu → Actions günlerce YEŞİL kalabilirdi.
"""
from src import daily_job


def test_hata_tek_yola_yazilir():
    r = {}
    daily_job._hata(r, "import", ValueError("csv yok"))
    assert r["hatalar"] == {"import": "csv yok"}


def test_kritik_adim_patlarsa_basarisiz():
    for adim in daily_job.KRITIK_ADIMLAR:
        assert daily_job.basarisiz_mi({"hatalar": {adim: "x"}}) == [adim]


def test_kritik_olmayan_adim_isi_dusurmez():
    """EVDS/OHLC/grafik bir gün atlanabilir; rapor yine anlamlıdır."""
    r = {"hatalar": {"evds": "timeout", "ohlc": "yf", "grafik": "matplotlib yok",
                     "zskor_prova": "x", "history": "y", "tahmin": "z",
                     "mutabakat": "w"}}
    assert daily_job.basarisiz_mi(r) == []


def test_hatasiz_kosum_basarili():
    assert daily_job.basarisiz_mi({"tarih": "2026-07-27"}) == []


def test_rapor_ve_import_kritik_listede():
    """Bu iki adım kritik olmaktan çıkarılırsa sessiz bozulma geri gelir."""
    assert set(daily_job.KRITIK_ADIMLAR) == {"import", "rapor"}
