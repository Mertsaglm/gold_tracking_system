"""Yeni bütçe ayrı defter açar; geçmişi yeniden ölçeklemez veya silmez."""
import json
import re
from pathlib import Path


def state_path(root, cfg=None):
    root = Path(root)
    cfg = cfg if cfg is not None else json.loads((root / 'advisor/config.json').read_text())
    identity = cfg.get('account_id')
    base = root / 'data/advisor'
    if identity is None:
        return base  # 2026-09-15 defterlerinin ve eski kapsüllerin sözleşmesi.
    if not isinstance(identity, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', identity):
        raise ValueError('Geçersiz sanal hesap kimliği.')
    return base / 'accounts' / identity
