"""Saf çekirdeğin MATEMATİKSEL değişmezleri (property testleri).

Var olan testler çoğunlukla "şu girdiye şu çıktı" biçiminde — doğru ama kırılgan
bir zırh: bir formül yeniden yazılırken tek örnek tesadüfen tutabilir. Buradaki
testler formülün TAŞIMASI GEREKEN ÖZELLİĞİ sınar ve rastgele yüzlerce girdiyle
koşar (tohum sabit → tekrarlanabilir, "bazen kırmızı" test yok).

En önemli özellik **ölçek değişmezliği**: bu projenin amaç fonksiyonu TL değil
GRAM (ADR #007-A). Gram uzayında ölçen bir formül, tüm TL fiyatları k katına
çıkarıldığında AYNI sonucu vermek zorundadır — çünkü TL enflasyonu bir oran
metriğinde sadeleşir. Bir gün biri `gram_carry_gain_pct`'i "sadeleştirip" fark
tabanlı (mutlak TL) hâle getirirse hiçbir örnek-testi düşmez ama proje ölçtüğünü
sandığı şeyi ölçmez olur. Bu test düşer.

Rastgelelik neden güvenli: `random.Random(...)` sabit tohumla; her koşum aynı
girdi kümesini üretir. Ağ, DB, dosya yok.
"""
from __future__ import annotations

import math
import random

import pytest

from src import calc, chart, gram, ozellikler as oz, tahmin, util

CFG = util.load_config()
RT = 1.20                      # temsili gidiş-dönüş maliyeti (banka_hesap ölçümü)


def _rnd(tohum: int) -> random.Random:
    return random.Random(tohum)


def _seri(r: random.Random, n: int, taban: float = 1000.0,
          egim: float = 0.0002, gurultu: float = 0.01) -> list[float]:
    """Sürüklenen + gürültülü pozitif fiyat serisi."""
    out, p = [], taban
    for _ in range(n):
        p *= (1 + egim + r.gauss(0, gurultu))
        out.append(max(p, 1e-6))
    return out


# ============================================================ gram uzayı
def test_carry_kazanci_TL_olceginden_bagimsiz():
    """KİLİT TEST. Amaç fonksiyonu GRAM; TL ölçeği sonucu değiştirmemeli.

    100 gramla başlayıp 108 gram bitirmek TL'nin kaç olduğuna bağlı değildir.
    Formül fark tabanlı (mutlak TL) hâle gelirse bu test düşer.
    """
    r = _rnd(1)
    for _ in range(300):
        giris, cikis = r.uniform(100, 9000), r.uniform(100, 9000)
        faiz, gun = r.uniform(0, 60), r.randint(1, 400)
        k = r.choice([0.01, 0.5, 3.0, 1000.0])
        a = gram.gram_carry_gain_pct(giris, cikis, faiz, gun, 15.0)
        b = gram.gram_carry_gain_pct(giris * k, cikis * k, faiz, gun, 15.0)
        assert a == pytest.approx(b, rel=1e-9), f"ölçek {k} sonucu değiştirdi"


def test_carry_cikis_fiyatinda_azalan_giriste_artan():
    """Satıp geri almak: çıkış fiyatı düştükçe daha çok gram alırsın."""
    r = _rnd(2)
    for _ in range(200):
        giris, cikis = r.uniform(500, 8000), r.uniform(500, 8000)
        d = gram.gram_carry_gain_pct(giris, cikis, 40.0, 30, 15.0)
        assert gram.gram_carry_gain_pct(giris, cikis * 1.05, 40.0, 30, 15.0) < d
        assert gram.gram_carry_gain_pct(giris * 1.05, cikis, 40.0, 30, 15.0) > d


def test_carry_faiz_ihmal_edilirse_sat_haksiz_kotu_gorunur():
    """Mevduat faizi ŞART (ADR #007-B): onsuz ölçüm SAT'ı ~0.8p haksız yere
    kötü gösterir. Faizsiz sonuç DAİMA faizli sonuçtan küçük olmalı."""
    r = _rnd(3)
    for _ in range(200):
        giris, cikis = r.uniform(500, 8000), r.uniform(500, 8000)
        gun = r.randint(5, 200)
        faizli = gram.gram_carry_gain_pct(giris, cikis, 45.0, gun, 15.0)
        faizsiz = gram.gram_carry_gain_pct(giris, cikis, None, gun, 15.0)
        assert faizsiz < faizli


def test_carry_yatay_fiyat_faizsiz_sifir():
    """Sıfır noktası fiyat sabitliği DEĞİL carry-nötr noktadır; faiz yoksa
    yatay fiyat tam olarak 0 vermeli."""
    assert gram.gram_carry_gain_pct(6000.0, 6000.0, None, 30, 15.0) == \
        pytest.approx(0.0)
    assert gram.gram_carry_gain_pct(6000.0, 6000.0, 0.0, 30, 15.0) == \
        pytest.approx(0.0)


def test_carry_bozuk_fiyatta_none():
    for g, c in ((0.0, 100.0), (100.0, 0.0), (None, 100.0), (100.0, None)):
        assert gram.gram_carry_gain_pct(g, c, 40.0, 30, 15.0) is None


def test_net_mevduat_faizi_sürede_dogrusal():
    """Basit (bileşiksiz) oran: iki katı süre iki katı getiri. Bileşik hâle
    getirilirse taktik eşiği sessizce değişir."""
    r = _rnd(4)
    for _ in range(100):
        brut, stopaj = r.uniform(5, 80), r.uniform(0, 40)
        g = r.randint(1, 180)
        assert gram.net_mevduat_faizi(brut, stopaj, 2 * g) == pytest.approx(
            2 * gram.net_mevduat_faizi(brut, stopaj, g))


def test_net_mevduat_faizi_stopajda_azalan():
    onceki = None
    for stopaj in (0.0, 10.0, 15.0, 30.0, 100.0):
        v = gram.net_mevduat_faizi(45.0, stopaj, 365)
        if onceki is not None:
            assert v < onceki
        onceki = v
    assert gram.net_mevduat_faizi(45.0, 100.0, 365) == pytest.approx(0.0)


# ============================================================ hüküm doğruluğu
def test_hukum_dogru_mu_tek_esikte_donuyor():
    """KİLİT TEST. Tek eşik = gidiş-dönüş maliyeti; ikinci bir eşik (ATR ölü
    bandı) BİLEREK yok — ayarlanabilir eşik, karneyi güzelleştirmek için
    oynanabilir bir koldur."""
    r = _rnd(5)
    for _ in range(500):
        kazanc = r.uniform(-40, 40)
        sat = gram.hukum_dogru_mu("SAT_25", kazanc, RT)
        tut = gram.hukum_dogru_mu("TUT", kazanc, RT)
        assert sat is (kazanc > RT)
        assert tut is not sat, "TUT, SAT'ın tam tümleyeni olmalı"


def test_hukum_dogru_mu_SAT_olmayan_her_hukum_TUT_gibi():
    """L-010'un kaynağı: `SAT*` olmayan HER hüküm tıpatıp `TUT` cevabı alır.

    Bu bir hata değil tanımın sonucudur — ama karnenin `olculebilir_mi`
    bayrağına neden ihtiyaç duyduğunu açıklayan tam olarak budur. Kimlik
    burada KİLİTLENİYOR ki bayrak kaldırılırsa niye gerektiği görünsün.
    """
    r = _rnd(6)
    for _ in range(100):
        kazanc = r.uniform(-30, 30)
        taban = gram.hukum_dogru_mu("TUT", kazanc, RT)
        for h in ("AL", "AL_COK", "AL_AZ", "BEKLE", "TUT"):
            assert gram.hukum_dogru_mu(h, kazanc, RT) is taban


def test_hukum_dogru_mu_veri_yoksa_none():
    assert gram.hukum_dogru_mu("TUT", None, RT) is None
    assert gram.hukum_dogru_mu("SAT_25", None, RT) is None


def test_esik_taktik_ile_cekirdek_farki_tam_maliyet():
    """Çekirdek kolun eşiği DAİMA daha düşük ve fark TAM OLARAK gidiş-dönüş
    maliyeti (ADR #007-C: aynı bahsin ucuz ve pahalı versiyonu)."""
    r = _rnd(7)
    for _ in range(200):
        taban, rt = r.uniform(-20, 20), r.uniform(0, 5)
        t = gram.esik_pct(taban, rt, "taktik")
        c = gram.esik_pct(taban, rt, "cekirdek")
        assert t - c == pytest.approx(rt)
        assert c == pytest.approx(abs(taban))
        assert t >= c >= 0


def test_gram_etkisi_satmayan_hukum_sifir():
    """ASIL METRİK gram etkisi: satılmadıysa gram sayısı değişmez."""
    for h in ("TUT", "AL", "AL_COK", "AL_AZ", "BEKLE"):
        assert tahmin.gram_etkisi(h, 25.0, RT) == 0.0
        assert tahmin.gram_etkisi(h, -25.0, RT) == 0.0


def test_gram_etkisi_kismi_sat_oranli_ve_maliyet_dusulmus():
    r = _rnd(8)
    for _ in range(200):
        kazanc = r.uniform(-30, 30)
        assert tahmin.gram_etkisi("SAT_25", kazanc, RT) == pytest.approx(
            (kazanc - RT) * 0.25)
        assert tahmin.gram_etkisi("SAT_50", kazanc, RT) == pytest.approx(
            (kazanc - RT) * 0.50)
        # oran okunamazsa tam pozisyon varsayılır (güvenli taraf: maliyeti tam yaz)
        assert tahmin.gram_etkisi("SAT", kazanc, RT) == pytest.approx(kazanc - RT)


def test_gram_etkisi_isaret_maliyette_donuyor():
    assert tahmin.gram_etkisi("SAT_25", RT - 0.001, RT) < 0
    assert tahmin.gram_etkisi("SAT_25", RT + 0.001, RT) > 0
    assert tahmin.gram_etkisi("SAT_25", RT, RT) == pytest.approx(0.0)


# ============================================================ pencere/indeks
def test_pencere_ortalamasi_uc_gunun_ortalamasi():
    r = _rnd(9)
    for _ in range(100):
        seri = _seri(r, 40)
        i = r.randint(1, 38)
        beklenen = sum(seri[i - 1:i + 2]) / 3
        assert tahmin.pencere_ortalamasi(seri, i) == pytest.approx(beklenen)


def test_pencere_ortalamasi_sinirlarda_kirpar_ve_disarda_none():
    seri = [10.0, 20.0, 30.0]
    assert tahmin.pencere_ortalamasi(seri, 0) == pytest.approx(15.0)
    assert tahmin.pencere_ortalamasi(seri, 2) == pytest.approx(25.0)
    assert tahmin.pencere_ortalamasi(seri, 3) is None
    assert tahmin.pencere_ortalamasi(seri, -1) is None
    assert tahmin.pencere_ortalamasi([], 0) is None


def test_hedef_indeks_takvim_degil_islem_gunu_sayar():
    """Tatiller karneyi kaydırmasın: ufuk İŞLEM GÜNÜ cinsinden sayılır.

    Seride 2 haftalık boşluk var; 5 işlem günü sonrası takvimde 19 gün sonra
    olabilir ve doğru cevap indeks tabanlı olandır.
    """
    tarihler = ["2026-01-05", "2026-01-06", "2026-01-07",
                "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29"]
    assert tahmin.hedef_indeks(tarihler, "2026-01-05", 5) == 5
    assert tarihler[5] == "2026-01-28"
    assert tahmin.hedef_indeks(tarihler, "2026-01-05", 99) is None


def test_hedef_indeks_asof_islem_gunu_degilse_oncesini_alir():
    """asof hafta sonuna düşerse (veri yok) bir önceki işlem günü kullanılır."""
    tarihler = ["2026-01-05", "2026-01-06", "2026-01-09", "2026-01-12"]
    assert tahmin.hedef_indeks(tarihler, "2026-01-07", 1) == 2      # 01-06 → +1


def test_tahmini_hedef_tarih_hafta_sonunu_ekler():
    """Yalnız GÖSTERİM için: 5 işlem günü ≈ 7 takvim günü."""
    assert tahmin.tahmini_hedef_tarih("2026-01-05", 5) == "2026-01-12"
    assert tahmin.tahmini_hedef_tarih("2026-01-05", 21) == "2026-02-03"


def test_nonoverlap_pencereler_ortusmez_ve_fazi_korur():
    r = _rnd(10)
    for _ in range(50):
        n, h = r.randint(20, 400), r.randint(2, 40)
        faz = r.randint(0, h - 1)
        pencereler = list(gram.nonoverlap_windows(n, h, faz))
        if not pencereler:
            continue
        assert pencereler[0][0] == faz
        for (i1, j1), (i2, _) in zip(pencereler, pencereler[1:]):
            assert j1 == i2, "pencereler örtüşüyor ya da boşluk var"
        for i, j in pencereler:
            assert 0 <= i < j < n
            assert j - i == h


def test_faz_eslemesi_havuz_ve_faz_sayilari_tutarli():
    """Havuz N'i horizon kat şişkindir ve BAĞIMSIZ DEĞİLDİR; istatistiksel güç
    `n_bagimsiz`'dan okunur. İkisinin karışması N'i horizon kat büyük gösterir."""
    r = _rnd(11)
    seri = _seri(r, 300)
    h = 21
    s = gram.phase_matched_baseline(len(seri), h,
                                    lambda i, j: (seri[j] / seri[i] - 1) * 100)
    assert s["yeterli"] is True
    assert s["n_havuz"] > s["n_bagimsiz"]
    assert s["n_havuz"] <= s["n_bagimsiz"] * h + h
    assert s["en_kotu"] <= s["medyan"] <= s["en_iyi"]
    assert 0.0 <= s["kazanma_pct"] <= 100.0
    assert s["yayilim"] >= 0.0


def test_faz_eslemesi_sabit_egimde_faz_farki_uretmez():
    """Faz artefaktı ölçümün kendisinden gelmeli, kurgudan değil: sabit oranlı
    büyümede tüm fazlar aynı sonucu verir → yayılım 0."""
    seri = [1000.0 * (1.001 ** i) for i in range(200)]
    s = gram.phase_matched_baseline(len(seri), 10,
                                   lambda i, j: (seri[j] / seri[i] - 1) * 100)
    assert s["yayilim"] == pytest.approx(0.0, abs=1e-9)
    assert s["faz_0_ortalama"] == pytest.approx(s["ortalama"], abs=1e-9)


# ============================================================ calc
def test_zscore_kaydirma_ve_olcek_degismez():
    """z-skor konumsal bir ölçü: seriye sabit eklemek ya da hepsini k ile
    çarpmak z'yi DEĞİŞTİRMEZ. Değişirse eşik (|z|>2) sessizce kayar."""
    r = _rnd(12)
    for _ in range(100):
        tarihce = [r.uniform(-5, 5) for _ in range(80)]
        deger = r.uniform(-5, 5)
        temel = calc.zscore(tarihce, deger, 60).value
        c = r.uniform(-100, 100)
        k = r.choice([0.1, 2.0, 50.0])
        assert calc.zscore([x + c for x in tarihce], deger + c, 60).value == \
            pytest.approx(temel)
        assert calc.zscore([x * k for x in tarihce], deger * k, 60).value == \
            pytest.approx(temel)


def test_zscore_kapisi_ve_duz_seri():
    assert calc.zscore([1.0] * 59, 1.0, 60).status == "insufficient"
    assert calc.zscore([1.0] * 59, 1.0, 60).value is None
    duz = calc.zscore([1.0] * 60, 2.0, 60)
    assert duz.status == "flat" and duz.value is None


def test_prim_ve_teorik_gram_tersi_birbirinin():
    r = _rnd(13)
    for _ in range(200):
        teorik, prim = r.uniform(500, 9000), r.uniform(-20, 20)
        piyasa = calc.gram_from_theoretical(teorik, prim)
        assert calc.prim_pct(piyasa, teorik) == pytest.approx(prim)


def test_teorik_gram_dogrusal_ve_olcekli():
    r = _rnd(14)
    for _ in range(100):
        ons, usd = r.uniform(1000, 6000), r.uniform(10, 100)
        t = calc.theoretical_gram(ons, usd)
        assert calc.theoretical_gram(2 * ons, usd) == pytest.approx(2 * t)
        assert calc.theoretical_gram(ons, 3 * usd) == pytest.approx(3 * t)
        assert t == pytest.approx(ons / calc.TROY_OZ * usd)


def test_dekompozisyon_bilesenleri_tam_toplaniyor():
    """Δln(gram) = Δln(ons) + Δln(kur) + Δln(1+prim). Bileşenler TAM toplanmalı;
    yaklaşık toplanan bir ayrıştırma "kur mu ons mu çekti" sorusunu bozar."""
    r = _rnd(15)
    for _ in range(300):
        o0, u0 = r.uniform(1000, 5000), r.uniform(10, 60)
        o1, u1 = o0 * r.uniform(0.8, 1.2), u0 * r.uniform(0.8, 1.2)
        p0, p1 = r.uniform(-5, 5), r.uniform(-5, 5)
        d = calc.decompose(o0, u0, p0, o1, u1, p1)
        assert d.ons_pct + d.kur_pct + d.prim_pct == pytest.approx(d.total_pct)
        g0 = calc.gram_from_theoretical(calc.theoretical_gram(o0, u0), p0)
        g1 = calc.gram_from_theoretical(calc.theoretical_gram(o1, u1), p1)
        assert d.total_pct == pytest.approx(math.log(g1 / g0) * 100.0)


def test_makas_esit_fiyatta_sifir_ve_isaretli():
    assert calc.spread_pct(100.0, 100.0) == pytest.approx(0.0)
    assert calc.spread_pct(99.0, 101.0) > 0
    assert calc.spread_pct(101.0, 99.0) < 0
    assert calc.spread_pct(0.0, 0.0) == 0.0                # sıfıra bölme yok


def test_ceyrek_primi_has_icerigine_gore_olculuyor():
    """Sikke fiyatı tam has içeriği kadarsa prim SIFIR. Ölçek değişmezliği de
    korunmalı: gram fiyatı ve sikke fiyatı aynı katla çarpılırsa prim aynı."""
    c = CFG["instruments"]["coins"]["ceyrek"]
    gram_fiyat = 6000.0
    adil = c["gross_g"] * c["milyem"] * gram_fiyat
    assert calc.quarter_prim_pct(adil, gram_fiyat, c["gross_g"], c["milyem"]) == \
        pytest.approx(0.0)
    for k in (0.5, 2.0, 100.0):
        assert calc.quarter_prim_pct(adil * k * 1.02, gram_fiyat * k,
                                     c["gross_g"], c["milyem"]) == \
            pytest.approx(2.0, abs=1e-9)


# ============================================================ özellik katmanı
def test_getiri_ve_oynaklik_olcek_degismez():
    """Yüzde getiri ve log-getiri oynaklığı ölçekten bağımsızdır. Bir gün fiyat
    serisi TL'den başka bir birime çevrilirse özellik vektörü değişmemeli —
    aksi halde tarihsel replay ile canlı üretim ayrışır (ADR #007-G)."""
    r = _rnd(16)
    seri = _seri(r, 300)
    for k in (0.001, 7.0, 1e4):
        olcekli = [x * k for x in seri]
        assert oz.getiri_pct(olcekli, 21) == pytest.approx(oz.getiri_pct(seri, 21))
        assert oz.yillik_oynaklik_pct(olcekli, 60) == pytest.approx(
            oz.yillik_oynaklik_pct(seri, 60))
        assert oz.donchian_konum(olcekli, 55) == pytest.approx(
            oz.donchian_konum(seri, 55))


def test_donchian_daima_sifir_bir_arasinda():
    r = _rnd(17)
    for _ in range(100):
        seri = _seri(r, r.randint(60, 200), gurultu=0.05)
        v = oz.donchian_konum(seri, 55)
        assert v is not None and 0.0 <= v <= 1.0


def test_z_konum_kaydirma_degismez():
    r = _rnd(18)
    for _ in range(100):
        seri = [r.uniform(0, 10) for _ in range(60)]
        deger = r.uniform(0, 10)
        c = r.uniform(-50, 50)
        assert oz.z_konum(deger + c, [x + c for x in seri], 60) == pytest.approx(
            oz.z_konum(deger, seri, 60))


def test_getiri_yetersiz_veride_none_degil_yanlis_deger_dondurmuyor():
    """Pencere dolmadan sayı üretmek en sinsi hata: kısa seride uydurma bir
    momentum, karar motoruna gerçek gibi girer."""
    assert oz.getiri_pct([100.0] * 10, 21) is None
    assert oz.hareketli_ortalama([100.0] * 10, 200) is None
    assert oz.yillik_oynaklik_pct([100.0] * 10, 60) is None
    assert oz.donchian_konum([100.0] * 10, 55) is None
    assert oz.z_konum(1.0, [1.0] * 10, 60) is None


def test_gunler_once_takvim_gunu_geriye():
    assert oz.gunler_once("2026-03-05", 35) == "2026-01-29"
    assert oz.gunler_once("2026-01-01", 1) == "2025-12-31"


# ============================================================ göstergeler
def test_rsi_daima_sifir_yuz_arasinda():
    """RSI tanım gereği [0,100]; dışına çıkan bir uygulama etiketleri bozar
    (`label_rsi` eşikleri 30/70)."""
    r = _rnd(19)
    for _ in range(50):
        seri = _seri(r, 120, gurultu=r.uniform(0.001, 0.08))
        for v in chart.rsi(seri, 14):
            assert v is None or 0.0 <= v <= 100.0


def test_rsi_tek_yonlu_serilerde_uclara_gider():
    assert chart.rsi([100.0 + i for i in range(40)], 14)[-1] == pytest.approx(100.0)
    assert chart.rsi([100.0 - i for i in range(40)], 14)[-1] == pytest.approx(0.0)
    assert chart.rsi([100.0] * 40, 14)[-1] == pytest.approx(50.0)


def test_atr_negatif_olamaz_ve_aralikla_sinirli():
    r = _rnd(20)
    kapanis = _seri(r, 120)
    yuksek = [c * 1.01 for c in kapanis]
    dusuk = [c * 0.99 for c in kapanis]
    trs = [chart.true_range(yuksek[i], dusuk[i], kapanis[i - 1] if i else None)
           for i in range(len(kapanis))]
    for v in chart.atr(yuksek, dusuk, kapanis, 14):
        assert v is None or 0.0 <= v <= max(trs) + 1e-9


def test_true_range_bosluk_baskin():
    """Fiyat boşluğu (gap) günün H-L aralığından büyükse ATR onu görmeli."""
    assert chart.true_range(110.0, 105.0, 100.0) == pytest.approx(10.0)
    assert chart.true_range(110.0, 105.0, None) == pytest.approx(5.0)


def test_bollinger_orta_bant_ortalama_pctb_sinirli():
    r = _rnd(21)
    seri = _seri(r, 80)
    for i, (mid, up, dn, pctb) in enumerate(chart.bollinger(seri, 20, 2.0)):
        if mid is None:
            continue
        assert mid == pytest.approx(sum(seri[i - 19:i + 1]) / 20)
        assert dn <= mid <= up
        assert pctb is None or -3.0 < pctb < 4.0


def test_bollinger_sabit_seride_pctb_none():
    """sd=0'da %B sonsuz olurdu; None dönmeli (etiketleyici None'ı biliyor)."""
    assert chart.bollinger([5.0] * 30, 20, 2.0)[-1][3] is None


# ============================================================ maliyet modeli
def test_gidis_donus_maliyet_siralamasi_olculen_ile_ayni():
    """ADR #007-B ölçümü: altins1 %0.40 < banka_hesap %1.20 < fiziki %3.00.

    Bu sıra taktik eşiğini doğrudan belirliyor (ALTINS1'e geçilirse eşik
    3.18p → 2.38p düşer, STATE backlog). Sıra bozulursa eşik yanlış hesaplanır.
    """
    a = gram.roundtrip_cost_pct(CFG, "altins1")
    b = gram.roundtrip_cost_pct(CFG, "banka_hesap")
    f = gram.roundtrip_cost_pct(CFG, "fiziki_gram")
    assert 0 < a < b < f
    assert a == pytest.approx(0.40, abs=0.05)
    assert b == pytest.approx(1.20, abs=0.05)
    assert f == pytest.approx(3.00, abs=0.05)


def test_altin_fonu_gidis_donus_sifir_ve_bu_dogru():
    """Fonun maliyeti giriş-çıkış makası değil, zamana yayılı yönetim ücreti;
    gidiş-dönüş kavramı ona uymuyor. 0 dönmesi doğru ve bilinçli."""
    assert gram.roundtrip_cost_pct(CFG, "altin_fonu") == pytest.approx(0.0)


def test_bilinmeyen_enstruman_sessizce_gecmiyor():
    """Yanlış enstrüman adı 0 maliyet üretirse taktik eşiği sıfırlanır."""
    with pytest.raises(ValueError):
        gram.roundtrip_cost_pct(CFG, "yok_boyle_bir_sey")


def test_enstruman_neti_altin_getirisinde_artan():
    from src import calculators
    for ad in calculators.INSTRUMENTS:
        onceki = None
        for getiri in (-20.0, 0.0, 15.0, 40.0):
            v = calculators.instrument_net(CFG, ad, 100000.0, 12, getiri)["net"]
            if onceki is not None:
                assert v > onceki, f"{ad}: net getiri altın getirisiyle artmıyor"
            onceki = v


def test_bilezik_iscilik_geri_satista_yaniyor():
    r = _rnd(22)
    for _ in range(50):
        brut, isc, fiyat = r.uniform(1, 50), r.uniform(0, 40), r.uniform(1000, 9000)
        s = CFG["instruments"]["coins"]["ceyrek"]["milyem"]
        from src import calculators
        res = calculators.bilezik_basabas(CFG, brut, isc, fiyat, milyem=s)
        assert res["odenen_toplam"] >= res["hurda_deger"]
        assert res["basabas_gereken_gram_yukselis_pct"] == pytest.approx(isc)
