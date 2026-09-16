"""İzinli dosya listesiyle yedek ve boş dizinde doğrulanmış geri dönüş."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from .ledger import Ledger


def backup(root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise ValueError('Mevcut yedek üzerine yazılmaz.')
    files = [p for p in (root / 'data/advisor').rglob('*') if p.is_file() and p.suffix in {'.json', '.jsonl', '.gz'}]
    files += [p for p in (root / 'advisor').glob('*.py')]
    files += list((root / 'advisor').glob('*.json'))
    files += [p for p in (root / 'data').glob('*.sql')]
    files += [root / name for name in ('config.yaml','holidays_tr.yaml','universe.yaml','requirements-runtime.txt') if (root/name).exists()]
    if not (root / 'data/advisor/events.jsonl').exists():
        raise ValueError('Yedeklenecek defter yok.')
    Ledger(root / 'data/advisor/events.jsonl').account()
    manifest = {}
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            name = p.relative_to(root).as_posix()
            data = p.read_bytes()
            manifest[name] = hashlib.sha256(data).hexdigest()
            z.writestr(name, data)
        z.writestr('manifest.json', json.dumps(manifest, sort_keys=True))
    return {'files': len(manifest), 'archive': str(output)}


def restore(archive, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Geri dönüş yalnız yeni, boş bir dizine yapılır.')
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        if set(z.namelist()) != set(manifest) | {'manifest.json'} or len(z.namelist()) != len(manifest)+1:
            raise ValueError('Yedek manifesti dosyalarla eşleşmiyor.')
        payloads = {}
        for name, checksum in manifest.items():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Yedekte güvensiz dosya yolu.')
            data = z.read(name)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError('Yedek checksum eşleşmedi.')
            payloads[name] = data
    destination.mkdir(parents=True)
    for name, data in payloads.items():
        p = destination / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    ledger = Ledger(destination / 'data/advisor/events.jsonl')
    accounts = {book: ledger.account(book) for book in ('strategy','benchmark','shadow_reference','shadow_candidate')}
    return {'ledger_hash': ledger.root_hash, 'accounts': accounts, 'files': len(payloads)}


def drill(archive):
    with tempfile.TemporaryDirectory(prefix='advisor-recovery-') as tmp:
        result = restore(archive, Path(tmp) / 'restored')
        return {'ok': True, 'ledger_hash': result['ledger_hash'], 'files': result['files'],
                'cash_cents': {k:v['cash_cents'] for k,v in result['accounts'].items()}}
