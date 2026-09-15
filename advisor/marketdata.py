"""Herkese açık fiyat referansları; banka hesabına/emir servisine erişmez."""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from html import unescape
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Europe/Istanbul")


def tr_number(value):
    text = unescape(value).strip().replace("\u200b", "").replace("\xa0", "")
    return float(text.replace(".", "").replace(",", "."))


class SocketValues(HTMLParser):
    def __init__(self, key):
        super().__init__()
        self.key, self.active, self.values = key, None, {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("data-socket-key") == self.key:
            self.active = a.get("data-socket-attr")

    def handle_endtag(self, tag):
        if tag in {"span", "div", "td"}:
            self.active = None

    def handle_data(self, text):
        if self.active and text.strip() and self.active not in self.values:
            self.values[self.active] = text.strip()


def parse_gold(html, now, url):
    if "İş Bankası Gram Altın" not in html:
        raise ValueError("Sayfada İş Bankası ürün kimliği doğrulanamadı.")
    parser = SocketValues("4-gram-altin")
    parser.feed(html)
    v = parser.values
    bid, ask = tr_number(v["bid"]), tr_number(v["ask"])
    stamp = v.get("ts", "")
    if not re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", stamp):
        raise ValueError("Altın kotasyonu saat damgası yok.")
    local = now.astimezone(IST)
    hh, mm = map(int, stamp.split(":")[:2])
    quoted = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if quoted > local + timedelta(minutes=1):
        quoted -= timedelta(days=1)
    return {"GRAM": {"symbol": "GRAM", "bid": bid, "ask": ask,
                     "quoted_at": quoted.astimezone(timezone.utc).isoformat(),
                     "observed_at": now.isoformat(), "source": "İş Bankası / Döviz.com",
                     "url": url, "kind": "bank_reference", "timestamp_kind": "time_only",
                     "note": "İkincil kaynak; İşCep kişisel kotasyonu değildir. Kaynak saati gün içi kabul edilir."}}


def parse_stocks(html, now, url, symbols):
    # İş Yatırım'ın sayfa üretim zamanı; fiyatın bireysel işlem zamanı DEĞİLDİR.
    stamp = re.search(r"önbellek profili kullanılarak işlendi, saat:\s*([\dT:\-]+)", html)
    if not stamp:
        raise ValueError("İş Yatırım sayfa zaman damgası bulunamadı.")
    published = datetime.fromisoformat(stamp.group(1)).replace(tzinfo=IST)
    table = html.split('id="allStockTable"', 1)
    if len(table) != 2:
        raise ValueError("İş Yatırım hisse tablosu bulunamadı.")
    table = table[1].split("</table>", 1)[0]
    rows = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, flags=re.S | re.I):
        match = re.search(r"sirket-karti\.aspx\?hisse=([A-Z0-9]+)", row)
        if not match or match.group(1) not in symbols:
            continue
        cols = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.S | re.I)
        try:
            price = tr_number(re.sub(r"<[^>]*>", "", cols[1]))
            import math
            if not math.isfinite(price) or price <= 0:
                continue
        except (ValueError, IndexError):
            continue
        symbol = match.group(1)
        rows[symbol] = {"symbol": symbol, "bid": price, "ask": price,
                        "quoted_at": published.astimezone(timezone.utc).isoformat(),
                        "observed_at": now.isoformat(), "source": "İş Yatırım",
                        "url": url, "kind": "delayed_last", "timestamp_kind": "page_cache",
                        "note": "En az 15 dk gecikmeli son fiyat. Emir defteri yok; dolum kayma eklenmiş sanal referanstır."}
    if not rows:
        raise ValueError("İstenen hisseler fiyat tablosunda yok.")
    return rows


def fetch(cfg, symbols, now):
    market = cfg["market"]
    url = cfg["sources"]["stocks" if market == "bist" else "gold"]
    r = requests.get(url, timeout=(8, 20))
    r.raise_for_status()
    if market == 'bist':
        return parse_stocks(r.text, now, url, symbols)
    quotes = parse_gold(r.text, now, url)
    try:
        import yfinance as yf
        legs = {}
        for symbol in ('GC=F', 'TRY=X'):
            bars = yf.Ticker(symbol).history(period='5d', interval='5m', auto_adjust=False, raise_errors=True)
            if bars.empty:
                raise ValueError('Gram referansı boş.')
            stamp = bars.index[-1].to_pydatetime()
            if not 0 <= (now - stamp).total_seconds() <= cfg['max_quote_age_minutes'] * 60:
                raise ValueError('Gram referansı eski.')
            legs[symbol] = {'price': float(bars.Close.iloc[-1]), 'at': stamp.isoformat()}
        quotes['GRAM']['reference_price'] = legs['GC=F']['price'] * legs['TRY=X']['price'] / 31.1034768
        quotes['GRAM']['reference_legs'] = legs
        quotes['GRAM']['reference_note'] = 'Geçmiş GC=F×kur serisinin gün içi karşılığı; banka makası ayrı hesaplanır.'
    except Exception as exc:
        quotes['GRAM']['reference_error'] = type(exc).__name__
    return quotes


def usable(quote, cfg, now, holidays=(), *, allow_wide_spread=False):
    if not quote:
        return "Fiyat kaynağına ulaşılamadı."
    try:
        import math
        bid, ask = float(quote["bid"]), float(quote["ask"])
        if not all(math.isfinite(x) and x > 0 for x in (bid, ask)) or ask < bid:
            return "Alış/satış fiyatı geçersiz."
        stamp = datetime.fromisoformat(quote["quoted_at"])
        if stamp.tzinfo is None:
            return "Fiyatın saat dilimi belirsiz."
        age = (now - stamp).total_seconds() / 60
        if age < -1 or age > cfg["max_quote_age_minutes"]:
            return "Fiyat bayat veya geleceğe ait."
        local = now.astimezone(IST)
        if local.weekday() > 4 or local.date().isoformat() in holidays:
            return "Piyasa tatilinde yeni sanal işlem yapılmaz."
        # Banka dışı saatlerde genişleyen makas ve belirsiz BIST referansı kullanılmaz.
        if not (10 * 60 + 15 <= local.hour * 60 + local.minute <= 17 * 60 + 45):
            return "İşlem penceresi dışında; uygun saat bekleniyor."
        if stamp.astimezone(IST).date() != local.date():
            return "Önceki güne ait kotasyon."
        if not allow_wide_spread and (ask / bid - 1) * 100 > cfg["max_spread_pct"]:
            return "Banka makası bugün fazla geniş."
    except (KeyError, TypeError, ValueError):
        return "Fiyat kaydı doğrulanamadı."
    return None
