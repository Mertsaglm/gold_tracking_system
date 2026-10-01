"""Tarihli banka tarifesi; ücret alacağı nakit yokken kaybolmaz."""
from datetime import date, datetime, timedelta
from .calendar import IST
from .ledger import cents, digest


def quarterly_fee(average_try, policy):
    for band in policy['bands']:
        if band['up_to_try'] is None or average_try <= band['up_to_try']:
            return cents(band['fee_try'] * (1 + policy['bsmv_rate']))
    raise ValueError('Saklama tarifesi üst dilimi eksik.')


def accrue(ledger, cfg, quotes, now, books=('strategy', 'benchmark')):
    """Her günün son gözlemi; eksik değerleme biliniyor gibi doldurulmaz.

    Gün içi arşiv olmadığından takvim günü son gözlemi tarife matrahının açık
    yaklaşımıdır. Eksik işlem günü bulunan çeyrek kesilmez; görünür bekler.
    """
    policy = cfg.get('custody')
    if cfg['market'] != 'bist' or not policy or not policy.get('enabled'):
        return {'enabled': False, 'pending': []}
    from .policy import value_account
    from .calendar import trading_day
    today = now.astimezone(IST).date()
    def components(book):
        # (ücret kimliği, birlikte değerlenen alt hesaplar, ücretin borçlandığı hesap)
        return (book[0], book[1], book[2]) if isinstance(book, tuple) else (book, (book,), book)

    for item in books:
        book, members, _ = components(item)
        views = [value_account(ledger.account(member), quotes, cfg, now) for member in members]
        value = (sum(float(p['quantity']) * quotes[p['symbol']]['bid']
                     for view in views for p in view['positions'])
                 if all(view['valuation_complete'] for view in views) else None)
        ledger.add('custody_mark', f'custody-mark:{book}:{now.isoformat()}', now.isoformat(),
                   book=book, day=today.isoformat(), value_try=value)
    pending = []
    begin = date.fromisoformat(cfg['start_date'])
    quarter = date(begin.year, ((begin.month - 1) // 3) * 3 + 1, 1)
    while quarter < today:
        end = date(quarter.year + 1, 1, 1) if quarter.month == 10 else date(quarter.year, quarter.month + 3, 1)
        if end > today:
            break
        for item in books:
            book, _, charge_book = components(item)
            key = f'custody:{book}:{quarter.isoformat()}'
            if key in ledger.keys:
                continue
            marks = {e['data']['day']: e['data']['value_try'] for e in ledger.events
                     if e['kind'] == 'custody_mark' and e['data']['book'] == book}
            values, missing, day, last = [], [], max(quarter, begin), None
            # Çeyrek tatilde başlayabilir. Önceki seansın bilinen değerini
            # taşı; arada eksik bir işlem günü varsa yine bilinmiyor kalır.
            prior_day = day - timedelta(days=1)
            while not trading_day(prior_day, cfg):
                prior_day -= timedelta(days=1)
            if day > begin:
                last = marks.get(prior_day.isoformat())
            while day < end:
                stamp = day.isoformat()
                if stamp in marks:
                    last = marks[stamp]
                elif trading_day(day, cfg):
                    last = None
                if last is None:
                    missing.append(stamp)
                else:
                    values.append(last)
                day += timedelta(days=1)
            if missing or not values:
                pending.append({'book': book, 'quarter': quarter.isoformat(), 'missing_days': len(missing)})
                continue
            average = sum(values) / len(values)
            amount = quarterly_fee(average, policy)
            ledger.add('account_fee', key, now.isoformat(), book=charge_book, amount_cents=amount,
                       average_securities_try=average, source=policy['source'], policy_id=digest(policy),
                       basis='Gözlenen brüt kıymet değerinin takvim günü ortalaması; banka ekstresi değildir.')
        quarter = end
    return {'enabled': True, 'pending': pending, 'source': policy['source'],
            'note': 'Dönemsel saklama tarifesi uygulanır. Matrah günlük brüt referans değer yaklaşımıdır; eksik günler görünür bekler.'}
