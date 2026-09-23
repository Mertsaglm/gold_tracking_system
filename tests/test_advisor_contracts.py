"""Yanlış yerde yeşil testten kaçın: CI, kaynak eşliği ve veri yan etkisi."""
from pathlib import Path
import importlib.util
import json
import shutil

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]


def checker():
    spec=importlib.util.spec_from_file_location('advisor_manifest',ROOT/'scripts/advisor_manifest.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_shared_engine_manifest_and_peer_when_present():
    module=checker();assert module.check(ROOT)>0
    peer=ROOT.parent/('gold_tracking_system' if ROOT.name!='gold_tracking_system' else 'BIST tahmin')
    if (peer/'advisor/shared-manifest.json').exists():module.check(ROOT,peer)


def test_manifest_really_rejects_a_changed_peer(tmp_path):
    module=checker();(tmp_path/'advisor').mkdir()
    (tmp_path/'advisor/shared-manifest.json').write_text((ROOT/'advisor/shared-manifest.json').read_text())
    for p in (ROOT/'advisor').glob('*.py'):shutil.copy2(p,tmp_path/'advisor'/p.name)
    assert module.check(tmp_path)>0
    with (tmp_path/'advisor/policy.py').open('a') as f:f.write('\n# injected drift\n')
    with pytest.raises(ValueError,match='değişti'):module.check(tmp_path)


def test_panel_and_operational_checks_are_wired_into_ci():
    workflows=[yaml.safe_load(p.read_text()) for p in (ROOT/'.github/workflows').glob('*.yml')]
    commands=[step.get('run','') for w in workflows for job in w.get('jobs',{}).values() for step in job.get('steps',[])]
    assert any('npm test --prefix dashboard' in command for command in commands)
    assert any('npm run build --prefix dashboard' in command for command in commands)
    for command in ('advisor watchdog','advisor recovery-check'):
        wf=next(w for w in workflows if any(command in s.get('run','') for j in w['jobs'].values() for s in j.get('steps',[])))
        assert wf['permissions']['contents']=='read'
    assert all('==' in line for line in (ROOT/'requirements-runtime.txt').read_text().splitlines() if line and not line.startswith('#'))


def test_portfolio_has_a_scheduled_fallback_and_observer_remains_read_only():
    # Üretimde 15 dk'lık dispatch'in sahibi doğrulanamadı; repo kendi yedeğini de tanımlamalı.
    portfolio=yaml.safe_load((ROOT/'.github/workflows/portfolio.yml').read_text())
    triggers=portfolio.get('on',portfolio.get(True))
    assert 'workflow_dispatch' in triggers and triggers['schedule']
    assert portfolio['concurrency']['cancel-in-progress'] is False
    watchdog=yaml.safe_load((ROOT/'.github/workflows/advisor-watchdog.yml').read_text())
    observer=watchdog.get('on',watchdog.get(True))
    assert len(observer['schedule']) == 1 and '13,43' in observer['schedule'][0]['cron']
    assert watchdog['permissions']['contents'] == 'read'
    if (ROOT/'src/advisor_refresh.py').exists():
        steps=portfolio['jobs']['portfolio']['steps']
        refresh=next(i for i,s in enumerate(steps) if 'src.advisor_refresh' in s.get('run',''))
        cycle=next(i for i,s in enumerate(steps) if 'advisor cycle' in s.get('run',''))
        assert refresh < cycle and steps[refresh].get('continue-on-error') is True
        assert any('git add data/advisor/ data/altin.sql' in s.get('run','') for s in steps)
