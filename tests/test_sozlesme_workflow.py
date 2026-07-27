"""GitHub Actions workflow SÖZLEŞMESİ — üretim ortamı burada tanımlı.

Bu projede üretim bir sunucu değil, iki YAML dosyası: `archive.yml` (15 dk) ve
`daily.yml` (günlük). Yani **adım sırası kod kadar davranışsaldır** ve YAML'ı
hiçbir test okumuyorsa üretim sözleşmesi denetimsizdir.

Kilit sıra `daily.yml`'de:

    restore_db  →  daily_job  →  dbdump  →  commit

Bu sıranın her bağlantısı ölçülmüş bir olaya dayanıyor:

- `restore_db` ÖNCE olmalı: Actions stateless, sqlite gitignore'da. Restore
  atlanırsa iş BOŞ bir DB üzerinde koşar ve ardından o boş DB dump'lanıp
  commit'lenir → tüm geçmiş silinir.
- `dbdump` SONRA olmalı: L-009 tam bunun tersinden doğdu (dump eski sqlite'tan
  üretildi, 2890 tick geri sarıldı).
- `daily_job` adımında `continue-on-error` OLMAMALI: ADR #008 K-6, kritik adım
  patlarsa süreç `exit(1)` ile çıkıyor ve **sonraki adımlar (dump + commit)
  atlanıyor**. `continue-on-error: true` eklenirse bu koruma sessizce ölür ve
  yarım veri commit'lenir.
- `archive.yml` dump ÜRETMEZ: yalnız restore edip okur. Oraya bir `dbdump`
  adımı eklenirse 15 dakikada bir, yarım bağlamla üretilmiş dump commit'lenir.
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

from tests.conftest import KOK

WF = KOK / ".github" / "workflows"


def _yukle(ad: str) -> dict:
    return yaml.safe_load((WF / ad).read_text(encoding="utf-8"))


def _tetik(wf: dict) -> dict:
    """PyYAML `on:` anahtarını YAML 1.1 kuralıyla `True` boolean'ına çevirir."""
    return wf.get("on", wf.get(True, {}))


def _adimlar(wf: dict, is_adi: str) -> list[dict]:
    return wf["jobs"][is_adi]["steps"]


def _komutlar(adimlar: list[dict]) -> list[str]:
    return [a.get("run", "") for a in adimlar]


def _indeks(adimlar: list[dict], parca: str) -> int:
    """`parca` metnini içeren ilk adımın indeksi (-1 yoksa)."""
    for i, a in enumerate(adimlar):
        if parca in a.get("run", ""):
            return i
    return -1


GUNLUK = _yukle("daily.yml")
ARSIV = _yukle("archive.yml")
GUNLUK_ADIM = _adimlar(GUNLUK, "daily")
ARSIV_ADIM = _adimlar(ARSIV, "archive")


def test_workflow_dosyalari_yerinde():
    """Yanlış yerdeki doğru dosya = yok hükmünde (L-004 aynı ders)."""
    assert sorted(p.name for p in WF.glob("*.yml")) == ["archive.yml", "daily.yml"]


# ------------------------------------------------------------ daily.yml sırası
def test_gunluk_restore_isten_once():
    """KİLİT TEST. Restore atlanırsa iş boş DB'de koşar ve boş DB commit'lenir."""
    r = _indeks(GUNLUK_ADIM, "src.restore_db")
    j = _indeks(GUNLUK_ADIM, "src.daily_job")
    assert r >= 0, "daily.yml'de restore_db adımı YOK — DB her koşumda boş başlar"
    assert j >= 0, "daily.yml daily_job'u çağırmıyor"
    assert r < j, "restore_db, daily_job'dan SONRA → iş boş DB'de koşuyor"


def test_gunluk_dump_isten_sonra():
    """L-009: dump eski/yarım sqlite'tan üretilirse veri GERİYE sarılır."""
    j = _indeks(GUNLUK_ADIM, "src.daily_job")
    d = _indeks(GUNLUK_ADIM, "src.dbdump")
    assert d >= 0, "dbdump adımı YOK → o günün verisi commit'lenmez"
    assert j < d, "dbdump işten ÖNCE koşuyor → günün verisi dump'a girmez"


def test_gunluk_commit_dumptan_sonra_ve_data_ekliyor():
    """`git add data/` yoksa dump commit'lenmez → Actions stateless, veri ölür."""
    d = _indeks(GUNLUK_ADIM, "src.dbdump")
    c = _indeks(GUNLUK_ADIM, "git add")
    assert c > d >= 0, "commit adımı dump'tan önce"
    metin = GUNLUK_ADIM[c]["run"]
    assert "data/" in metin and "reports/" in metin


def test_gunluk_is_adimi_hatayi_yutmuyor():
    """KİLİT TEST (ADR #008 K-6).

    `daily_job` kritik adım patlarsa `sys.exit(1)` ediyor. Adıma
    `continue-on-error: true` eklenmesi bu korumayı sessizce iptal eder: iş
    yeşil kalır, dump+commit çalışır, yarım veri repoya girer.
    """
    for a in GUNLUK_ADIM:
        if "src.daily_job" in a.get("run", ""):
            assert not a.get("continue-on-error"), (
                "daily_job adımına continue-on-error eklenmiş → kritik adım "
                "koruması (exit 1) etkisiz")
            return
    pytest.fail("daily_job adımı bulunamadı")


def test_gunluk_dump_ve_commit_de_hatayi_yutmuyor():
    """Dump veya commit sessizce başarısız olursa gün kaybedilir ve fark
    edilmez (logs/ gitignore'da)."""
    for a in GUNLUK_ADIM:
        if "src.dbdump" in a.get("run", "") or "git add" in a.get("run", ""):
            assert not a.get("continue-on-error")


def test_gunluk_cron_kapanis_oncesi():
    """asof=T−1 gerekçesi cron saatine bağlı: iş 15:35 UTC'de koşuyor, CME altın
    ~21:00 UTC'de kapanıyor → o günün barı YARIM. Cron 21:00 sonrasına
    taşınırsa `ozellikler.son_kapali_gun`'un gerekçesi geçersizleşir ve bir gün
    veri boşuna beklenir; taşımak isteyen ADR yazmalı."""
    cron = _tetik(GUNLUK)["schedule"][0]["cron"]
    dakika, saat = cron.split()[0], int(cron.split()[1])
    assert saat < 21, f"cron {cron} → CME kapanışından sonra; asof gerekçesi değişir"
    assert dakika.isdigit()


def test_gunluk_requirements_kuruyor():
    """Görsel grafik (matplotlib) yalnız requirements.txt'te; `pip install
    matplotlib` elle yazılırsa requirements ile ayrışır."""
    assert any("-r requirements.txt" in k for k in _komutlar(GUNLUK_ADIM))


# ------------------------------------------------------------ archive.yml
def test_arsiv_cekim_bildirimden_once():
    """Bildirim, o turda çekilen TAZE CSV satırını okuyor (`notify._latest_csv_row`).
    Sıra ters olursa alarm bir tur eski veriyle değerlendirilir."""
    f = _indeks(ARSIV_ADIM, "src.archive_fetch")
    n = _indeks(ARSIV_ADIM, "src.notify")
    assert 0 <= f < n, "arşiv çekimi bildirimden sonra → alarm bayat veriyle koşar"


def test_arsiv_bildirim_hatasi_commiti_bloklamaz():
    """Telegram düşerse fiyat verisi YİNE arşivlenmeli — veri kaybı kabul edilemez,
    bildirim kaybı edilebilir."""
    for a in ARSIV_ADIM:
        if "src.notify" in a.get("run", ""):
            assert a.get("continue-on-error") is True, (
                "notify adımı continue-on-error değil → Telegram hatası CSV "
                "commit'ini engeller ve o turun fiyatı kaybolur")
            return
    pytest.fail("notify adımı bulunamadı")


def test_arsiv_dump_URETMEZ():
    """KİLİT TEST (L-009 zırhı).

    `archive.yml` DB'yi yalnız OKUR (bildirim bağlamı için restore eder).
    Buraya bir `dbdump` adımı eklenirse 15 dakikada bir, günlük işin henüz
    yazmadığı yarım bir DB dump'lanıp commit'lenir — L-009'un otomatikleşmiş
    hâli.
    """
    assert _indeks(ARSIV_ADIM, "src.dbdump") < 0, (
        "archive.yml dump üretiyor → 15 dk'da bir yarım DB commit'lenir (L-009)")


def test_arsiv_commit_csv_ve_alarm_durumunu_ekliyor():
    """Alarm durumu (soğuma/tavan) commit'lenmezse Actions stateless olduğu için
    her tur sıfırlanır ve aynı alarm 15 dakikada bir tekrar gider."""
    c = _indeks(ARSIV_ADIM, "git add")
    assert c >= 0
    metin = ARSIV_ADIM[c]["run"]
    assert "data/archive/" in metin
    assert "data/alert_state.json" in metin, "soğuma durumu commit'lenmiyor"


def test_arsiv_cron_onbes_dakika():
    """Nominal ritim config'teki `alerts.archive_freq_minutes` ile eşleşmeli
    (sağlık metriği bu ikisini karşılaştırıyor)."""
    from src import util
    cron = _tetik(ARSIV)["schedule"][0]["cron"]
    assert cron.split()[0] == "*/15"
    assert util.load_config()["alerts"]["archive_freq_minutes"] == 15


# ------------------------------------------------------------ ikisi için ortak
@pytest.mark.parametrize("wf,ad", [(GUNLUK, "daily.yml"), (ARSIV, "archive.yml")])
def test_ayni_concurrency_grubu(wf, ad):
    """İki workflow aynı repoya push ediyor; farklı gruplara ayrılırlarsa
    eşzamanlı push çakışması olur (retry'li pull --rebase bunu maskeler ama
    kaybedilen tur veri kaybıdır)."""
    assert wf["concurrency"]["group"] == "repo-commit", f"{ad}: grup değişmiş"
    assert wf["concurrency"].get("cancel-in-progress") is False, (
        f"{ad}: cancel-in-progress true → devam eden commit iptal edilebilir")


@pytest.mark.parametrize("wf,ad", [(GUNLUK, "daily.yml"), (ARSIV, "archive.yml")])
def test_yazma_izni_ve_python_surumu(wf, ad):
    assert wf["permissions"]["contents"] == "write", f"{ad}: push edemez"
    adimlar = _adimlar(wf, list(wf["jobs"])[0])
    surumler = [a.get("with", {}).get("python-version") for a in adimlar
                if "setup-python" in str(a.get("uses", ""))]
    assert surumler and all(str(s) == "3.12" for s in surumler), (
        f"{ad}: Python sürümü PROJECT.md kısıtından (3.12) farklı")


@pytest.mark.parametrize("wf,ad", [(GUNLUK, "daily.yml"), (ARSIV, "archive.yml")])
def test_elle_tetikleme_acik(wf, ad):
    """`workflow_dispatch` olmadan arıza anında elle koşum yapılamaz; bu, tek
    başına duran bir sistemde tek müdahale kolu."""
    assert "workflow_dispatch" in _tetik(wf), f"{ad}: elle tetikleme yok"


@pytest.mark.parametrize("wf,ad", [(GUNLUK, "daily.yml"), (ARSIV, "archive.yml")])
def test_sir_yalnizca_secretsten(wf, ad):
    """Token/anahtar workflow metnine gömülmemeli — repo PUBLIC."""
    metin = (WF / ad).read_text(encoding="utf-8")
    for anahtar in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "EVDS_API_KEY"):
        for satir in metin.splitlines():
            if anahtar in satir and "secrets." not in satir and "#" not in satir:
                pytest.fail(f"{ad}: {anahtar} secrets dışında geçiyor: {satir.strip()}")


def test_calisan_modul_adlari_gercek():
    """Workflow'un çağırdığı her `python -m src.X` modülü var olmalı.

    Bir modül yeniden adlandırılırsa üretim çöker ama yerelde hiçbir test
    bunu görmez — workflow'u kimse import etmiyor.
    """
    import re
    for ad, adimlar in (("daily.yml", GUNLUK_ADIM), ("archive.yml", ARSIV_ADIM)):
        for komut in _komutlar(adimlar):
            for modul in re.findall(r"python -m (src\.[\w.]+)", komut):
                yol = KOK / pathlib.Path(modul.replace(".", "/") + ".py")
                assert yol.exists(), f"{ad}: {modul} yok"
