"""Check repository-relative Markdown links in project documentation."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

LINK = re.compile(r'(?<!!)\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)')
ROOT = Path(__file__).resolve().parents[1]


def check(root):
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    known = {root / path for path in tracked if path}
    directories = {parent for path in known for parent in path.parents}
    docs = sorted({p for area in ('ai', 'docs') for p in (root / area).rglob('*.md')}
                  | set(root.glob('*.md')))
    errors = []
    checked = 0
    for page in docs:
        if page.name == 'PROFILE.md':
            continue
        for lineno, line in enumerate(page.read_text().splitlines(), 1):
            for link in LINK.findall(line):
                target = urlsplit(link.strip('<>'))
                if target.scheme or target.netloc or not target.path:
                    continue
                checked += 1
                path = (page.parent / unquote(target.path)).resolve()
                if not path.is_relative_to(root) or not (path.exists() or path in known or path in directories):
                    errors.append(f'{page.relative_to(root)}:{lineno}: {link}')
    return len(docs), checked, errors


if __name__ == '__main__':
    pages, links, failures = check(ROOT)
    for entry in failures:
        print(entry)
    print(f'{pages} pages, {links} relative links, {len(failures)} errors')
    raise SystemExit(bool(failures))
