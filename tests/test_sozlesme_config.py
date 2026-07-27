"""config.yaml ↔ kod SÖZLEŞMESİ ve ÖNCEDEN KAYITLI eşiklerin kilidi.

İki ayrı hasar sınıfını kapatır:

**A) Sözleşme kopması.** `config.yaml`'ın ilk satırı kuralı söylüyor: "Tüm eşik /
URL / oran bu dosyada. Kod içine sabit gömülmez." Bir kod `cfg["x"]["y"]` okuyup
o anahtar config'te yoksa `KeyError` fırlar; `daily_job`'un kritik olmayan
adımları bu hatayı YUTAR (bkz. ADR #008 K-6) → özellik sessizce ölür. Tersi de
olur: config'e anahtar eklenir, kimse okumaz (ADR #008'de 7 ölü anahtar bulundu).
Bu testler iki yönü de statik olarak denetler; DB, ağ, çalışma zamanı gerekmez.

**B) Eşik gevşetmesi.** Bu projenin dürüstlük iddiası "şartı ÖNCEDEN yazdım ve
gevşetmeyeceğim"e dayanıyor (ADR #007-C: taktik kapı; ADR #006-B: z-skor kapısı).
Bir kapıyı açmanın en kolay yolu kodu değiştirmek değil, **config'teki eşiği
düşürmek**tir — ve bu değişiklik hiçbir testi düşürmezdi. Artık düşürüyor.
Eşiği gerçekten değiştirmek isteyen ADR yazıp bu testi de bilerek güncellemeli;
bilmeden yapılamaz.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src import calc, util
from tests.conftest import KOK

CFG = util.load_config()
SRC = sorted(pathlib.Path(KOK / "src").glob("**/*.py"))
SRC_METIN = "\n".join(p.read_text(encoding="utf-8") for p in SRC)

# `cfg` adı bu repoda sözleşmedir: her modül config'i `cfg: dict` parametresiyle
# alır. Yerel değişkenler (`c`, `ic`, `a`) bilerek KAPSAM DIŞI — onlar config
# değil, config'in bir dilimi ya da tamamen başka bir sözlük olabilir
# (ör. `c = panel["consensus"]`) ve tarama yanlış pozitif üretirdi.
CFG_ADLARI = {"cfg"}

# Yaprakları kod tarafından ADIYLA okunmayan, DİNAMİK olarak (items() ile)
# tüketilen kapsayıcılar. Muafiyetin kendisi de denetlenir: aşağıdaki
# `test_dinamik_kapsayicilar_gercekten_iterlenir` bu kapsayıcıların gerçekten
# döngüyle okunduğunu doğrular, yoksa muafiyet ölü anahtarı gizleyen bir
# arka kapıya dönüşür.
DINAMIK_KAPSAYICILAR = {
    ("sources", "truncgil", "keys"): "truncgil.fetch → keys.items()",
    ("sources", "evds", "series"): "evds_job._series_map → smap.items()",
    ("karar", "ufuklar_gun"): "tahmin.kaydet / gram.sat_engeli → ufuklar.items()",
}


def _zincir(node: ast.AST) -> tuple[str, ...] | None:
    """`cfg["a"]["b"]` → ("a","b"). Dinamik anahtarda None (güvenli taraf)."""
    anahtarlar: list[str] = []
    cur = node
    while isinstance(cur, ast.Subscript):
        dilim = cur.slice
        if isinstance(dilim, ast.Constant) and isinstance(dilim.value, str):
            anahtarlar.append(dilim.value)
        else:
            return None
        cur = cur.value
    if isinstance(cur, ast.Name) and cur.id in CFG_ADLARI:
        return tuple(reversed(anahtarlar))
    return None


def _config_okumalari() -> tuple[set, set]:
    """(zorunlu, opsiyonel) config yolları — (dosya, yol) çiftleri."""
    zorunlu, opsiyonel = set(), set()
    for p in SRC:
        agac = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(agac):
            if isinstance(n, ast.Subscript):
                z = _zincir(n)
                if z:
                    zorunlu.add((p.name, z))
            # cfg["a"].get("b", varsayilan)
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "get" and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and isinstance(n.args[0].value, str)):
                taban = n.func.value
                if isinstance(taban, ast.Subscript):
                    z = _zincir(taban)
                elif isinstance(taban, ast.Name) and taban.id in CFG_ADLARI:
                    z = ()
                else:
                    z = None
                if z is not None:
                    opsiyonel.add((p.name, z + (n.args[0].value,)))
    return zorunlu, opsiyonel


def _cozulur(yol: tuple[str, ...]) -> bool:
    cur = CFG
    for k in yol:
        if not isinstance(cur, dict) or k not in cur:
            return False
        cur = cur[k]
    return True


def _yapraklar(d: dict, yol: tuple = ()):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _yapraklar(v, yol + (k,))
        else:
            yield yol + (k,), v


ZORUNLU, OPSIYONEL = _config_okumalari()


# ---------------------------------------------------------------- A) sözleşme
def test_taranan_okuma_sayisi_makul():
    """Tarayıcı gerçekten çalışıyor mu? (boş küme her testi geçirir)

    Negatif kontrol: `_zincir` bozulursa aşağıdaki testler girdisiz kalır ve
    sessizce yeşile döner — bu testin varlık sebebi o sessizliği engellemek.
    """
    assert len(ZORUNLU) > 100, f"config taraması çöktü: {len(ZORUNLU)} okuma"
    assert len(OPSIYONEL) > 10


def test_kodun_okudugu_her_config_anahtari_var():
    """`cfg[...]` zincirlerinin HEPSİ config.yaml'da çözülmeli.

    Çözülmezse üretimde `KeyError`; kritik olmayan adımlarda bu hata yutulur
    ve özellik sessizce ölür (ADR #008 K-6 aynı zemin).
    """
    eksik = sorted((f, ".".join(z)) for f, z in ZORUNLU if not _cozulur(z))
    assert not eksik, f"config.yaml'da olmayan anahtarlar okunuyor: {eksik}"


def test_opsiyonel_okumalar_da_configte_tanimli():
    """`.get(anahtar, varsayilan)` bile config'te TANIMLI olmalı.

    Varsayılan bir kaçış kapısıdır: anahtar silinirse kod çalışmaya devam eder
    ama artık config'in söylediğini değil koda gömülü sayıyı uygular — yani
    "eşikler config'te" kuralı sessizce çöker. Varsayılan çökme koruması olarak
    kalır, tek kaynak olarak DEĞİL.
    """
    eksik = sorted((f, ".".join(z)) for f, z in OPSIYONEL if not _cozulur(z))
    assert not eksik, f"varsayılana düşen (config'te olmayan) anahtarlar: {eksik}"


def test_olu_config_anahtari_yok():
    """config'te olup kodda hiç okunmayan yaprak kalmasın.

    ADR #008 (LOW) yedi ölü anahtar buldu (`kismi_oranlar`, `coverage_warn_pct`,
    `report.hour_local`, ...). Ölü anahtar zararsız değil: okuyan insan onun
    etkili olduğunu sanır ve değiştirip "neden hiçbir şey değişmedi?" der.
    """
    olu = []
    for yol, _ in _yapraklar(CFG):
        if any(yol[:len(k)] == k for k in DINAMIK_KAPSAYICILAR):
            continue
        ad = yol[-1]
        if f'"{ad}"' in SRC_METIN or f"'{ad}'" in SRC_METIN:
            continue
        olu.append(".".join(yol))
    assert not olu, (f"kodda hiç okunmayan config anahtarları: {olu} — ya bağla "
                     "ya sil (ADR #008 LOW)")


@pytest.mark.parametrize("kapsayici", sorted(DINAMIK_KAPSAYICILAR))
def test_dinamik_kapsayicilar_gercekten_iterlenir(kapsayici):
    """Muafiyet listesi ölü anahtar saklamak için kullanılamaz.

    Bir kapsayıcı "dinamik tüketiliyor" diye muaf tutuluyorsa, onu okuyan
    dosyada gerçekten bir döngü (`.items()`) olmalı. Aksi halde muafiyet
    `test_olu_config_anahtari_yok`'u sessizce devre dışı bırakırdı.
    """
    assert _cozulur(kapsayici), f"{kapsayici} config'te yok"
    okuyanlar = {f for f, z in ZORUNLU if z == kapsayici}
    assert okuyanlar, f"{kapsayici} hiçbir yerden okunmuyor → ölü"
    iterleyen = [f for f in okuyanlar
                 if ".items()" in (KOK / "src" / f).read_text(encoding="utf-8")]
    assert iterleyen, (f"{kapsayici} okunuyor ama okuyan dosyalarda ({okuyanlar}) "
                       "döngü yok → muafiyet geçersiz")


def test_troy_ons_sabiti_tek_deger():
    """Aynı fiziksel sabitin iki kaynağı var; ayrışırlarsa prim yanlış hesaplanır.

    `calc.TROY_OZ` varsayılan argüman, `config.instruments.troy_ounce_gram`
    çağrılarda geçilen değer. Biri değişip diğeri kalırsa hangi yolun
    kullanıldığına göre farklı teorik gram üretilir.
    """
    assert CFG["instruments"]["troy_ounce_gram"] == pytest.approx(calc.TROY_OZ)


def test_ons_ve_kur_sembolleri_her_yerde_ayni():
    """Sembol üç yerde yazılı; birini yeniden adlandırıp diğerini bırakmak
    L-008'in ta kendisi olur (yarım bağlama). Tabloya bir sembolle yazılıp
    başka bir sembolle okunan veri sessizce boş döner."""
    ons = CFG["chart"]["ohlc"]["symbols"]["ons"]
    assert CFG["sources"]["yfinance"]["ons_ticker"] == ons
    assert CFG["indicators"]["ons_ticker"] == ons
    assert CFG["chart"]["ohlc"]["symbols"]["kur"] == \
        CFG["sources"]["yfinance"]["usdtry_ticker"]


def test_tarihsel_baslangiclar_ayni():
    """`chart.ohlc.start` ile `backtest.start` aynı olmalı (config yorumu bunu
    söylüyor: "history_daily ile aynı başlangıç"). Ayrışırsa OHLC göstergeleri
    ile fiyat serisi farklı pencerelerden ölçülür ve karşılaştırma bozulur."""
    assert CFG["chart"]["ohlc"]["start"] == CFG["backtest"]["start"]


def test_dump_yolu_izlenen_data_altinda():
    """Actions `git add data/` yapıyor; dump başka bir dizine taşınırsa
    commit'lenmez ve Actions stateless olduğu için TÜM DB her gün sıfırlanır."""
    assert CFG["paths"]["db_dump"].startswith("data/")
    assert CFG["paths"]["db"].startswith("data/")
    assert CFG["paths"]["db"].endswith(".sqlite"), "binary DB gitignore kuralına bağlı"


# ---------------------------------------------------------------- B) kapı kilidi
def test_taktik_kol_dogustan_kapali_kalir():
    """KİLİT TEST (ADR #007-C).

    Taktik kol gerçek para yakabilir ve açılma şartı ölçümle konuldu: satmak
    1 ay ufkunda ortalama %-1.99 gram kaybettiriyor. `aktif: true` yapmak tek
    satırlık bir config değişikliğidir; bu test onu bilinçsiz yapılamaz kılar.
    """
    assert CFG["karar"]["taktik"]["aktif"] is False, (
        "Taktik kol açılmış. Bu ancak canlı KARNE şartı sağlandığında ve ADR "
        "yazıldığında meşrudur (ADR #007-C). Şart: N>=30 çözülmüş + gram "
        "etkisi>0 + isabet farkı>+10p. Karne henüz ÖLÇÜM İÇERMİYOR (ADR #008).")


def test_taktik_kapi_sartlari_gevsetilmemis():
    """Önceden kayıtlı şartlar SERTLEŞEBİLİR, gevşeyemez."""
    t = CFG["karar"]["taktik"]
    assert t["kapi_min_cozulmus"] >= 30
    assert t["kapi_min_gram_etkisi_pct"] >= 0.0
    assert t["kapi_min_isabet_farki_puan"] >= 10.0
    assert t["maliyet_emniyet_carpani"] >= 1.5, (
        "emniyet çarpanı 1.5'in altına inerse beklenen kazanç ölçülen maliyeti "
        "yeterli payla aşmadan SAT üretilebilir")


def test_cekirdek_kademeleri_dar_kalir():
    """Kanıt gücü t≈1.4; 2x/0.5x agresiflik bu kanıtla savunulamaz (ADR #007-C).

    `test_karar.test_cekirdek_kademeler_dar` aynı bandı kontrol ediyor; burada
    ayrıca eşiklerin SIRASI ve alımın hiç kesilmemesi denetlenir.
    """
    c = CFG["karar"]["cekirdek"]
    assert 1.0 < c["kademe_carpani_ust"] <= 1.5
    assert 0.5 <= c["kademe_carpani_alt"] < 1.0
    assert c["kademe_carpani_alt"] > 0.0, "çekirdek kol alımı ASLA kesmez"
    assert c["reel_mevduat_dusuk_pct"] < c["reel_mevduat_yuksek_pct"]


def test_zskor_kapisi_60_gun():
    """Kapı GÜN sayar ve 60'tır (Faz 7 + ADR #006-B). Düşürmek, kalibre
    edilmemiş bir alarmı erken canlıya almak demektir; kuru prova (dry-run)
    tam bu riski azaltmak için var."""
    assert CFG["stats"]["zscore_min_samples"] == 60
    assert CFG["stats"]["zskor_prova_aktif"] is True, (
        "kuru prova kapatılmış → kapı açıldığında dağılım bilinmeyecek "
        "(ADR #006-B'nin amacı buydu)")


def test_karne_zayif_n_backtestten_sert():
    """Seçilmiş bir kuralın karnesi, ham bir dağılımdan daha çok örnek ister."""
    assert CFG["karar"]["karne"]["zayif_n"] >= CFG["backtest"]["weak_n_threshold"]
    assert CFG["karar"]["karne"]["zayif_n"] >= 30


def test_karar_motoru_ve_grafik_acik():
    """`karar.enabled: false` HÜKÜM bloğunu rapordan sessizce siler — kullanıcının
    rapordan beklediği tek şey o blok (ADR #007)."""
    assert CFG["karar"]["enabled"] is True
    assert CFG["chart"]["enabled"] is True


def test_birincil_ufuk_ve_enstruman_tanimli():
    """Hüküm bloğu bu iki anahtara dayanıyor; tanımsızlık `KeyError` demek."""
    k = CFG["karar"]
    assert k["birincil_ufuk"] in k["ufuklar_gun"]
    assert k["enstruman"] in CFG["instrument_costs"], "gidiş-dönüş maliyeti okunamaz"
    assert isinstance(k["model_version"], str) and k["model_version"]


def test_alti_ay_ufku_hukme_girmez():
    """ADR #007: 6 ay ufkunda 20 örtüşmeyen pencere kalıyor — hiçbir parametre
    dürüstçe kalibre edilemez. Ölçüm raporda gösterilir, HÜKME girmez."""
    assert "6ay" not in CFG["karar"]["ufuklar_gun"]


def test_evds_yayin_gecikmeleri_look_aheadi_kapatir():
    """`evds_daily.date` DÖNEM BAŞIDIR. Gecikme 0 olursa `date <= asof` filtresi
    1-35 gün geleceği sızdırır (ADR #007-G) ve karne sahtelenir."""
    g = CFG["karar"]["evds_yayin_gecikme_gun"]
    for seri in ("mevduat_3ay", "mevduat_1yil", "aofm_politika", "enf_bek_12ay"):
        assert seri in g, f"{seri} gecikmesi tanımsız → feature_vector KeyError"
        assert g[seri] >= 1, f"{seri} gecikmesi 0 → yayınlanmamış veri sızıyor"
    assert g["tufe"] >= 30, "TÜFE ayın ~3'ünde önceki ay için yayınlanır"


def test_saglik_metrikleri_gozlemlenen_ritme_kalibre():
    """ADR #003/#005: NOMİNAL cron (*/15) ile GERÇEKLEŞEN ritim (~90 dk) farklı.
    Metrik nominale döndürülürse sağlıklı sistem her gün "ardışık çalışma
    başarısız" der — bu tam olarak L-003'teki yanlış alarmdır."""
    a = CFG["alerts"]
    assert a["archive_observed_freq_minutes"] > a["archive_freq_minutes"]
    assert a["archive_gap_tolerance_factor"] >= 1.0


def test_bildirim_yorgunlugu_ayarlari_acik():
    """Soğuma ve günlük tavan kapatılırsa alarm yorgunluğu geri gelir."""
    a = CFG["alerts"]
    assert a["cooldown_hours"] > 0 and a["daily_cap"] > 0
    assert 50 < a["spread_percentile"] < 100


def test_uretim_modu_actions():
    """Üretim GitHub Actions (PROJECT.md kısıtı; Oracle ertelendi/iptal).
    `collector` moduna çevrilmesi sağlık metriklerini poll_seconds'a (60 sn)
    kalibre eder ve kapsama %4 görünür — sistem sağlıklıyken."""
    assert CFG.get("runtime_mode", "actions") == "actions"
