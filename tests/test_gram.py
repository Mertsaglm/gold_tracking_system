"""Gram hakemi saf çekirdek testleri.

Bu testleri doğuran olay: sistem 10.5 yıl boyunca "sinyal üret ama doğruluğunu
ölçme" modunda çalıştı ve kullanıcı haklı olarak "bu proje işimi görmez" dedi.
Artık her hüküm gram uzayında ölçülüyor; ölçüm doğru değilse karne de yalan
olur. Bu yüzden metriğin kendisi elle hesaplanabilir örneklerle kilitlendi.
"""
import math

import pytest

from src import gram, util

CFG = util.load_config()


# ---------- gidiş-dönüş maliyeti ----------
def test_roundtrip_banka_hesabi():
    """0.5 alış + 0.5 satış makası + 0.2 BSMV, çarpımsal → %1.196."""
    assert gram.roundtrip_cost_pct(CFG, "banka_hesap") == pytest.approx(1.1955, abs=1e-3)


def test_roundtrip_altins1_daha_ucuz():
    """ALTINS1 banka hesabından belirgin ucuz — taktik eşiğini doğrudan düşürür."""
    assert gram.roundtrip_cost_pct(CFG, "altins1") < \
        gram.roundtrip_cost_pct(CFG, "banka_hesap")


def test_roundtrip_altin_fonu_sifir():
    """Fonun maliyeti zamana yayılı yönetim ücreti; gidiş-dönüş makası yok.
    0 dönmesi DOĞRU — docstring'deki uyarı bu davranışı belgeliyor."""
    assert gram.roundtrip_cost_pct(CFG, "altin_fonu") == 0.0


# ---------- gram carry ----------
def test_carry_fiyat_sabitken_faiz_kadar_kazandirir():
    """Gram fiyatı yatay + %36 brüt faiz + 21 gün → net %30.6 yıllık, 21 günde
    ~%1.76. Sıfır noktası fiyat sabitliği DEĞİL, carry-nötr nokta."""
    v = gram.gram_carry_gain_pct(1000.0, 1000.0, 36.0, 21, 15.0)
    beklenen = 36.0 * 0.85 / 100 * 21 / 365 * 100
    assert v == pytest.approx(beklenen, abs=1e-6)
    assert v > 0


def test_carry_fiyat_yukselirse_sat_kaybettirir():
    """Fiyat %10 yükseldiyse 1 ay faizi bunu kapatamaz → SAT gram kaybettirir."""
    assert gram.gram_carry_gain_pct(1000.0, 1100.0, 36.0, 21, 15.0) < 0


def test_carry_faizsiz_olcum_sati_haksiz_kotu_gosterir():
    """Mevduat faizi ihmal edilirse SAT sistematik olarak kötü görünür —
    bu yüzden faiz ŞART. Fark 1 ayda ~1.8 puan."""
    faizli = gram.gram_carry_gain_pct(1000.0, 1000.0, 36.0, 21, 15.0)
    faizsiz = gram.gram_carry_gain_pct(1000.0, 1000.0, None, 21, 15.0)
    assert faizsiz == 0.0
    assert faizli - faizsiz > 1.5


def test_carry_bozuk_fiyat_none():
    assert gram.gram_carry_gain_pct(0.0, 1000.0, 36.0, 21, 15.0) is None


# ---------- hüküm doğruluğu: üç bölge ----------
RT = 1.20


def test_hukum_sat_masrafini_cikardi():
    """kazanç > maliyet → SAT doğru, TUT yanlış."""
    assert gram.hukum_dogru_mu("SAT_50", 3.0, RT) is True
    assert gram.hukum_dogru_mu("TUT", 3.0, RT) is False


def test_hukum_orta_bolge_tut_lehine():
    """0 < kazanç < maliyet: SAT haklıydı ama masrafını ÇIKARMADI → TUT doğru.
    Bu bölge kritik; onsuz gürültü işlemler doğru sayılırdı."""
    assert gram.hukum_dogru_mu("SAT_25", 0.6, RT) is False
    assert gram.hukum_dogru_mu("TUT", 0.6, RT) is True


def test_hukum_kazanc_negatif_al_dogru():
    assert gram.hukum_dogru_mu("AL_COK", -2.0, RT) is True
    assert gram.hukum_dogru_mu("SAT_50", -2.0, RT) is False


def test_hukum_veri_yoksa_none():
    assert gram.hukum_dogru_mu("TUT", None, RT) is None


# ---------- eşik ----------
def test_esik_taktik_makasi_ekler_cekirdek_eklemez():
    """Aynı bahis, iki fiyat: taktik kol gidiş-dönüş öder, çekirdek ödemez."""
    assert gram.esik_pct(-1.99, RT, "taktik") == pytest.approx(3.19, abs=1e-6)
    assert gram.esik_pct(-1.99, RT, "cekirdek") == pytest.approx(1.99, abs=1e-6)


# ---------- faz eşleştirme ----------
def test_nonoverlap_pencereler_ortusmez():
    w = list(gram.nonoverlap_windows(100, 21, faz=0))
    assert w[0] == (0, 21)
    for (i0, j0), (i1, _) in zip(w, w[1:]):
        assert i1 >= j0          # bir pencerenin çıkışı sonrakinin girişinden sonra değil


def test_faz_esleme_sabit_egimde_faz_bagimsiz():
    """Düzgün üstel seride her faz aynı getiriyi verir → yayılım ~0.
    Faz artefaktı gerçek bir sinyal değil, örnekleme yan etkisidir."""
    n, h = 400, 21
    fiyat = [100.0 * (1.001 ** i) for i in range(n)]
    r = gram.phase_matched_baseline(
        n, h, lambda i, j: (fiyat[j] / fiyat[i] - 1.0) * 100.0)
    assert r["yeterli"]
    assert r["yayilim"] < 1e-6


def test_faz_esleme_dalgali_seride_yayilim_yakalar():
    """Testere dişli seride faz seçimi sonucu değiştirir; fonksiyon bunu
    'yayilim' olarak RAPORLAR — measure_edge'in sessizce yuttuğu artefakt."""
    n, h = 400, 20
    fiyat = [100.0 + 10.0 * math.sin(2 * math.pi * i / h) for i in range(n)]
    r = gram.phase_matched_baseline(
        n, h, lambda i, j: (fiyat[j] / fiyat[i] - 1.0) * 100.0)
    assert r["yeterli"]
    assert r["n_bagimsiz"] < r["n_havuz"]     # havuz N'i şişkin, bağımsız N gerçek


def test_faz_esleme_bos_seri():
    assert gram.phase_matched_baseline(5, 21, lambda i, j: None)["yeterli"] is False
