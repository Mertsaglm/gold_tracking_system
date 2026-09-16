"""Ortak motor sözleşmesi; --peer ile iki checkout birlikte doğrulanır."""
import argparse
import hashlib
import json
from pathlib import Path


def fingerprint(root):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((Path(root)/'advisor').glob('*.py'))}


def check(root,peer=None):
    root=Path(root)
    expected=json.loads((root/'advisor/shared-manifest.json').read_text())['files']
    actual=fingerprint(root)
    if actual!=expected:raise ValueError('Ortak motor değişti; iki projeyi eşitle ve manifesti birlikte yenile.')
    if peer and fingerprint(peer)!=actual:raise ValueError('BIST ve altın ortak motorları ayrışmış.')
    return len(actual)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--peer',type=Path);p.add_argument('--write',action='store_true');a=p.parse_args()
    if a.write:
        if a.peer and fingerprint(a.root)!=fingerprint(a.peer):p.error('Manifest yazmadan önce motorları eşitle.')
        payload=json.dumps({'version':1,'files':fingerprint(a.root)},indent=2)+'\n'
        (a.root/'advisor/shared-manifest.json').write_text(payload)
        if a.peer:(a.peer/'advisor/shared-manifest.json').write_text(payload)
    print(f'{check(a.root,a.peer)} ortak modül doğrulandı.')
