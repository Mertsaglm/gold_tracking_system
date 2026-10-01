"""2026-09-15 sözleşmesinin regresyon girdisi; yeni hesap ayrı test edilir."""
from advisor.service import configuration


def legacy_configuration(root):
    cfg = configuration(root)
    for key in ('account_id','entry_window','observation_window','adaptive_risk','custody',
                'candidates_enabled','require_next_quote','watchlist_enabled'):
        cfg.pop(key, None)
    cfg.update(start_date='2026-09-15', initial_try=5000,
               execution_window={'open':'10:15','close':'17:45','half_day_close':'12:15'})
    return cfg
