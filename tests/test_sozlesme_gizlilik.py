"""Gizlilik ve `.gitignore` zırhı — repo PUBLIC, sessizce bozulan koruma en tehlikelisi.

L-005 bu dosyanın varlık sebebi: `.gitignore`'a satır-sonu yorumu yazıldı
(`data/altin.sqlite   # binary izlenmez`), git satır-sonu yorumu desteklemediği
için yorum metni pattern'in parçası sayıldı ve **üç gizlilik kuralı sessizce
devre dışı kaldı**. Hiçbir hata çıkmadı. Dersin kuralı da orada yazılı:
"Düzenledikten sonra kuralları tek tek doğrula:
`git check-ignore -q <yol> && echo korunuyor || echo AÇIK`" — bu dosya o
doğrulamayı otomatikleştiriyor.

İki yön birlikte denetlenir, çünkü ikisi de kayıp üretir:
  - KORUNMALI: sır, kişisel profil, binary DB, sohbet export'u
  - İZLENMELİ: dump, raporlar, arşiv CSV'si, `ai/` hafızası — Actions stateless
    olduğu için izlenmeyen veri her gün yok olur; hafıza izlenmezse disk
    gidince devir paketi de gider (gitignore yorumunda yazılı olay).
"""
from __future__ import annotations

import subprocess

import pytest

from src import util
from tests.conftest import KOK

GITIGNORE = KOK / ".gitignore"

KORUNMALI = [
    ".env",
    "data/altin.sqlite",
    "data/altin.sqlite-wal",
    "ai/PROFILE.md",
    "telegram çıktısı.json",
    "logs/daily_job.log",
    "data/grafik.png",
    "data/trends_cache.json",
    ".claude/settings.json",
    "Proje Yardımcısı - Gold Tracking System/ai/PROFILE.md",
]

IZLENMELI = [
    "data/altin.sql",
    "data/archive/2026-07.csv",
    "data/alert_state.json",
    "data/zskor_prova.jsonl",
    "data/gram_engeli.json",
    "reports/rapor_2026-07-26.md",
    "AGENTS.md",
    "CLAUDE.md",
    "config.yaml",
    "ai/STATE.md",
    "ai/DECISIONS.md",
    "ai/LESSONS.md",
    "ai/PROJECT.md",
]

SIR_ADLARI = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "EVDS_API_KEY")


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(("git", "-C", str(KOK)) + args,
                          capture_output=True, text=True)


def _git_var() -> bool:
    return _git("rev-parse", "--git-dir").returncode == 0


pytestmark = pytest.mark.skipif(not _git_var(), reason="git deposu yok")


# ------------------------------------------------------- L-005: yorum tuzağı
def test_gitignore_satir_sonu_yorumu_yok():
    """KİLİT TEST (L-005). Yorum kendi satırında olmalı.

    `data/x   # açıklama` yazıldığında git bunu "data/x   # açıklama" adlı bir
    pattern sanır; kural sessizce hiçbir şeyi korumaz. Bir kez yaşandı ve üç
    gizlilik kuralını birden düşürdü.
    """
    hatali = []
    for no, satir in enumerate(GITIGNORE.read_text(encoding="utf-8").splitlines(), 1):
        s = satir.rstrip()
        if not s or s.lstrip().startswith("#"):
            continue
        if "#" in s:
            hatali.append(f"{no}: {s}")
    assert not hatali, (f".gitignore'da satır-sonu yorumu var (L-005): {hatali} — "
                        "yorumu kendi satırına al, yoksa kural sessizce ölür")


def test_gitignore_bos_pattern_yok():
    """Sadece boşluktan oluşan satır ya da tek başına `!` kuralı bozar."""
    for no, satir in enumerate(GITIGNORE.read_text(encoding="utf-8").splitlines(), 1):
        if satir.strip() in ("!", "/"):
            pytest.fail(f".gitignore:{no} anlamsız pattern: {satir!r}")


@pytest.mark.parametrize("yol", KORUNMALI)
def test_hassas_yol_gercekten_ignore_ediliyor(yol):
    """Dosyanın var olması gerekmiyor — kuralın ÇALIŞMASI gerekiyor."""
    assert _git("check-ignore", "-q", yol).returncode == 0, (
        f"{yol} artık ignore EDİLMİYOR → public repoya girebilir")


@pytest.mark.parametrize("yol", IZLENMELI)
def test_izlenmesi_gereken_yol_ignore_edilmiyor(yol):
    """Ters hata da veri kaybettirir: Actions stateless, izlenmeyen veri ölür.

    `Proje Yardımcısı/` klasörünün tamamı bir ara ignore'daydı ve devir
    paketinin hiçbir yedeği yoktu — gitignore'un kendi yorumunda yazılı.
    """
    assert _git("check-ignore", "-q", yol).returncode != 0, (
        f"{yol} ignore ediliyor → commit'lenmiyor, her Actions koşumunda kaybolur")


def test_hafiza_dosyalari_gercekten_izleniyor():
    """`ai/` hafızası ve kural köprüleri git'te KAYITLI olmalı.

    Bu dosyalar projenin araç-bağımsızlık planının tamamı (ADR #001/#002):
    Claude Code aboneliği bitince yeni araç bunları okuyarak devralacak.
    İzlenmiyorlarsa devir diye bir şey yok.
    """
    izlenen = set(_git("ls-files").stdout.splitlines())
    for zorunlu in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "config.yaml",
                    "ai/PROJECT.md", "ai/STATE.md", "ai/DECISIONS.md",
                    "ai/LESSONS.md", ".github/copilot-instructions.md"):
        assert zorunlu in izlenen, f"{zorunlu} git'te izlenmiyor"


def test_hassas_dosya_git_indeksinde_degil():
    """Kural doğru olsa bile dosya daha önce eklenmiş olabilir; `check-ignore`
    bunu görmez — index'e bakmak gerekir."""
    izlenen = _git("ls-files").stdout.splitlines()
    yasak = [y for y in izlenen
             if y == ".env" or y.endswith(".sqlite") or y == "ai/PROFILE.md"
             or y.startswith("logs/") or y.endswith("çıktısı.json")]
    assert not yasak, f"hassas dosyalar git'e girmiş: {yasak}"


# ------------------------------------------------------- sır sızıntısı
def _env_degerleri() -> dict:
    yol = KOK / ".env"
    if not yol.exists():
        return {}
    out = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if satir and not satir.startswith("#") and "=" in satir:
            k, v = satir.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if k.strip() in SIR_ADLARI and len(v) >= 4:
                out[k.strip()] = v
    return out


def test_izlenen_hicbir_dosyada_sir_degeri_yok():
    """Gerçek token/chat_id değerleri commit'li hiçbir dosyada geçmemeli.

    Değerler test çıktısına ASLA yazılmaz; yalnız hangi anahtarın hangi dosyada
    göründüğü bildirilir.
    """
    sirlar = _env_degerleri()
    if not sirlar:
        pytest.skip(".env yok (CI) — sızıntı taraması atlandı")
    bulundu = []
    for yol in _git("ls-files").stdout.splitlines():
        p = KOK / yol
        if not p.is_file() or p.stat().st_size > 20_000_000:
            continue
        try:
            metin = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ad, deger in sirlar.items():
            if deger in metin:
                bulundu.append(f"{yol} ← {ad}")
    assert not bulundu, f"SIR SIZINTISI (değerler gizlendi): {bulundu}"


def test_mask_pii_chat_idyi_maskeler(monkeypatch):
    """`save_report` bu fonksiyondan geçiyor — savunma katmanı çalışmalı."""
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    assert util.mask_pii("chat 123456789 raporu") == "chat <chat_id> raporu"
    assert util.mask_pii("") == ""
    assert util.mask_pii(None) is None


def test_outbox_chat_alani_kisaltilmis():
    """Giden mesaj arşivi repoda birikiyor (`outbox_enabled: true`); chat_id tam
    hâliyle yazılırsa public repoya kişisel kimlik girer."""
    yol = KOK / "data" / "telegram_outbox.jsonl"
    if not yol.exists():
        pytest.skip("outbox henüz yok")
    from tests.conftest import jsonl_oku
    for kayit in jsonl_oku(yol):
        assert len(str(kayit.get("chat", ""))) <= 3, (
            f"outbox'ta uzun chat kimliği: {kayit.get('ts_utc')}")


def test_raporlarda_chat_id_gecmiyor():
    """Commit'li raporlar Telegram'a giden metnin aynısı; maskeleme çalışmazsa
    kimlik repoya sızar."""
    sirlar = _env_degerleri()
    cid = sirlar.get("TELEGRAM_CHAT_ID")
    if not cid:
        pytest.skip(".env yok")
    kirli = [p.name for p in (KOK / "reports").glob("*.md")
             if cid in p.read_text(encoding="utf-8", errors="ignore")]
    assert not kirli, f"raporlarda chat_id var: {kirli}"


# ------------------------------------------------------- L-007: sessiz yan etki
def test_repo_scriptleri_kendiliginden_push_etmiyor():
    """L-007: repoda duran bir yedekleme script'i sonunda `git commit && git push`
    yapıyordu — kimseye sormadan. Kural: commit/push yalnız workflow'ların işi.

    Tarama Python İLE BİRLİKTE kabuk script'lerini ve systemd birimlerini de
    kapsıyor: olay tam olarak bir `.sh` dosyasında yaşandı, yalnız `.py`
    taramak dersi yarım uygulamak olurdu.
    """
    hedefler = (list((KOK / "src").glob("**/*.py"))
                + [p for p in (KOK / "scripts").glob("*") if p.is_file()]
                + [p for p in (KOK / "deploy").glob("*") if p.is_file()])
    assert len(hedefler) > 30, "tarama kapsamı çöktü"
    suphe = []
    for p in hedefler:
        try:
            metin = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Yorumlar ayıklanır: yasağı ANLATAN açıklama (backup.sh'ın başındaki
        # L-007 notu gibi) yasağın ihlali sayılmamalı.
        kod = "\n".join(s.split("#")[0] for s in metin.splitlines())
        for kalip in ("git commit", "git push", "git add"):
            if kalip in kod:
                suphe.append(f"{p.relative_to(KOK)}: {kalip}")
    assert not suphe, f"kod/script git'e yazıyor (L-007): {suphe}"
