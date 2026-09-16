"""O gün bilinen evren; sonraki üyelik bilgisi geçmişe taşınamaz."""
from datetime import date
import json
from pathlib import Path

from .ledger import atomic_json, digest


def validate(rows):
    seen={}
    for row in rows:
        if not isinstance(row.get('symbol'),str) or not row['symbol'] or not row.get('source'):
            raise ValueError('Evren kaydı sembol ve kaynak gerektirir.')
        for key in ('known_at','effective_from'):
            date.fromisoformat(row[key])
        if row.get('effective_to'):
            date.fromisoformat(row['effective_to'])
            if row['effective_to']<=row['effective_from']:
                raise ValueError('Evren bitişi başlangıçtan sonra olmalı.')
        if not isinstance(row.get('active'),bool):
            raise ValueError('Üyelik durumu açıkça belirtilmeli.')
        key=(row['symbol'],row['known_at'],row['effective_from'])
        if key in seen and seen[key]!=row:raise ValueError('Aynı tarihli üyelik kayıtları çelişiyor.')
        seen[key]=row
    return rows


def members(rows, day):
    available=[r for r in validate(rows) if r['known_at']<=day and r['effective_from']<=day
               and (not r.get('effective_to') or day<r['effective_to'])]
    by_symbol={}
    for r in sorted(available,key=lambda r:(r['known_at'],r['effective_from'])):
        by_symbol[r['symbol']]=r
    return {s for s,r in by_symbol.items() if r['active']}


def archive(ledger, symbols, now):
    from .calendar import IST
    day=now.astimezone(IST).date().isoformat()
    symbols=sorted(set(symbols))
    ledger.add('universe_snapshot','universe:'+digest({'day':day,'symbols':symbols}),now.isoformat(),
               known_at=day,effective_from=day,symbols=symbols,source='güncel izleme evreni; geçmiş üyelik iddiası yok')


def read(root):
    path=Path(root)/'advisor/universe-history.json'
    return validate(json.loads(path.read_text())) if path.exists() else []


def import_history(root, input_path):
    rows=validate(json.loads(Path(input_path).read_text()))
    path=Path(root)/'advisor/universe-history.json'
    old=read(root)
    validate(old+rows)
    combined={digest(r):r for r in old+rows}
    atomic_json(path, sorted(combined.values(),key=lambda r:(r['known_at'],r['symbol'],r['effective_from'])))
    return {'records':len(combined)}
