"""Karar kapılarının tarihli paydaları; karşı olgu işlem getirisi değildir."""
from __future__ import annotations

from collections import Counter


def summarize(decisions):
    summary = Counter()
    codes = Counter()
    combinations = Counter()
    for decision in decisions:
        codes[decision.get('decisive_code', decision.get('code', 'bilinmiyor'))] += 1
        checks = {item['check']: item['status'] for item in decision.get('checks', [])}
        for name, status in checks.items():
            summary[(name, 'evaluated' if status != 'değerlendirilmedi' else 'not_evaluated')] += 1
            if status == 'geçti':
                summary[(name, 'passed')] += 1
            elif status == 'kaldı':
                summary[(name, 'failed')] += 1
        required = ('maliyet', 'trend', 'rsi', 'kazanc_risk')
        if all(checks.get(name) in ('geçti', 'kaldı') for name in required):
            cost, trend, rsi, rr = (checks[name] == 'geçti' for name in required)
            combinations['fully_evaluated'] += 1
            combinations['all_pass'] += cost and trend and rsi and rr
            combinations['without_rr'] += cost and trend and rsi
            combinations['without_trend'] += cost and rsi and rr
            combinations['without_both'] += cost and rsi
    gates = {name: {'evaluated': summary[(name, 'evaluated')],
                    'passed': summary[(name, 'passed')],
                    'failed': summary[(name, 'failed')],
                    'not_evaluated': summary[(name, 'not_evaluated')]}
             for name in sorted({name for name, _ in summary})}
    return {'decisions': len(decisions), 'gates': gates, 'decisive_codes': dict(codes),
            'bist_interaction': dict(combinations),
            'note': ('Birleşim sayıları yalnız dört kontrolün de ölçüldüğü hisselerin paydasındadır. '
                     'Filtreyi kaldırınca oluşabilecek aday sayısıdır; gerçekleşmiş getiri veya işlem değildir.'),
            'outcome_claim': False}
