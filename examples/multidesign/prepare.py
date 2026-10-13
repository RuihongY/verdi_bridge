"""Generate baseline and mutant fixtures. Ground truth is separate from captures."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def prepare(root):
    root = Path(root)
    specs = json.loads(Path(__file__).with_name('specs.json').read_text())
    for case, spec in specs.items():
        for name, digest in spec['files'].items():
            repo = spec['repository'].removeprefix('https://github.com/')
            url = f"https://raw.githubusercontent.com/{repo}/{spec['commit']}/rtl/{name}"
            data = urllib.request.urlopen(url, timeout=30).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"upstream hash mismatch: {url}")
            for variant in ('baseline', 'mutant'):
                folder = root / case / variant
                folder.mkdir(parents=True, exist_ok=True)
                text = data.decode()
                if name == spec['target']:
                    if text.count(spec['original']) != 1:
                        raise ValueError('mutation must have one exact anchor')
                    spec['line'] = text[:text.index(spec['original'])].count('\n') + 1
                    if variant == 'mutant':
                        text = text.replace(spec['original'], spec['mutated'])
                (folder / name).write_text(text)
    (root / 'ground-truth.json').write_text(json.dumps(specs, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', nargs='?', default='build/multidesign')
    prepare(parser.parse_args().root)
