"""YAPISAL korumalar — "yazılmış ama bağlanmamış koruma, olmayan korumadır" (L-011).

Bu dosya davranış değil YAPI test eder ve bunun sebebi ölçülmüş bir olaydır:
`asof = T−1` garantisi hem ADR'de hem docstring'de "yapısal garanti" diye
anlatılıyordu, koruma gerçekten yazılmıştı — ama parametre opsiyoneldi ve iki
çağıranın hiçbiri onu geçmiyordu. Yani davranış testi yazmak yetmez; **korumayı
atlayan bir yol var mı?** sorusunu da testin sorması gerekiyor. L-011'in kuralı
aynen şu: "Sonra 'bu korumayı atlayan bir yol var mı?' diye grep at."

Burada grep'i test atıyor. Kapsanan kalıplar:

| Kalıp | Ders |
|---|---|
| Tek `asof` kaynağı | L-011 (ikinci, korumasız `MAX(date)` kopyası) |
| Yazma yolunda bugün/hafta sonu filtresi | ADR #008-D/G (kaynağı kapat, tüketiciyi değil) |
| Eşik mantığı tek yerde | ADR #006-D (üretim 5 kural, CLI 3 kural — sessizce ayrışmıştı) |
| Maliyet/teorik gram tek formül | L-008 (aynı değeri üreten ikinci yol) |
| `predictions` tek yazıcı | ADR #007-F (kayıt disiplini) |
| Adım hatası tek yola yazılır | ADR #008 K-6 (Actions yeşil kalırken sistem ölü) |

Metin taraması naif ama kasıtlı: karmaşık bir çözümleyici yerine "yorumları at,
kalan kodda ara" yeterli — bu repoda SQL'ler tek satırlık string'ler.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from src import (calculators, daily_job, db, gram, karar, notify, ohlc_hist,
                 ozellikler, signals, tahmin)
from tests.conftest import KOK

SRC = sorted(pathlib.Path(KOK / "src").glob("**/*.py"))


def _kod_metni(yol: pathlib.Path) -> str:
    """Docstring ve yorumları ATILMIŞ kaynak — "yorumda geçiyor" yanlış pozitifi
    bu repoda gerçek bir sorun: düzeltilen hatalar yorumlarda anlatılıyor."""
    ham = yol.read_text(encoding="utf-8")
    parcalar = ham.split('"""')
    kod = "".join(parcalar[::2])                     # tek indeksler docstring
    return "\n".join(s.split("#")[0] for s in kod.splitlines())


KOD = {p.name: _kod_metni(p) for p in SRC}


# ------------------------------------------------------------ L-011: tek asof
def test_asof_hesabi_tek_yerde():
    """KİLİT TEST. `history_daily` üzerinde ikinci bir `MAX(date)` olamaz.

    `tahmin.py`'de tam böyle bir kopya vardı ve o kopyada bugünü dışlayan filtre
    YOKTU; iki asof yolu = iki farklı kesim tarihi ihtimali.
    """
    suclular = [ad for ad, kod in KOD.items()
                if "MAX(date)" in kod and ad != "ozellikler.py"]
    assert not suclular, (f"ikinci asof yolu: {suclular} — asof'un tek kaynağı "
                          "ozellikler.son_kapali_gun (L-011)")


def test_son_kapali_gun_filtresi_zorunlu():
    """Filtresiz bir yol BİLEREK yok: `bugun` opsiyonel olsa bile sorgu daima
    `date < ?` uygular. Filtre kaldırılırsa bugünün YARIM barı asof olur ve
    `predictions`'a DEĞİŞTİRİLEMEZ şekilde yazılır."""
    kaynak = inspect.getsource(ozellikler.son_kapali_gun)
    assert "date < ?" in kaynak
    assert "local_today" in kaynak, "referans yerel TR günü olmalı (UTC değil)"


def test_asof_yerel_gun_kullanir():
    """UTC kullanmak, TR'de gece 01:00'de koşan bir işte o günün yarım barını
    "kapanmış" gösterirdi (GC=F 21:00 UTC = 00:00 TR'de kapanıyor)."""
    kaynak = inspect.getsource(ozellikler)
    assert "utcnow().date()" not in kaynak


# ------------------------------------------------- ADR #008-D/G: kaynağı kapat
def test_history_yazma_yolu_bugunu_disliyor():
    """16 tüketiciyi tek tek yamamak L-008'in ta kendisi olurdu; koruma KAYNAKTA.

    `build_history_daily` kesişimden bugünü düşürmezse yarım bar tabloya girer
    ve en kritik tüketici (`tahmin._fiyat_serisi` → `cozumle`'nin ÇIKIŞ
    ortalaması) onu `prediction_outcomes`'a yazar.
    """
    from src import history
    kaynak = inspect.getsource(history.build_history_daily)
    assert "local_today" in kaynak
    assert "< bugun" in kaynak.replace("<bugun", "< bugun")


def test_ohlc_yazma_yolu_iki_filtreyi_de_uygular():
    """`drop_unclosed_bar` tek başına YETMİYOR: Cumartesi yazılan bar Pazartesi
    koşumunda geçmiş tarihlidir ve o filtreden geçer (ADR #008-G).
    Ölçüldü: 5401 tarihsel barın 0'ı hafta sonu → filtre güvenli."""
    kaynak = inspect.getsource(ohlc_hist.update_ohlc_daily)
    assert "drop_unclosed_bar" in kaynak
    assert "drop_weekend_bars" in kaynak, "hafta sonu hayalet barı geri gelir"


def test_notify_alarmlari_yarim_bari_referans_almaz():
    """ADR #008 K-7: filtresiz "en son satır", günlük koşumdan sonra BUGÜNÜN
    yarım kapanışı oluyordu → fark ~0 → alarm akşamları ölü."""
    for fn in (notify._atr_from_history, notify.build_context):
        assert "date < ?" in inspect.getsource(fn), f"{fn.__name__}: bugün filtresi yok"


def test_gram_icin_ohlc_bari_yazilmiyor():
    """db.py şema kuralı: `high_gram ≠ high_ons × high_usdtry` (aynı ana ait
    değil) → gram TL için OHLC TÜRETİLMEZ. Sembol listesi tam iki tanedir."""
    from src import util
    cfg = util.load_config()
    semboller = ohlc_hist._symbols(cfg)
    assert len(semboller) == 2
    assert not any("gram" in s.lower() for s in semboller)


# ------------------------------------------------- ADR #006-D: tek kaynak eşik
def test_esik_mantigi_yalnizca_notifyda():
    """KİLİT TEST. İki kopya ZATEN ayrışmıştı: üretim 5 kural uygularken CLI
    yalnız 3'ünü biliyordu (`makas` ve `ceyrek_prim` eksik).

    `signals.py` eşik anahtarlarını kendi başına okumaya başlarsa ikinci kopya
    geri gelmiş demektir.
    """
    esik_anahtarlari = ("prim_abs_pct", "prim_z", "daily_move_atr",
                        "spread_percentile", "quarter_z")
    kod = KOD["signals.py"]
    sizan = [a for a in esik_anahtarlari if f'"{a}"' in kod and "alerts" in kod
             and f'a["{a}"]' in kod]
    assert not sizan, f"signals.py eşiği kendi okuyor: {sizan}"
    assert "notify.evaluate_thresholds" in inspect.getsource(signals.evaluate_alerts)


def test_kural_kumesi_bes_kural():
    """Üretimin kural kümesi TAM olarak beş kuraldır (ADR #006-D).

    Ayrışma şöyle ölçülmüştü: üretim (`notify`) 5 kural uygularken CLI yalnız
    3'ünü biliyordu — `makas` ve `ceyrek_prim` eksikti. Bir kural sessizce
    düşerse (ör. `quarter_z` yeniden "şimdilik pas" olursa, bkz. ADR #006-C)
    kullanıcı o alarmı bir daha hiç almaz ve bunu fark etmesinin yolu yoktur.
    Bu yüzden kümenin KENDİSİ kilitli.
    """
    from src import util
    cfg = util.load_config()
    hepsi_tetikler = {"all_fresh": True, "prim": 9.0, "prim_z": 5.0,
                      "spread": 1.0, "spread_p90": 0.1,
                      "daily_move": 500.0, "atr": 10.0, "quarter_z": 5.0}
    tipler = {a["tip"] for a in notify.evaluate_thresholds(hepsi_tetikler, cfg)}
    assert tipler == {"prim_sapma", "prim_z", "makas", "gunluk_hareket",
                      "ceyrek_prim"}, f"kural kümesi değişti: {sorted(tipler)}"


# ------------------------------------------------- L-008: tek formül
def test_maliyet_formulu_tek_modulde():
    """Gidiş-dönüş maliyeti yalnız `calculators.instrument_net`'te hesaplanır.

    `gram.roundtrip_cost_pct` formülü tekrar yazmıyor, onu çağırıyor — ikinci
    kopya, taktik eşiğinin (taban + maliyet) sessizce ayrışması demek olurdu.
    """
    maliyet_anahtarlari = ("bsmv_pct", "alis_makas_pct", "satis_makas_pct",
                           "alis_satis_makas_pct", "komisyon_pct",
                           "yonetim_ucreti_yillik_pct")
    for anahtar in maliyet_anahtarlari:
        okuyan = [ad for ad, kod in KOD.items() if anahtar in kod]
        assert okuyan in ([], ["calculators.py"]), f"{anahtar} şurada da: {okuyan}"
    assert "calculators.instrument_net" in inspect.getsource(gram.roundtrip_cost_pct) \
        or "instrument_net" in inspect.getsource(gram.roundtrip_cost_pct)


def test_teorik_gram_formulu_tek_modulde():
    """`ons / troy * usd` yalnız `calc.theoretical_gram`'da. Sabit de tek yerde:
    `31.10...` başka bir dosyada görünürse ikinci bir troy ons tanımı var."""
    sabit_iceren = [ad for ad, kod in KOD.items() if "31.10" in kod]
    assert sabit_iceren == ["calc.py"], f"troy ons sabiti şurada da: {sabit_iceren}"
    for ad in ("history.py", "import_actions.py", "notify.py", "collector.py"):
        assert "theoretical_gram" in KOD[ad], f"{ad} teoriği kendi hesaplıyor olabilir"


def test_prim_serisi_olu_argumani_geri_gelmedi():
    """ADR #008 LOW: `only_valid` sekiz çağıranın sekizinde de True geçilen ölü
    bir daldı ve "geçersiz kayıtları da kat" seçeneği yanlış kullanıma davetiyeydi."""
    # Docstring'i taramıyoruz: argümanın NEDEN kaldırıldığı orada anlatılıyor.
    assert "only_valid" not in KOD["db.py"], "ölü argüman geri gelmiş"
    imza = inspect.signature(db.prim_series)
    assert list(imza.parameters) == ["con", "column"]


# ------------------------------------------------- ADR #007-F/G: tek yol
def test_predictions_tek_yazici():
    """Tahmin kaydı yalnız `tahmin.py`'den yazılır. Başka bir modül yazarsa
    değiştirilemezlik disiplini (asof, kapı durumu, özellik vektörü) atlanabilir."""
    yazanlar = [ad for ad, kod in KOD.items() if "INTO predictions" in kod]
    assert yazanlar == ["tahmin.py"], f"predictions'a yazan başka modül: {yazanlar}"


def test_ozellik_tek_giris_noktasi():
    """ADR #007-G: canlı üretim ve tarihsel replay AYNI fonksiyonu çağırır.
    Üçüncü bir çağıran meşru olabilir ama listeye bilinçli eklenmeli."""
    izinli = {"ozellikler.py", "karar.py", "tahmin.py", "tahmin_backfill.py"}
    cagiranlar = {ad for ad, kod in KOD.items() if "feature_vector(" in kod}
    assert cagiranlar <= izinli, f"beklenmeyen özellik okuyucu: {cagiranlar - izinli}"
    assert {"karar.py", "tahmin.py"} <= cagiranlar, "canlı yol kopmuş"


def test_kapi_esikleri_configten_okunuyor():
    """Kapı şartı config'te ÖNCEDEN kayıtlı; koda gömülmesi onu görünmez kılar."""
    kaynak = inspect.getsource(karar.kapi_durumu)
    for anahtar in ("kapi_min_cozulmus", "kapi_min_gram_etkisi_pct",
                    "kapi_min_isabet_farki_puan"):
        assert anahtar in kaynak, f"{anahtar} config'ten okunmuyor"


def test_hukum_dogru_mu_tek_esik_kullanir():
    """Karneyi güzelleştirmek için oynanabilecek ikinci bir eşik (ATR ölü bandı)
    BİLEREK yok; tek eşik piyasadan gelen gidiş-dönüş maliyetidir."""
    kaynak = inspect.getsource(gram.hukum_dogru_mu)
    assert "roundtrip" in kaynak
    assert "atr" not in kaynak.lower().replace("atr ölü", "")


# ------------------------------------------------- ADR #008 K-6: hata yolu
def test_daily_job_her_istisna_hatayi_kaydeder():
    """KİLİT TEST. Altı adımın hepsi istisnayı yutuyordu ve süreç daima 0 ile
    çıkıyordu → `import`/`rapor` günlerce patlasa Actions YEŞİL kalırdı.

    AST ile denetlenir: `run` içindeki HER `except` bloğu `_hata` çağırmalı.
    Yalnız `log.warning` yapan bir blok geri gelirse test düşer.
    """
    agac = ast.parse(inspect.getsource(daily_job))
    fn = next(n for n in ast.walk(agac)
              if isinstance(n, ast.FunctionDef) and n.name == "run")
    bloklar = [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]
    assert len(bloklar) >= 6, f"beklenenden az except bloğu: {len(bloklar)}"
    for b in bloklar:
        cagrilar = {getattr(c.func, "id", getattr(c.func, "attr", ""))
                    for c in ast.walk(b) if isinstance(c, ast.Call)}
        assert "_hata" in cagrilar, (
            f"satır {b.lineno}: istisna `_hata` ile kaydedilmiyor → Actions "
            "yeşil kalır (ADR #008 K-6)")


def test_kritik_adim_adlari_gercek_adimlarla_esleşiyor():
    """KİLİT TEST. `KRITIK_ADIMLAR` metin eşleşmesiyle çalışıyor; bir adımın
    `_hata(result, "rapor", e)` etiketi değişirse liste sessizce hiçbir şeyi
    yakalamaz — iş yine daima yeşil olur."""
    agac = ast.parse(inspect.getsource(daily_job))
    etiketler = set()
    for n in ast.walk(agac):
        if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_hata"
                and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)):
            etiketler.add(n.args[1].value)
    eksik = set(daily_job.KRITIK_ADIMLAR) - etiketler
    assert not eksik, (f"KRITIK_ADIMLAR'daki {eksik} adı hiçbir _hata çağrısında "
                       f"yok (mevcut etiketler: {sorted(etiketler)})")


def test_main_blogu_kritik_hatada_exit_ediyor():
    """`exit(1)` olmadan Actions kırmızıya düşmez; dump+commit adımları da
    atlanmaz ve yarım veri commit'lenir."""
    kod = KOD["daily_job.py"]
    assert "basarisiz_mi" in kod and "sys.exit(1)" in kod


def test_uyari_metni_ortak():
    """Disclaimer maliyeti sıfır ve çıktıyı sulandırmıyor (ADR #007); iki
    modülde birebir aynı cümle olmalı, üçüncü bir varyant üretilmemeli."""
    assert karar.UYARI == signals.UYARI
    assert "yatırım tavsiyesi değildir" in karar.UYARI
    assert "yatırım tavsiyesi değildir" in inspect.getsource(notify._format_alert)


@pytest.mark.parametrize("modul", ["report.py", "gram.py", "tahmin_backfill.py"])
def test_rapor_ciktilarinda_disclaimer(modul):
    assert "yatırım tavsiyesi değildir" in (KOK / "src" / modul).read_text(
        encoding="utf-8")


def test_tahmin_kacinma_yasagi_kodda():
    """"Emin değilim" diye gün atlamak karneyi seçerek temizlemenin kapısıdır:
    her asof, her ufuk × kol için TAM OLARAK bir satır yazar (koşulsuz döngü)."""
    kaynak = inspect.getsource(tahmin.kaydet)
    assert "for ufuk_ad, h in k[\"ufuklar_gun\"].items():" in kaynak
    assert "continue" not in kaynak, "hüküm yazma döngüsünde atlama dalı var"
