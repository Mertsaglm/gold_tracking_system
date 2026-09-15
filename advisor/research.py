"""Eski kararların sonraki fiyat hareketi: seçilmeyenler de paydaya girer."""
from __future__ import annotations

import pandas as pd
from . import history, learning


def retrospective(con, cfg):
    table = 'bars_daily' if cfg['market'] == 'bist' else 'history_daily'
    latest = con.execute(f'SELECT max(date) FROM {table}').fetchone()[0]
    prices = learning.features(history.load(con, cfg['market'], latest), cfg['horizon_sessions'])
    if cfg['market'] == 'bist':
        decisions = pd.read_sql_query("SELECT p.ticker symbol,p.asof date,p.action,p.veto_code,r.tool source FROM predictions p JOIN llm_runs r USING(run_id) WHERE r.tool!='replay'", con)
    else:
        decisions = pd.read_sql_query("SELECT 'GRAM' symbol,asof_date date,hukum action,kol source FROM predictions", con)
    original_records = len(decisions)
    decisions = decisions.drop_duplicates(['symbol','date','action','source'])
    joined = decisions.merge(prices[['symbol','date','forward_pct','label_end']], on=['symbol','date'], how='left')
    result = []
    for (source, action), g in joined.groupby(['source','action']):
        mature = g[g.forward_pct.notna()]
        result.append({'source':source,'action':action,'decisions':len(g),'matured':len(mature),
                       'mean_forward_pct':float(mature.forward_pct.mean()) if len(mature) else None,
                       'up_moves':int((mature.forward_pct>0).sum()),'down_moves':int((mature.forward_pct<0).sum())})
    unchosen = joined[~joined.action.isin(['plan_sec','AL','AL_AZ','TUT']) & joined.forward_pct.notna()]
    examples = unchosen.sort_values('forward_pct', ascending=False).head(15)
    return {'asof':latest,'horizon_sessions':cfg['horizon_sessions'],'groups':result, 'original_records':original_records, 'unique_day_source_decisions':len(decisions),
            'unselected_up_moves':examples.where(pd.notna(examples),None).to_dict('records'),
            'note':'Sonraki düzeltilmiş kapanış değişimi. Limit giriş, stop ve banka maliyeti uygulanmış işlem sonucu değildir. Aynı güne ait birden fazla model bağımsız örnek sayılmaz.'}
