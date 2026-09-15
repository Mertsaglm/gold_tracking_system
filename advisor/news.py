"""Resmî kaynaklardan tarihli gündem; erişim hatası 'haber yok' sayılmaz."""
from __future__ import annotations

import email.utils
import calendar
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests

FEEDS = {
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "ECB": "https://www.ecb.europa.eu/rss/press.html",
    'TCMB': 'https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB%2BTR/Bottom%2BMenu/Diger/RSS/Basin%2BDuyurulari',
}
FOMC = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'


def atom_items(root):
    ns = {'a':'http://www.w3.org/2005/Atom'}
    months = ['Oca','Şub','Mar','Nis','May','Haz','Tem','Ağu','Eyl','Eki','Kas','Ara']
    for item in root.findall('a:entry', ns):
        stamp = item.findtext('a:published', '', ns).strip()
        parts = stamp.split()
        if len(parts) != 4 or parts[1] not in months:
            continue
        day, month, year, clock = parts
        parsed = datetime.fromisoformat(f'{year}-{months.index(month)+1:02d}-{int(day):02d}T{clock}').replace(tzinfo=ZoneInfo('Europe/Istanbul'))
        link = item.find('a:link', ns)
        url = urljoin('https://www.tcmb.gov.tr', link.get('href','')) if link is not None else ''
        yield item.findtext('a:title','',ns), url.replace('http://www.tcmb.gov.tr','https://www.tcmb.gov.tr'), parsed


def fomc_calendar(html, today):
    meetings = []
    years = list(re.finditer(r'>(20\d{2}) FOMC Meetings</a>', html))
    for i, match in enumerate(years):
        block = html[match.end():years[i+1].start() if i+1<len(years) else len(html)]
        pattern = r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)'
        for month, days in re.findall(pattern, block, re.S):
            month = month.strip().split('/')[-1]
            if month not in calendar.month_name:
                continue
            numbers = re.findall(r'\d{1,2}', days)
            if not numbers:
                continue
            end = date(int(match[1]), list(calendar.month_name).index(month), int(numbers[-1]))
            if today <= end <= today + timedelta(days=7):
                meetings.append({'date':end.isoformat(),'title':'Fed faiz kararı / FOMC toplantısının son günü','source':'Federal Reserve','url':FOMC})
    if not years:
        raise ValueError('Fed takvimi çözümlenemedi.')
    return sorted(meetings, key=lambda x:x['date'])


def collect(con, market, now, fetch_external=True):
    items, status = [], []
    if market == "bist":
        since = (now - timedelta(days=7)).isoformat()
        for r in con.execute("SELECT DISTINCT title,url,published_utc FROM disclosures WHERE published_utc>=? AND published_utc<=? ORDER BY published_utc DESC LIMIT 30", (since, now.isoformat())):
            items.append({"title": r[0], "url": r[1], "published_at": r[2], "source": "KAP"})
        status.append({"source": "KAP", "ok": bool(items), "detail": "Üretim arşivindeki tarihli bildirimler" if items else "Son hafta arşivinde bildirim bulunamadı; güncellik doğrulanamadı."})
    for name, url in FEEDS.items():
        if not fetch_external:
            status.append({"source": name, "ok": False, "detail": "Çevrimdışı inceleme"})
            continue
        try:
            r = requests.get(url, timeout=(5, 10))
            r.raise_for_status()
            root = ET.fromstring(r.content)
            accepted = 0
            if name == 'TCMB':
                entries = list(atom_items(root))
            else:
                entries = [(item.findtext('title',''), item.findtext('link',''), email.utils.parsedate_to_datetime(item.findtext('pubDate',''))) for item in root.findall('.//item')]
            if not entries:
                raise ValueError('Haber beslemesi boş veya biçimi değişmiş.')
            for title, link, stamp in entries:
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                if now - timedelta(days=7) <= stamp <= now:
                    items.append({"title": title[:250], "url": link,
                                  "published_at": stamp.isoformat(), "source": name})
                    accepted += 1
            status.append({"source": name, "ok": True, "items": accepted})
        except (requests.RequestException, ET.ParseError, TypeError, ValueError):
            status.append({"source": name, "ok": False, "detail": "Kaynak alınamadı; güncel gündem eksik."})
    upcoming = []
    if fetch_external:
        try:
            r = requests.get(FOMC, timeout=(5,10)); r.raise_for_status()
            upcoming = fomc_calendar(r.text, now.astimezone(ZoneInfo('Europe/Istanbul')).date())
            status.append({'source':'Fed takvimi','ok':True})
        except (requests.RequestException, ValueError):
            status.append({'source':'Fed takvimi','ok':False,'detail':'Takvim doğrulanamadı.'})
    return {"items": sorted(items, key=lambda x: x["published_at"], reverse=True)[:20], "sources": status, 'upcoming':upcoming,
            "note": "Başlıklar kaynak metnidir; modelin yön tahminine sayısal haber skoru olarak eklenmez."}
