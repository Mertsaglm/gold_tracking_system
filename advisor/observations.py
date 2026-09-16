"""Kişisel işlem günlüğü değil; kotasyon/masraf varsayımının kanıtlı kontrolü."""
import math
from .ledger import digest


def record(ledger, rows, now):
    added=0
    for row in rows:
        source=row.get('source_reference')
        symbol=row.get('symbol');side=row.get('side')
        if not source or not symbol or side not in ('BUY','SELL'):
            raise ValueError('Sembol, yön ve kaynak referansı gerekli.')
        for key in ('reference_price','observed_price','expected_fee_try','observed_fee_try'):
            value=row.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError('Geçerli fiyat/masraf gerekli: '+key)
        if min(row['reference_price'],row['observed_price'])<=0:raise ValueError('Fiyat pozitif olmalı.')
        difference=(row['observed_price']/row['reference_price']-1)*100*(1 if side=='BUY' else -1)
        added+=ledger.add('cost_observation','cost-observation:'+digest(row),now.isoformat(),**row,
                          adverse_price_difference_pct=difference,
                          extra_fee_try=row['observed_fee_try']-row['expected_fee_try'])
    return added


def summary(ledger):
    rows=[e['data'] for e in ledger.events if e['kind']=='cost_observation']
    return {'samples':len(rows),'mean_adverse_price_pct':sum(r['adverse_price_difference_pct'] for r in rows)/len(rows) if rows else None,
            'extra_fees_try':sum(r['extra_fee_try'] for r in rows),
            'note':'Doğrulanmış gözlemler yoksa kişisel tarife doğrulanmış sayılmaz.'}
