"""MODÜL SAĞLIĞI — import edilebilirlik, imza kilidi, CLI girişleri, bağımlılıklar.

Bu dosya "sessizce kırılan yüzeyleri" test eder. Üretimde koşan tek şey
`python -m src.X` komutları; hiçbiri test paketinden çağrılmıyor, dolayısıyla:

- bir modül import edilemez hâle gelirse (döngüsel import, eksik bağımlılık)
  yalnız üretimde patlar,
- bir fonksiyonun PARAMETRE SIRASI değişirse konumsal çağıranlar sessizce
  yanlış argümanla koşar (`feature_vector(cfg, con, asof)` → `(con, cfg, asof)`
  hiçbir istisna üretmeyebilir, yalnız yanlış sonuç verir),
- `if __name__ == "__main__"` bloğu hiçbir zaman import edilmediği için oradaki
  bir yazım/ad hatası ancak üretimde görünür,
- `requirements.txt`'e eklenmemiş bir import yerelde çalışır, Actions'ta çöker.

Hepsi statik olarak denetlenebilir; bu dosya onu yapıyor.
"""
from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import pathlib
import pkgutil
import sys

import pytest

import src
from tests.conftest import KOK

# Alt paketler (src.sources) ayrı listede: dosya yolu `__init__.py` olduğu için
# `m.replace(".", "/") + ".py"` eşlemesi onlarda geçerli değil.
MODULLER = sorted(f"src.{m.name}" for m in pkgutil.iter_modules(src.__path__)
                  if not m.ispkg)
KAYNAK_MODULLERI = sorted(f"src.sources.{m.name}"
                          for m in pkgutil.iter_modules(
                              importlib.import_module("src.sources").__path__)
                          if not m.ispkg)

# Üçüncü parti bağımlılıklar: requirements.txt'te olmalı.
# İstisna, gerekçesiyle kayda geçer (repo kuralı).
BAGIMLILIK_ISTISNALARI = {
    "certifi": "requests'in transitive bağımlılığı; util._ensure_ascii_cert "
               "onu try/except içinde kullanıyor, yokluğu akışı bozmuyor",
}
PAKET_ADI = {"yaml": "PyYAML"}          # import adı ≠ paket adı


# ------------------------------------------------------------ import sağlığı
@pytest.mark.parametrize("modul", MODULLER + KAYNAK_MODULLERI)
def test_modul_import_edilebiliyor(modul):
    """Her modül tek başına import edilebilmeli (döngüsel import yok)."""
    assert importlib.import_module(modul) is not None


@pytest.mark.parametrize("modul", MODULLER + KAYNAK_MODULLERI)
def test_import_aninda_yan_etki_yok(modul):
    """Import DB açmamalı, config okumamalı, ağa çıkmamalı.

    Modül düzeyinde `db.connect(cfg)` ya da `load_config()` çağrısı, testleri
    ve CLI'yı gerçek `data/altin.sqlite`'a bağlar — L-009'un yolu buradan geçer.
    """
    yol = KOK / (modul.replace(".", "/") + ".py")
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    yasak = ("connect", "load_config", "load_env", "build_report", "run")
    for n in agac.body:                       # YALNIZ modül düzeyi
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            ad = getattr(n.value.func, "attr", getattr(n.value.func, "id", ""))
            assert ad not in yasak, f"{modul}: import anında {ad}() çağrılıyor"
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            ad = getattr(n.value.func, "attr", getattr(n.value.func, "id", ""))
            assert ad not in yasak, f"{modul}: import anında {ad}() çağrılıyor"


def test_modul_sayisi_beklenen_aralikta():
    """Negatif kontrol: parametrize listesi boşalırsa yukarıdaki testler
    sessizce hiçbir şey denetlemez."""
    assert len(MODULLER) >= 30, f"modül taraması eksik: {len(MODULLER)}"
    assert len(KAYNAK_MODULLERI) >= 3


# ------------------------------------------------------------ CLI girişleri
def _main_blogu(agac: ast.Module):
    for n in agac.body:
        if (isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                and getattr(n.test.left, "id", "") == "__name__"):
            return n
    return None


@pytest.mark.parametrize("modul", MODULLER)
def test_main_blogunda_tanimsiz_ad_yok(modul):
    """KİLİT TEST. `__main__` bloğu import edilmez → oradaki ad hatası yalnız
    üretimde görünür.

    Örnek senaryo: `run()` fonksiyonu `execute()` diye yeniden adlandırılır,
    modül import edilebilir kalır, tüm testler geçer — ama `python -m src.X`
    `NameError` ile patlar ve bu ancak Actions log'unda görünür (logs/
    gitignore'da olduğu için orada da görünmez).
    """
    yol = KOK / (modul.replace(".", "/") + ".py")
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    blok = _main_blogu(agac)
    if blok is None:
        pytest.skip("CLI girişi yok")
    m = importlib.import_module(modul)

    yerel: set[str] = set()
    for n in ast.walk(blok):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            yerel.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                yerel.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.comprehension) and isinstance(n.target, ast.Name):
            yerel.add(n.target.id)

    eksik = sorted({n.id for n in ast.walk(blok)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                   - yerel - set(dir(m)) - set(dir(builtins)))
    assert not eksik, f"{modul} __main__ bloğunda tanımsız ad: {eksik}"


def test_calistirilabilir_modul_sayisi_makul():
    n = sum(1 for m in MODULLER
            if _main_blogu(ast.parse((KOK / (m.replace(".", "/") + ".py")).read_text(
                encoding="utf-8"))) is not None)
    assert n >= 15, f"CLI girişi olan modül sayısı beklenenden az: {n}"


# ------------------------------------------------------------ imza kilidi
# Tek giriş noktası olan ya da konumsal çağrılan fonksiyonlar. Parametre SIRASI
# sözleşmedir: değişirse çağıranlar sessizce yanlış argüman geçirir.
IMZALAR = {
    "src.ozellikler:feature_vector": ["cfg", "con", "asof_date"],
    "src.ozellikler:son_kapali_gun": ["con", "bugun"],
    "src.karar:karar_ver": ["ozellikler", "cfg", "engel", "karne"],
    "src.karar:cekirdek_hukum": ["reel_net_mevduat", "esikler"],
    "src.karar:taktik_hukum": ["ufuk_engel", "kapi", "emniyet_carpani"],
    "src.karar:kapi_durumu": ["cfg", "karne"],
    "src.gram:hukum_dogru_mu": ["hukum", "gram_carry_kazanc_pct", "roundtrip_pct"],
    "src.gram:gram_carry_gain_pct": ["giris_gram_fiyat", "cikis_gram_fiyat",
                                     "mevduat_yillik_brut_pct", "gun", "stopaj_pct"],
    "src.gram:esik_pct": ["taban_ort_pct", "roundtrip_pct", "kol"],
    "src.gram:roundtrip_cost_pct": ["cfg", "enstruman"],
    "src.tahmin:gram_etkisi": ["hukum", "gram_carry_kazanc_pct", "roundtrip_pct"],
    "src.tahmin:karne_ozeti": ["satirlar", "zayif_n"],
    "src.tahmin:kaydet": ["cfg", "con", "asof_date", "kaynak"],
    "src.tahmin:karne": ["cfg", "con", "kol", "kaynak", "model_version"],
    "src.notify:evaluate_thresholds": ["ctx", "cfg"],
    "src.notify:apply_cooldown": ["alerts", "state", "now_iso", "cooldown_hours",
                                  "daily_cap"],
    "src.calc:theoretical_gram": ["ons_usd", "usdtry", "troy"],
    "src.calc:prim_pct": ["market_price", "theoretical"],
    "src.calc:zscore": ["history", "value", "min_samples"],
    "src.calculators:instrument_net": ["cfg", "name", "amount", "months",
                                       "annual_gold_pct"],
    "src.report:classify_gap": ["prim_gap_min", "collection_gap_min", "tol_min"],
    "src.dbdump:dump": ["cfg", "out_path"],
    "src.dbdump:restore": ["cfg", "dump_path"],
    "src.ohlc_hist:drop_unclosed_bar": ["bars", "today_iso"],
    "src.ohlc_hist:drop_weekend_bars": ["bars"],
}


@pytest.mark.parametrize("hedef,parametreler", sorted(IMZALAR.items()))
def test_imza_sozlesmesi_korunuyor(hedef, parametreler):
    """KİLİT TEST. Parametre adı/sırası değişmişse çağrı yolları sessizce bozulur.

    `gram_carry_gain_pct(giris, cikis, ...)` argümanlarının yeri değişirse
    ölçüm işaret değiştirir — hiçbir istisna fırlamaz, yalnız karne yalan olur.
    """
    modul_adi, fn_adi = hedef.split(":")
    fn = getattr(importlib.import_module(modul_adi), fn_adi)
    mevcut = [p for p in inspect.signature(fn).parameters]
    assert mevcut == parametreler, (
        f"{hedef} imzası değişti:\n  beklenen: {parametreler}\n  mevcut  : {mevcut}")


def test_imza_kilidi_gercek_fonksiyonlari_kapsiyor():
    """Negatif kontrol: sözlük yanlışsa (typo'lu modül adı) parametrize sessizce
    atlanmasın — import hatası testte görünür."""
    assert len(IMZALAR) >= 20


# ------------------------------------------------------------ bağımlılıklar
def _ucuncu_parti() -> dict[str, set[str]]:
    stdlib = set(sys.stdlib_module_names)
    out: dict[str, set[str]] = {}
    for p in sorted(pathlib.Path(KOK / "src").glob("**/*.py")):
        agac = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(agac):
            adlar = []
            if isinstance(n, ast.Import):
                adlar = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                adlar = [n.module.split(".")[0]]
            for ad in adlar:
                if ad not in stdlib and ad != "src":
                    out.setdefault(ad, set()).add(p.name)
    return out


def test_her_ucuncu_parti_import_requirementsta():
    """KİLİT TEST. Yerelde `.venv` her şeyi taşıyor; Actions yalnız
    `requirements.txt`'i kuruyor. Beyan edilmemiş bir import üretimde
    `ModuleNotFoundError` — ve `daily_job` bunu yutabilir (kritik olmayan adım)."""
    req = (KOK / "requirements.txt").read_text(encoding="utf-8").lower()
    eksik = []
    for ad, dosyalar in sorted(_ucuncu_parti().items()):
        if ad in BAGIMLILIK_ISTISNALARI:
            continue
        paket = PAKET_ADI.get(ad, ad).lower()
        if paket not in req:
            eksik.append(f"{ad} ({sorted(dosyalar)})")
    assert not eksik, f"requirements.txt'te olmayan bağımlılıklar: {eksik}"


def test_requirements_pytest_iceriyor():
    """Test paketi üretim bağımlılığı değil ama devir için şart: yeni araç
    `pip install -r requirements.txt` sonrası testleri koşabilmeli."""
    assert "pytest" in (KOK / "requirements.txt").read_text(encoding="utf-8")


def test_matplotlib_yalnizca_gorsel_yolda_ve_lazy():
    """`archive.yml` matplotlib kurmuyor; modül düzeyinde import edilirse 15
    dakikalık iş akışı `ImportError` ile patlar."""
    kaynak = (KOK / "src" / "grafik_ciz.py").read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    modul_duzeyi = [n for n in agac.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    adlar = {a.name.split(".")[0] for n in modul_duzeyi if isinstance(n, ast.Import)
             for a in n.names}
    assert "matplotlib" not in adlar, "matplotlib modül düzeyinde import edilmiş"
    assert "import matplotlib" in kaynak, "lazy import kaybolmuş"


def test_fred_onbellegi_diske_yazilmiyor():
    """`_FRED_CACHE` SÜREÇ ömürlü olmalı: "ölü" damgası diske yazılırsa FRED
    geri geldiği gün sistem onu bir daha hiç denemez (ADR #006-A'nın tersi)."""
    kaynak = (KOK / "src" / "indicators.py").read_text(encoding="utf-8")
    assert "_FRED_CACHE" in kaynak
    assert "write_json" not in kaynak, "FRED önbelleği kalıcılaştırılmış"
    assert "süreç" in kaynak, "önbelleğin süreç ömürlü olduğu belgelenmemiş"


# ------------------------------------------------------------ L-007: script'ler
def test_restore_db_ince_sarmalayici():
    """Workflow'un ilk adımı bu; sürpriz yan etki taşımamalı (L-007)."""
    kaynak = (KOK / "src" / "restore_db.py").read_text(encoding="utf-8")
    assert "dbdump.restore" in kaynak
    assert len(kaynak.splitlines()) < 15
    for yasak in ("unlink", "rmtree", "push", "commit"):
        assert yasak not in kaynak


def test_repo_scriptleri_okunmus_ve_dis_etkisi_belgeli():
    """L-007: "Repoda duran her script'i sonuna kadar oku." `set_secrets.py`
    dışa dönük (GitHub API'ye yazıyor) — bu bilinçli ve dosyanın başında yazılı;
    sessiz bir push/deploy YOK."""
    yol = KOK / "scripts" / "set_secrets.py"
    if not yol.exists():
        pytest.skip("scripts/set_secrets.py yok")
    metin = yol.read_text(encoding="utf-8")
    assert "secrets" in metin.lower()
    assert "ASLA yazdırılmaz" in metin or "asla yazdırılmaz" in metin.lower(), (
        "sır değerlerinin yazdırılmadığı belgelenmemiş")
    assert "git push" not in metin


def test_deploy_servislerinin_execstart_hedefi_var():
    """Ertelenmiş senaryonun altyapısı ÇALIŞIR durumda tutulmalı.

    `deploy/altin-backup.service` var olmayan bir script'i çağırıyordu; Oracle
    Cloud senaryosu aktive edildiği gün timer patlardı ve sebebi (yıllar sonra)
    anlaşılmazdı. Senaryo ERTELENDİ, iptal değil (PROJECT.md) → dosyalar
    silinmiyor (L-006), eksik parça tamamlanıyor.
    """
    eksik = []
    for yol in sorted((KOK / "deploy").glob("*.service")):
        for satir in yol.read_text(encoding="utf-8").splitlines():
            if satir.startswith("ExecStart="):
                komut = satir.split("=", 1)[1].split()[0]
                if komut.endswith(".sh"):
                    yerel = KOK / "scripts" / pathlib.Path(komut).name
                    if not yerel.exists():
                        eksik.append(f"{yol.name} → {komut}")
    assert not eksik, f"ExecStart hedefi repoda yok: {eksik}"


def test_yedek_scripti_yalnizca_yedek_aliyor():
    """KİLİT TEST (L-007). Bu script'in ESKİ sürümü sessizce `git commit &&
    git push` yapıyordu ve ürettiği ~2.9 MB'lık binary'ler gitignore'da değildi.

    Yeniden yazıldı; dersin kuralı testle sabitleniyor: dışa dönük hiçbir işlem
    (git/ağ/silme) yok ve çıktı dizini gitignore'lu.
    """
    yol = KOK / "scripts" / "backup.sh"
    assert yol.exists(), "scripts/backup.sh yok"
    metin = yol.read_text(encoding="utf-8")
    # Yorumlar ayıklanır: dosyanın başındaki L-007 açıklaması yasaklı komutları
    # ADIYLA anıyor ve bu ANLATIM, ihlal değil.
    kod = "\n".join(s.split("#")[0] for s in metin.splitlines())
    for yasak in ("git ", "curl", "wget", "rm ", "scp", "rsync"):
        assert yasak not in kod, f"backup.sh dışa dönük işlem içeriyor: {yasak!r}"
    assert "src.backup_db" in kod, "WAL-güvenli anlık görüntü aracını çağırmıyor"
    assert "set -euo pipefail" in kod, "hata durumunda sessizce devam ediyor"
    assert "L-007" in metin, "neden bu kadar dar olduğu belgelenmemiş"


def test_yedek_ciktisi_gitignorelu():
    """Binary yedek repoya ASLA girmemeli (Faz 5'te çözülen sorunun kendisi)."""
    import subprocess
    r = subprocess.run(("git", "-C", str(KOK), "check-ignore", "-q",
                        "data/backups/altin_latest.sqlite"), capture_output=True)
    if r.returncode == 128:
        pytest.skip("git deposu yok")
    assert r.returncode == 0, "data/backups/ ignore edilmiyor"


def test_deploy_paketi_bir_butun_olarak_duruyor():
    """L-006: "Kullanılmıyor" ile "silinebilir" aynı şey değil. Bu dosyalar
    ertelenmiş bir kararın (Oracle Cloud) hazır altyapısı ve birbirine bağlı tek
    bir paket; biri silinirse diğerleri anlamsız kalır (PROJECT.md "Kapsam Dışı")."""
    for ad in ("altin-collector.service", "altin-bot.service", "altin-report.service",
               "altin-report.timer", "altin-evds.service", "altin-evds.timer"):
        assert (KOK / "deploy" / ad).exists(), f"deploy/{ad} silinmiş (L-006)"
    for modul in ("collector", "supervisor"):
        assert (KOK / "src" / f"{modul}.py").exists(), (
            f"src/{modul}.py silinmiş — Oracle senaryosunun parçası (L-006)")


def test_deploy_servisleri_gercek_modulleri_cagiriyor():
    """Systemd dosyaları `python -m src.X` çağırıyor; modül yeniden
    adlandırılırsa senaryo aktive edildiği gün patlar."""
    import re
    for yol in sorted((KOK / "deploy").glob("*.service")):
        for modul in re.findall(r"python -m (src\.[a-z_]+)",
                                yol.read_text(encoding="utf-8")):
            assert (KOK / (modul.replace(".", "/") + ".py")).exists(), (
                f"{yol.name} → {modul} yok")
