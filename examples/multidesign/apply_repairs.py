"""Replay documented, investigator-proposed fixes into separate build directories."""
import argparse
import hashlib
import json
from pathlib import Path


def repair(root):
    root = Path(root)
    proposals = json.loads(Path(__file__).with_name('repairs.json').read_text())
    results = {}
    for case, patch in proposals.items():
        out = root / case / 'repaired'
        out.mkdir(parents=True, exist_ok=True)
        results[case] = {}
        for source in (root / case / 'mutant').glob('*.v'):
            text = source.read_text()
            if source.name == patch['file']:
                if text.count(patch['old']) != 1:
                    raise ValueError('repair anchor must occur exactly once')
                text = text.replace(patch['old'], patch['new'])
            data = text.encode()
            (out / source.name).write_bytes(data)
            results[case][source.name] = {
                'sha256': hashlib.sha256(data).hexdigest(),
                'matches_baseline': data == (root / case / 'baseline' / source.name).read_bytes()
            }
    (root / 'repair-audit.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', nargs='?', default='build/multidesign')
    repair(parser.parse_args().root)
