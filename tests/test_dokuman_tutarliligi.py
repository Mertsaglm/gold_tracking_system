"""HAFIZA ↔ KOD tutarlılığı — devir paketinin çalışır kalması.

Bu projenin en kritik varlığı kod değil `ai/` klasörü. ADR #001/#002'nin tamamı
şu kısıta dayanıyor: *"Claude Code aboneliği bitince Codex/Antigravity/GLM/Kiro/
VSCode ile devam edilecek → araç-özel çözümden kaçın."* Yeni araç projeyi
`AGENTS.md` + `ai/` dosyalarını OKUYARAK devralacak. O dosyalar bozulursa devir
sessizce çalışmaz — L-004 tam bu: kural dosyası alt klasörde kaldığı için sistem
atıl kaldı, **hata vermedi**.

Testler dokümanın İÇERİĞİNİ yargılamaz (üslup Mert'in işi); yalnız devir için
gereken YAPININ ayakta olduğunu doğrular:

- kural köprüleri kökte ve AGENTS.md'ye işaret ediyor mu (L-004)
- oturum ritüelinin okuduğu bölümler (`TAKVİM`, `Sıradaki 3 İş`) yerinde mi
- ders/karar numara uzayı çakışmış mı (2026-07-27'de tam bu oldu: L-005)
- dokümanların vaat ettiği komutlar gerçekten var mı
"""
from __future__ import annotations

import re

import pytest

from tests.conftest import KOK

AI = KOK / "ai"
PAKET = KOK / "Proje Yardımcısı - Gold Tracking System" / "ai"

KOPRULER = {
    "CLAUDE.md": "Claude Code",
    "GEMINI.md": "Gemini",
    ".github/copilot-instructions.md": "VS Code / Copilot",
}

# Doküman "python -m src.X" diye bir komut vaat ediyorsa o modül var olmalı.
DOKUMANLAR = ["README.md", "PROJE-REHBERI.md", "AGENTS.md", "İZLEME.md",
              "ai/PROJECT.md", "ai/STATE.md", "ai/DECISIONS.md", "ai/LESSONS.md"]

# Telegram komut sözleşmesi (ai/PROJECT.md "Kapsam" bölümünde sayılı)
TELEGRAM_KOMUTLARI = ["/hukum", "/karne", "/durum", "/rapor", "/net", "/bilezik",
                      "/grafik", "/aipaket"]

# AGENTS.md §7 komut sözleşmesi — araç değişse de davranış aynı kalmalı
USTA_KOMUTLARI = ["/durum", "/baslat", "/tanis", "/karar", "/plan", "/kapat",
                  "/ders", "/ogret"]


def _oku(yol) -> str:
    return (KOK / yol).read_text(encoding="utf-8")


# ------------------------------------------------------------ L-004: yerleşim
def test_kanonik_kural_dosyasi_kokte():
    """Yanlış yerdeki doğru dosya = yok hükmünde. Hiçbir IDE alt klasördeki
    AGENTS.md'yi otomatik okumaz."""
    assert (KOK / "AGENTS.md").exists()
    metin = _oku("AGENTS.md")
    assert "USTA" in metin
    assert "Oturum Ritüeli" in metin


@pytest.mark.parametrize("dosya,arac", sorted(KOPRULER.items()))
def test_kopru_dosyalari_agents_mdye_isaret_ediyor(dosya, arac):
    """Köprüler İNCE olmalı: kural tek yerde (AGENTS.md), köprü yalnız işaret
    eder. Köprüye kural yazılırsa araçlar arası davranış ayrışır (ADR #002)."""
    yol = KOK / dosya
    assert yol.exists(), f"{arac} köprüsü yok"
    metin = yol.read_text(encoding="utf-8")
    assert "AGENTS.md" in metin, f"{dosya} AGENTS.md'ye işaret etmiyor"
    assert len(metin.splitlines()) < 40, (
        f"{dosya} köprü değil kural dosyasına dönüşmüş ({len(metin.splitlines())} satır)")


def test_paketteki_agents_md_kokle_BIREBIR_ayni():
    """KİLİT TEST. Devir paketindeki `AGENTS.md`, kökteki kanonik dosyanın
    taşınabilir ikizidir — ayrışırsa devralan araç ESKİ kuralları uygular.

    Paketin kendi README'si bu şartı yazıyor ("kökle birebir aynı olmalı") ve
    STATE.md senkron kontrolünü `diff` ile tarif ediyor; test onu otomatikleştirir.
    Kural değişikliği önce köke yazılır, sonra buraya kopyalanır.
    """
    if not (PAKET.parent / "AGENTS.md").exists():
        pytest.skip("devir paketi bu checkout'ta yok")
    assert (PAKET.parent / "AGENTS.md").read_text(encoding="utf-8") == \
        _oku("AGENTS.md"), (
            "kök ↔ paket AGENTS.md ayrıştı — `cp AGENTS.md '<paket>/AGENTS.md'` "
            "ile senkronla (kural değişikliği ÖNCE köke yazılır)")


@pytest.mark.parametrize("kopru", sorted(KOPRULER))
def test_paketteki_koprüler_de_ayni(kopru):
    """Köprüler de ikiz: yeni projeye tohumlanırken buradan kopyalanıyor."""
    paket_yolu = PAKET.parent / kopru
    if not paket_yolu.exists():
        pytest.skip(f"pakette {kopru} yok")
    assert paket_yolu.read_text(encoding="utf-8") == _oku(kopru)


def test_hafiza_dosyalarinin_hepsi_var():
    """Oturum ritüeli bu dört dosyayı okuyor; biri yoksa ritüel sessizce eksik
    çalışır (PROFILE.md gitignore'da olduğu için listede yok)."""
    for ad in ("PROJECT.md", "STATE.md", "DECISIONS.md", "LESSONS.md"):
        assert (AI / ad).exists(), f"ai/{ad} yok"


# ------------------------------------------------------------ STATE yapısı
def test_state_oturum_ritualinin_okudugu_bolumleri_iceriyor():
    """AGENTS.md §2/§6 bu bölümlere göre çalışıyor: TAKVİM tablosu olmadan
    "SENDE KALANLAR" sorulamaz, "Sıradaki 3 İş" olmadan oturum yönsüz kalır."""
    metin = _oku("ai/STATE.md")
    for bolum in ("TAKVİM", "SENDE KALANLAR", "Sıradaki 3 İş", "Backlog"):
        assert bolum in metin, f"STATE.md'de '{bolum}' bölümü yok"


def test_takvim_tablosu_kim_kolonunu_tasiyor():
    """👤/🤖 ayrımı olmadan "yalnız Mert yapabilir" işleri filtrelenemez ve
    sorulmazsa unutulur (AGENTS.md §2 kuralı)."""
    metin = _oku("ai/STATE.md")
    assert "| Kim |" in metin or "|:--:|" in metin
    assert "👤" in metin and "🤖" in metin


def test_state_kisa_kaliyor():
    """§8 hafıza disiplini: ~100 satır hedef, eskiyen içerik `ai/archive/`'e.
    Sınırsız büyüyen bir STATE.md okunmaz hâle gelir ve devir işlevini yitirir."""
    satir = len(_oku("ai/STATE.md").splitlines())
    assert satir < 200, (f"STATE.md {satir} satır — eskiyen bölümleri "
                         "ai/archive/STATE-YYYY-MM.md'ye taşı (§8)")
    assert (AI / "archive").exists(), "arşiv klasörü yok"


@pytest.mark.parametrize("ifade", ["geçen hafta", "geçen ay", "önümüzdeki hafta",
                                   "gelecek hafta", "gelecek ay", "birkaç gün önce"])
def test_hafizada_goreli_tarih_yok(ifade):
    """§8: "Tarihler daima mutlak yazılır (2026-07-23 gibi)". Göreli ifade
    aylar sonra okunduğunda anlamsızlaşır — devir paketinin işlevi tam da
    aylar sonra okunmak.

    Not: "yarın/bugün" kelimeleri MEKANİZMA anlatırken meşru ("bugünün tam barı
    yarın yazılıyor") — bu yüzden listede yok; yasak olan TARİH yerine geçen
    göreli ifadeler.
    """
    for ad in ("STATE.md", "DECISIONS.md", "PROJECT.md"):
        metin = (AI / ad).read_text(encoding="utf-8").lower()
        assert ifade not in metin, f"ai/{ad} göreli tarih içeriyor: '{ifade}'"


# ------------------------------------------------------------ numara uzayı
def _ders_numaralari(yol) -> list[int]:
    return [int(m) for m in re.findall(r"^## L-(\d+)", yol.read_text(encoding="utf-8"),
                                       re.MULTILINE)]


def test_ders_numaralari_dosya_icinde_tekil():
    """Aynı numarada iki ders = biri okunmaz."""
    for yol in (AI / "LESSONS.md", PAKET / "LESSONS.md"):
        if not yol.exists():
            continue
        no = _ders_numaralari(yol)
        assert len(no) == len(set(no)), f"{yol.name}: tekrar eden L numarası {no}"


def test_ders_numara_uzayi_iki_dosyada_ortak():
    """KİLİT TEST — 2026-07-27'de gerçekleşen çakışmanın zırhı.

    LESSONS.md'nin kendi uyarısı: "Bu dosya ile devir paketindeki LESSONS.md
    AYNI L-NNN numaralarını paylaşır." Yeni ders yalnız birine eklenirse
    numara uzayı ayrışır ve bir sonraki ders çakışır (L-005 sanıldı, oysa
    pakette L-005 başka bir dersti → L-009'a taşındı).
    """
    if not (PAKET / "LESSONS.md").exists():
        pytest.skip("devir paketi bu checkout'ta yok")
    kok_no = set(_ders_numaralari(AI / "LESSONS.md"))
    paket_no = set(_ders_numaralari(PAKET / "LESSONS.md"))
    assert kok_no == paket_no, (
        f"numara uzayı ayrıştı — yalnız kökte: {sorted(kok_no - paket_no)}, "
        f"yalnız pakette: {sorted(paket_no - kok_no)}")


def test_ders_numaralari_boslusuz_ve_birden_basliyor():
    """Boşluk, "acaba silinmiş bir ders mi vardı?" sorusu doğurur."""
    no = sorted(_ders_numaralari(AI / "LESSONS.md"))
    assert no, "hiç ders yok"
    assert no == list(range(1, max(no) + 1)), f"numara boşluğu var: {no}"


def test_adr_numaralari_tekil_ve_yeniden_eskiye():
    """DECISIONS.md kuralı: "En yeni karar en üste"."""
    metin = _oku("ai/DECISIONS.md")
    no = [int(m) for m in re.findall(r"^## #(\d+)", metin, re.MULTILINE)]
    assert no, "hiç ADR yok"
    assert len(no) == len(set(no)), f"tekrar eden ADR numarası: {no}"
    assert no == sorted(no, reverse=True), f"ADR sırası yeniden eskiye değil: {no}"
    assert no == list(range(max(no), 0, -1)), f"ADR numara boşluğu: {no}"


# ------------------------------------------------------------ komut sözleşmesi
@pytest.mark.parametrize("komut", USTA_KOMUTLARI)
def test_usta_komut_sozlesmesi_tanimli(komut):
    """§7: "Bunlar araç özelliği değil, senin sözleşmendir." Bir komut tablodan
    düşerse yeni araç onu bilmez ve davranış araca göre değişir."""
    assert f"`{komut}" in _oku("AGENTS.md"), f"{komut} komut tablosunda yok"


@pytest.mark.parametrize("komut", TELEGRAM_KOMUTLARI)
def test_belgelenen_telegram_komutunun_isleyicisi_var(komut):
    """KİLİT TEST. PROJECT.md kapsamında sayılan her komut botta ÇALIŞMALI.

    ADR #006-C'nin kalıbı: belgelenen ama bağlanmamış özellik. Kullanıcı komutu
    yazar, bot sessiz kalır — hiçbir hata da görünmez.
    """
    kaynak = (KOK / "src" / "telegram_bot.py").read_text(encoding="utf-8")
    assert f'text.startswith("{komut}")' in kaynak, f"{komut} işleyicisi yok"
    assert komut in _oku("ai/PROJECT.md"), f"{komut} PROJECT.md kapsamında yazılı değil"


def test_yardim_metni_tum_komutlari_listeliyor():
    """`/yardim` reklamı ile gerçek işleyiciler ayrışmamalı: olmayan bir komutu
    listelemek de, çalışan bir komutu saklamak da tutarsızlık."""
    kaynak = (KOK / "src" / "telegram_bot.py").read_text(encoding="utf-8")
    yardim = kaynak[kaynak.index('text.startswith("/yardim")'):]
    yardim = yardim[:yardim.index("except")]
    for komut in TELEGRAM_KOMUTLARI:
        assert komut in yardim, f"{komut} /yardim metninde yok"


def test_belgelenen_modul_komutlari_gercekten_var():
    """Dokümanların vaat ettiği `python -m src.X` modülleri var olmalı ve
    çalıştırılabilir bir giriş noktası (`__main__`) taşımalı."""
    eksik, girissiz = [], []
    for dosya in DOKUMANLAR:
        yol = KOK / dosya
        if not yol.exists():
            continue
        for modul in set(re.findall(r"python -m (src\.[a-z_]+)",
                                    yol.read_text(encoding="utf-8"))):
            p = KOK / (modul.replace(".", "/") + ".py")
            if not p.exists():
                eksik.append(f"{dosya} → {modul}")
            elif '__name__ == "__main__"' not in p.read_text(encoding="utf-8"):
                girissiz.append(f"{dosya} → {modul}")
    assert not eksik, f"belgelenen modül yok: {eksik}"
    assert not girissiz, f"belgelenen modülün CLI girişi yok: {girissiz}"


# ------------------------------------------------------------ ölçüm kültürü
def test_amac_fonksiyonu_dokumanda_gram():
    """ADR #007-A: amaç fonksiyonu TERMİNAL GRAM, TL getirisi değil. Bu cümle
    dokümandan silinirse sonraki model TL getirisini optimize etmeye başlar."""
    proje = _oku("ai/PROJECT.md")
    assert "GRAM" in proje.upper()
    assert "TL getirisi değil" in proje or "TL getirisi DEĞİL" in proje
    assert "gram" in _oku("config.yaml").lower()


def test_taktik_kolun_kapali_olmasi_dokumanda_gerekceli():
    """Kapalılık bir tercih değil ölçüm sonucu; gerekçe dokümanda kalmalı ki
    bir sonraki model "neden kapalı, açalım" demeden önce ölçümü görsün."""
    for dosya in ("ai/PROJECT.md", "ai/DECISIONS.md", "config.yaml"):
        metin = _oku(dosya)
        if "taktik" in metin.lower():
            break
    else:
        pytest.fail("taktik kol hiçbir dokümanda anlatılmıyor")
    kararlar = _oku("ai/DECISIONS.md")
    assert "doğuştan kapalı" in kararlar or "doğuştan KAPALI" in kararlar
    assert "-1.99" in kararlar or "−1.99" in kararlar, "ölçülen taban kayıtlı değil"


def test_izleme_dosyasi_kapiyi_ve_tarihleri_tasiyor():
    """`İZLEME.md` kullanıcının "ne zaman ne olacak" dosyası; kapı tarihi
    buradan okunuyor (STATE.md ile tutarlı olmalı)."""
    yol = KOK / "İZLEME.md"
    if not yol.exists():
        pytest.skip("İZLEME.md yok")
    metin = yol.read_text(encoding="utf-8")
    assert "60" in metin, "z-skor kapısı (60 gün) İZLEME.md'de yok"
    assert re.search(r"20\d\d-\d\d", metin), "mutlak tarih yok"
