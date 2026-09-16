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
