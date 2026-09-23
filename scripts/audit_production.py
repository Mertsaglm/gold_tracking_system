"""Salt-okur V2 üretim kanıtı: python scripts/audit_production.py --root ... --output ...

--replay mühürlenmiş kendi kod paketlerini ayrı süreçte, ağsız yeniden çalıştırır.
Ham defter, SQL ve geçmiş raporlar değiştirilmez. Test sayısı yerine bu ölçümü yeniden koş.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import shutil
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor import capsule, history, learning, notifications, policy, service
from advisor.calendar import IST, load
from advisor.ledger import Ledger


def validate_fixes(root):
    """Güncel motoru gerçek mühürlü girdilerle; tam çevrimi/yedeği kopyada sına."""
    from advisor import engine, recovery
    root = Path(root).resolve()
    ledger = Ledger(root/'data/advisor/events.jsonl')
    def semantic(value):
        if isinstance(value, dict):
            return {k:semantic(v) for k,v in value.items() if k not in ('key','decision_key','horizon_sessions')}
        if isinstance(value, list):return [semantic(v) for v in value]
        return value
    checked = decisions = 0
    invalid_reference_displays = []
    for e in ledger.events:
        if e['kind'] != 'decision_capsule':continue
        payload=json.loads(gzip.decompress((root/'data/advisor'/e['data']['path']).read_bytes()))['payload']
        c=payload['context']; l=Ledger(Path('/nonexistent-audit-ledger'))
        l.events=list(c['events']);l.keys={r['key'] for r in l.events};l.root_hash=l.events[-1]['hash']
        actual,_=engine.run(l,c['rows'],c['forecasts'],c['model'],c['cfg'],c['quotes'],datetime.fromisoformat(c['now']),c['event_note'])
        assert len(actual)==len(payload['expected'])
        for old, new in zip(payload['expected'], actual):
            old,new=semantic(old),semantic(new)
            changed={k for k in old.keys()|new.keys() if old.get(k)!=new.get(k)}
            if changed:
                # Eksik referansla eskiden basılan hayali kalan getiri/hedef temizlenir;
                # gerçekleşen karar, emir ve maliyetin değişmesine izin verilmez.
                assert old['action']==new['action']=='VERİ BEKLENİYOR' and new['remaining_forecast_pct'] is None
                assert changed <= {'remaining_forecast_pct','stop','target'}, ('decision_changed',e['key'],changed)
                invalid_reference_displays.append({'at':c['now'],'symbol':new['symbol'],'fields':sorted(changed)})
        checked+=1; decisions+=len(actual)
    with tempfile.TemporaryDirectory(prefix='advisor-audit-fixes-') as temp:
        work=Path(temp)/'cycle';work.mkdir();(work/'advisor').mkdir()
        shutil.copytree(root/'data',work/'data')
        # Kod ve ayarlar denetimin çalıştırıldığı checkout'tan, girdiler arşivden.
        local=Path(__file__).resolve().parents[1]
        shutil.copy2(local/'advisor/config.json',work/'advisor/config.json')
        for name in ('holidays_tr.yaml','config.yaml','universe.yaml'):
            if (root/name).exists():shutil.copy2(root/name,work/name)
        s=json.loads((root/'data/advisor/latest.json').read_text())
        now=datetime.fromisoformat(s['generated_at'])
        books=('strategy','benchmark','shadow_reference','shadow_candidate')
        before={book:ledger.account(book) for book in books}
        for _ in range(2):
            updated=service.cycle(work,now=now,quotes=s['quotes'],offline=True)
            after=Ledger(work/'data/advisor/events.jsonl')
            assert {book:after.account(book) for book in books}==before, 'repeated_cycle_changed_accounts'
        old_model=json.loads((root/'data/advisor/model.json').read_text())
        new_model=json.loads((work/'data/advisor/model.json').read_text())
        numeric_deltas=[]
        def same_model(a,b):
            if isinstance(a,dict):return a.keys()==b.keys() and all(same_model(v,b[k]) for k,v in a.items())
            if isinstance(a,list):return len(a)==len(b) and all(same_model(x,y) for x,y in zip(a,b))
            if isinstance(a,float):
                numeric_deltas.append(abs(a-b))
                # Ubuntu ve macOS BLAS son bitleri değiştirebilir; bit eşliği iddia edilmez.
                return math.isclose(a,b,rel_tol=0,abs_tol=1e-10)
            return a==b
        for key in ('weights','mean','scale','intercept','training_rows','training_dates','label_end','evaluation'):
            assert same_model(old_model[key],new_model[key]), ('retrained_model_changed',key)
        archive=Path(temp)/'backup.zip';recovery.backup(root,archive)
        restored=recovery.restore(archive,Path(temp)/'restored')
        assert restored['ledger_hash']==ledger.root_hash and restored['accounts']==before
        return {'current_engine_capsules':checked,'current_engine_decisions':decisions,
                'comparison_excludes':['key','decision_key','horizon_sessions'],
                'invalid_reference_displays_corrected':invalid_reference_displays,
                'full_cycle_runs':2,'all_four_accounts_unchanged':True,
                'retrained_model_parameters_and_evaluation_match':True,
                'model_comparison_absolute_tolerance':1e-10,
                'model_maximum_absolute_difference':max(numeric_deltas,default=0),
                'analysis_issues_visible':updated['health']['analysis_issues'],
                'backup_restore_all_accounts_match':True,'backup_files':restored['files']}


def money(value):
    return int((Decimal(str(value))*100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def independent(events, book):
    """Defter.account çağırmadan katkı, maliyet, nakit, adet ve alacak mutabakatı."""
    cash = contributed = realized = receivable = 0
    positions = {}
    for e in events:
        d = e['data']
        if d.get('book') != book:
            continue
        if e['kind'] == 'account_checkpoint':
            a = d['account']
            cash, contributed, realized, receivable = (a[k] for k in ('cash_cents','contributed_cents','realized_cents','receivable_cents'))
            positions = {s:[Decimal(p['quantity']), p['cost_cents']] for s,p in a['positions'].items()}
        elif e['kind'] == 'contribution':
            cash += d['amount_cents']; contributed += d['amount_cents']
        elif e['kind'] == 'fill':
            qty = Decimal(d['quantity']); symbol = d['symbol']
            assert money(qty*Decimal(str(d['price']))) == d['notional_cents'], ('notional', e['key'])
            p = positions.setdefault(symbol, [Decimal(0),0])
            if d['side'] == 'BUY':
                amount = d['notional_cents']+d['fee_cents']
                cash -= amount; p[0] += qty; p[1] += amount
            else:
                assert p[0] >= qty, ('oversell', e['key'])
                cost = int((Decimal(p[1])*qty/p[0]).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                cash += d['notional_cents']-d['fee_cents']
                realized += d['notional_cents']-d['fee_cents']-cost
                p[0] -= qty; p[1] -= cost
            assert cash >= 0, ('negative_cash',e['key'])
        elif e['kind'] == 'dividend_receivable':
            receivable += d['amount_cents']
        elif e['kind'] == 'dividend_payment':
            receivable -= d['amount_cents']; cash += d['amount_cents']
            assert receivable >= 0
        elif e['kind'] == 'corporate_action':
            if d['action'] == 'split':
                if d['symbol'] in positions: positions[d['symbol']][0] *= Decimal(str(d['ratio']))
            else: cash += d['net_cents']
    return {'cash_cents':cash,'contributed_cents':contributed,'realized_cents':realized,
            'receivable_cents':receivable,'positions':{s:{'quantity':str(q),'cost_cents':c} for s,(q,c) in positions.items() if q>0}}


def audit(root, replay=False):
    root = Path(root).resolve(); cfg = service.configuration(root); cfg['calendar'] = load(root)
    path = root/'data/advisor/events.jsonl'; ledger = Ledger(path)
    snapshot = json.loads((root/'data/advisor/latest.json').read_text())
    events = ledger.events
    result = {'market':cfg['market'], 'through':events[-1]['at'],
              'snapshot_at':snapshot['generated_at'], 'analysis_date':snapshot['analysis_date'],
              'ledger_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'ledger_hash':ledger.root_hash,
              'events':len(events),'kinds':dict(Counter(e['kind'] for e in events)), 'accounts':{}}
    for book in ('strategy','benchmark','shadow_reference','shadow_candidate'):
        a = independent(events,book); expected = ledger.account(book)
        for key in ('cash_cents','contributed_cents','realized_cents','receivable_cents'):
            assert a[key] == expected[key], (book,key)
        assert a['positions'] == {s:{'quantity':str(p['quantity']),'cost_cents':p['cost_cents']} for s,p in expected['positions'].items()}
        result['accounts'][book] = a
    index = next(i for i,e in enumerate(events) if e['hash']==snapshot['health']['ledger_hash'])
    prefix = Ledger(Path('/nonexistent-audit-ledger')); prefix.events=events[:index+1]
    for book in ('strategy','benchmark'):
        value = policy.value_account(prefix.account(book),snapshot['quotes'],cfg,datetime.fromisoformat(snapshot['generated_at']))
        for field in ('cash_try','contributed_try','equity_try','pnl_try','receivable_try'):
            assert value[field] == snapshot[book][field], ('snapshot',book,field)
    result['snapshot_accounts_match'] = True
    daily = defaultdict(list)
    for e in events:
        if e['kind']=='session_check' and e['data'].get('in_execution_window',True):
            daily[e['at'][:10]].append(e)
    result['daily_cycles'] = []
    for day, rows in sorted(daily.items()):
        times = sorted(datetime.fromisoformat(r['at']) for r in rows)
        result['daily_cycles'].append({'date':day,'count':len(rows),'first':times[0].isoformat(),'last':times[-1].isoformat(),
            'max_gap_minutes':round(max(((b-a).total_seconds()/60 for a,b in zip(times,times[1:])),default=0),2),
            'full_quote_cycles':sum(r['data']['valid_quotes']==r['data']['expected_quotes'] for r in rows)})
    result['decisions'] = dict(Counter((e['data']['code']) for e in events if e['kind']=='decision'))
    result['fills'] = [{**{k:e['data'].get(k) for k in ('book','symbol','side','quantity','price','fee_cents','decision_key')},'at':e['at']}
                       for e in events if e['kind']=='fill']
    for e in events:
        if e['kind']=='fill':
            d=e['data'];price=policy.execution_price(d['quote'],cfg,d['side'])
            assert abs(price-d['price'])<1e-8
            assert policy.fee(cfg,float(d['quantity'])*price,d['side'])==d['fee_cents']
    last = next((e for e in reversed(events) if e['kind']=='notification'), None)
    result['last_notification'] = {'at':last['at'],'text':last['data']['text']} if last else None
    result['latest_notification_matches_current_state'] = notifications.delivered(ledger,snapshot)
    result['learning'] = {k:snapshot['feedback'][k] for k in ('roundtrips','live_gate_passed','scorecard','evidence')}
    result['models'] = []
    for file in sorted((root/'data/advisor/models').glob('*.json')):
        model=json.loads(file.read_text())
        assert model['label_end']<=model['asof']
        assert all(fold['train_label_end']<fold['test_start'] for fold in model['folds'])
        result['models'].append({'id':model['id'],'asof':model['asof'],'training_dates':model['training_dates'],
                                 'training_rows':model['training_rows'],'approved':model['approved'],
                                 'periods':model['evaluation']['periods'],'lower_95_pct':model['evaluation']['lower_95_pct']})
    verified=0; reproduced=0; runtimes=[]
    for e in events:
        if e['kind']!='decision_capsule':continue
        file=root/'data/advisor'/e['data']['path'];envelope=json.loads(gzip.decompress(file.read_bytes()))
        assert capsule.digest(envelope['payload'])==envelope['hash']==e['data']['id']
        context=envelope['payload']['context']
        assert all(r['date']<=context['now'][:10] for r in context['rows'])
        verified+=1
        if replay:
            assert capsule.reproduce(file)['ok'];reproduced+=1
            if reproduced%15==0:print(f"{cfg['market']}: {reproduced} karar paketi yeniden üretildi",file=sys.stderr,flush=True)
        if envelope['payload']['runtime'] not in runtimes:runtimes.append(envelope['payload']['runtime'])
    result['capsules']={'hash_verified':verified,'archived_code_reproduced':reproduced,'runtimes':runtimes}
    with history.connection(root,cfg['market']) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        result['sql_sha256']=hashlib.sha256((root/'data'/('bist.sql' if cfg['market']=='bist' else 'altin.sql')).read_bytes()).hexdigest()
        frame=history.load(con,cfg['market'],snapshot['generated_at'][:10])
        result['history']={'rows':len(frame),'last_date':str(frame.date.max()),'live_symbols':frame.attrs['live_symbols'],
            'latest_by_live_symbol':{s:str(g.date.max()) for s,g in frame[frame.symbol.isin(frame.attrs['live_symbols'])].groupby('symbol')}}
        if cfg['market']=='gold':
            from src import reconcile,util
            rows=reconcile.comparisons(con,util.load_config(),datetime.fromisoformat(result['snapshot_at']))
            result['legacy_reconciliation']={'rows':len(rows),'valid_matches':sum(r['valid'] for r in rows),
                'invalid_completed_flags':sum(r['recorded_reconciled'] and not r['valid'] for r in rows),
                'after_revision': [r for r in rows if r['ts']>='2026-09-15']}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--output',type=Path,required=True);p.add_argument('--replay',action='store_true');p.add_argument('--validate-fixes',action='store_true');a=p.parse_args()
    if a.output.resolve().is_relative_to((a.root/'data').resolve()):p.error('Kanıt raporu gerçek veri dizinine yazılamaz.')
    result=audit(a.root,a.replay)
    if a.validate_fixes:result['fix_validation']=validate_fixes(a.root)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'report':str(a.output),'events':result['events'],'capsules':result['capsules']},ensure_ascii=False))
