"""Boşluk sınıflandırma: altyapı arızası mı, kaynak kalitesi mi? (DECISIONS #005)

Gerçek olay: 2026-07-22 raporu "545 dk kesinti" dedi ve arıza sanıldı; oysa
Actions tam zamanında çalışmıştı (çekim boşluğu 217 dk), boşluk truncgil'in
boş dönmesindendi. İki farklı olgu aynı kelimeyle raporlanınca yanlış alarm.
"""
from src.report import classify_gap

TOL = 270.0


def test_gap_within_tolerance_is_silent():
    seviye, mesaj = classify_gap(200, 180, TOL)
    assert seviye == "ok" and mesaj is None


def test_source_quality_not_reported_as_outage():
    """07-22 senaryosu: prim boşluğu büyük ama Actions sağlıklı → arıza DEĞİL."""
    seviye, mesaj = classify_gap(545, 217, TOL)
    assert seviye == "kaynak"
    assert "Actions düzenli çalıştı" in mesaj
    assert "kontrol edilmeli" not in mesaj          # yanlış alarm üretmemeli


def test_real_outage_still_warns():
    """Çekim de durmuşsa gerçek arıza — uyarı korunmalı."""
    seviye, mesaj = classify_gap(600, 590, TOL)
    assert seviye == "ariza"
    assert "GitHub Actions kontrol edilmeli" in mesaj


def test_unknown_collection_gap_defaults_to_warning():
    """Arşiv sağlığı okunamadıysa (None) güvenli tarafta kal: uyar."""
    seviye, mesaj = classify_gap(600, None, TOL)
    assert seviye == "ariza" and mesaj is not None


def test_boundary_equal_tolerance_is_ok():
    seviye, _ = classify_gap(TOL, TOL, TOL)
    assert seviye == "ok"
