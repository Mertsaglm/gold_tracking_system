"""Bölünmeyi fiyat kaybından ayırır; geç gelen olayları sessizce düzeltmez."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from .ledger import Ledger, atomic_json, cents


def refresh(symbols, state, now):
    import json
    import yfinance as yf
    path = state / 'corporate.json'
    cache = json.loads(path.read_text()) if path.exists() else {}
    today = now.date().isoformat()
    result = {}
    for symbol in symbols:
        previous = cache.get(symbol, {})
        if previous.get('checked_day') == today and previous.get('ok'):
            result[symbol] = previous
            continue
        try:
            # t.actions boş listesi kaynak arızasını gizleyebilir; fiyat geçmişini de doğrula.
            bars = yf.Ticker(symbol + '.IS').history(period='1mo', auto_adjust=False, actions=True, raise_errors=True)
            if bars.empty or (now.date() - bars.index[-1].date()).days > 5:
                raise ValueError('Kurumsal işlem kaynağı eski/boş.')
            actions = []
            for stamp, row in bars.iterrows():
                for field, kind in [('Dividends', 'temettu'), ('Stock Splits', 'bolunme')]:
                    amount = float(row.get(field, 0))
                    if amount > 0:
                        actions.append({'ticker': symbol, 'date': stamp.date().isoformat(), 'kind': kind, 'value': amount})
            result[symbol] = {'checked_day': today, 'ok': True, 'actions': actions}
        except Exception as exc:
            result[symbol] = {'checked_day': today, 'ok': False, 'error': type(exc).__name__, 'actions': previous.get('actions', [])}
    atomic_json(path, result)
    return result


def reconcile(ledger, actions, cfg, now):
    blocked = {}
    today = now.date().isoformat()
    for a in sorted(actions, key=lambda a: (a['date'], a['ticker'], a['kind'])):
        if not cfg['start_date'] <= a['date'] <= today:
            continue
        symbol = a['ticker']
        for book in ('strategy', 'benchmark', 'shadow_reference', 'shadow_candidate'):
            key = f"corporate:{book}:{symbol}:{a['date']}:{a['kind']}"
            if key in ledger.keys:
                continue
            # Hak sahipliği ex-date öncesindeki eldeki miktardan gelir.
            before = Ledger(Path('/nonexistent-advisor-corporate-ledger'))
            before.events = [e for e in ledger.events if e['at'][:10] < a['date']]
            held = before.account(book)['positions'].get(symbol)
            if not held:
                continue
            late_fills = [e for e in ledger.events if e['kind'] == 'fill' and e['data']['book'] == book and e['data']['symbol'] == symbol and e['at'][:10] >= a['date']]
            if a['kind'] == 'bolunme' and late_fills:
                blocked[symbol] = 'Bölünme bilgisi işlemden sonra geldi; adet mutabakatı gerekli.'
                continue
            if a['kind'] == 'bolunme':
                ledger.add('corporate_action', key, now.isoformat(), book=book, symbol=symbol,
                           action='split', ratio=a['value'], effective_date=a['date'])
            elif a['kind'] == 'temettu':
                # Ödeme günü kaynaktan gelmiyor. Alacak ayrı izlenir, harcanabilir nakit sayılmaz.
                net = cents(float(held['quantity']) * a['value'] * (1 - cfg.get('dividend_tax_rate', .15)))
                ledger.add('dividend_receivable', key, now.isoformat(), book=book, symbol=symbol,
                           amount_cents=net, gross_per_share=a['value'], effective_date=a['date'],
                           note='Net temettü alacağı; ödeme tarihi doğrulanana kadar nakde eklenmez.')
    return blocked


def settle(ledger, payments, now):
    """Ödeme tarihi ve kanıt referansıyla alacağı bir kez nakde çevir."""
    count=0
    for payment in payments:
        key=payment['receivable_key']
        source=str(payment.get('source_reference','')).strip()
        paid=date.fromisoformat(payment['paid_on'])
        if not source or paid>now.date():raise ValueError('Geçerli ödeme günü ve kaynak referansı gerekli.')
        receivable=next((e for e in ledger.events if e['kind']=='dividend_receivable' and e['key']==key),None)
        if not receivable:raise ValueError('Temettü alacağı bulunamadı.')
        d=receivable['data']
        if paid.isoformat()<d['effective_date']:raise ValueError('Ödeme hak kazanma tarihinden önce olamaz.')
        amount=payment.get('amount_cents')
        if isinstance(amount,bool) or not isinstance(amount,int) or amount!=d['amount_cents']:
            raise ValueError('Ödeme net alacak tutarıyla birebir eşleşmeli.')
        prior=next((e['data'] for e in ledger.events if e['key']=='payment:'+key),None)
        if prior and (prior['paid_on']!=paid.isoformat() or prior['source_reference']!=source):
            raise ValueError('Önceki ödeme kanıtı değiştirilemez.')
        count+=ledger.add('dividend_payment','payment:'+key,now.isoformat(),book=d['book'],symbol=d['symbol'],
                          amount_cents=amount,paid_on=paid.isoformat(),source_reference=source,receivable_key=key)
        ledger.account(d['book'])
    return count
