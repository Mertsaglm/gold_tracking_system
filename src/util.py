"""Ortak yardımcılar: TR sayı ayrıştırma, zaman, config/env yükleme."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent


# ---------- Zaman ----------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def tz_local(offset_hours: int = 3) -> timezone:
    return timezone(timedelta(hours=offset_hours))


def to_local(dt: datetime, offset_hours: int = 3) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz_local(offset_hours))


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def slot_gunu(cron_utc: str, offset_hours: int = 3,
              simdi: Optional[datetime] = None) -> str:
    """GECMIS en son zamanlanmis cron slot'unun YEREL takvim gunu (ISO).

    ⚠ NEDEN VAR — "bu kosu HANGI GUN icin?" sorusunun tek dogru cevabi.

    `local_today()` isin BASLADIGI ani okur. GitHub cron GECIKIR (bu repoda
    olculdu: nominal */15 gercekte 1-3,5 saatlik ritim; gunluk iste 8,5 saatlik
    gecikme gorulda). Gecikme TR gece yarisini asinca is "ertesi gunun isi"
    gibi davranir ve UC ayri sessiz ariza uretir — hepsi 2026-08/09'da yasandi:

      * `rapor_<gun>.md` ertesi gunun adiyla yazilir. 2026-08-31 slotu
        09-01T00:02 TR'de kosup `rapor_2026-09-01.md`yi yazdi; ayni gun
        21:47'de gercek 09-01 kosusu onu EZDI. 08-31 raporu KAYIP,
        `rapor_2026-08-27.md` ise hic olusmadi.
      * `weekday` kayar: 08-31 (Pazartesi) slotu Sali'ye tasindi ve
        Pazartesi MUTABAKATI o hafta hic kosmadi.
      * `son_kapali_gun` bir gun ileri kayar; atlanan gun icin tahmin HIC
        yazilmaz. Olculdu: `predictions`ta asof=2026-08-26 YOK.

    Slot saatinden turetilen cevap gecikmeden BAGIMSIZDIR: is 8 saat de
    gecikse, gece yarisini da assa "hangi slot icin kostum" degismez.

    `cron_utc` "HH:MM" (UTC) — kaynagi `config.schedule`, ve o deger
    `.github/workflows/daily.yml` cron'una TESTLE baglidir
    (`test_sozlesme_workflow.py`), yani ikinci bir gercek kaynak olusamaz.
    """
    now = simdi or utcnow()
    sa, dk = (int(x) for x in cron_utc.split(":"))
    slot = now.replace(hour=sa, minute=dk, second=0, microsecond=0)
    if now < slot:
        slot -= timedelta(days=1)
    return to_local(slot, offset_hours).strftime("%Y-%m-%d")


def local_today(offset_hours: int = 3) -> str:
    """Yerel (TR) takvim günü, ISO. `asof` kapanmışlık kapısının referansı.

    UTC değil YEREL gün: GC=F ~21:00 UTC (00:00 TR) kapanıyor, yani D günü barı
    ancak D+1'in TR gününde tam kapanmış sayılır. UTC kullanmak, TR'de gece
    01:00'de koşan bir işte o günün yarım barını "kapanmış" gösterirdi.
    """
    return to_local(utcnow(), offset_hours).date().isoformat()


# ---------- TR sayı ayrıştırma ----------
def parse_tr_number(s: Any) -> Optional[float]:
    """'6.247,17' -> 6247.17 ; '46,8366' -> 46.8366 ; '%-0,34' -> -0.34.

    '$' de düşer: Truncgil ons alanını '$4.376,71' biçiminde veriyor (TL
    alanlarında para birimi işareti yok). İşaret düşmeseydi ons sessizce None
    kalırdı ve prim yfinance'in vadeli kontratına geri düşerdi.
    """
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace("%", "").replace("$", "").replace(" ", "").replace(" ", "")
    if t in ("", "-", "N/A", "null", "None"):
        return None
    # nokta = binlik ayraç, virgül = ondalık
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# ---------- Config / env ----------
def load_config(path: str | Path = ROOT / "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env(path: str | Path = ROOT / ".env") -> None:
    """Basit .env yükleyici (harici bağımlılık yok) + SSL cacert ASCII-path düzeltmesi."""
    _ensure_ascii_cert()
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _ensure_ascii_cert() -> None:
    """Proje yolu non-ASCII ise (ör. 'altın') curl_cffi cacert'i açamaz.
    certifi cacert'ini ASCII temp yola kopyalayıp env değişkenlerini ayarlar."""
    try:
        import certifi
        src = certifi.where()
        if src.isascii():
            return  # sorun yok
        import shutil
        import tempfile
        dst = Path(tempfile.gettempdir()) / "altin_cacert.pem"
        if not str(dst).isascii():
            return  # temp de non-ASCII ise yapacak bir şey yok
        if not dst.exists():
            shutil.copy(src, dst)
        for var in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
            os.environ.setdefault(var, str(dst))
    except Exception:
        pass  # cert düzeltmesi başarısızsa sessizce devam


def env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def abspath(rel: str | Path) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p


def mask_pii(text: str) -> str:
    """Rapor/çıktıya kaçmış olabilecek kişisel değerleri (chat_id) maskeler.
    Repo public — commit'lenen hiçbir metinde chat_id görünmemeli (savunma katmanı)."""
    if not text:
        return text
    cid = os.environ.get("TELEGRAM_CHAT_ID")
    if cid and cid in text:
        text = text.replace(cid, "<chat_id>")
    return text


def write_json(path: str | Path, data: Any) -> None:
    with open(abspath(path), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: str | Path, default: Any = None) -> Any:
    p = abspath(path)
    if not p.exists():
        return default
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)
