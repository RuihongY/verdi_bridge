"""Require complete baseline, mutant and repaired results; never infer pass from exit code."""
import argparse
import json
import re
from pathlib import Path

PATTERN = r'RESULT seed=(\d+) errors=(\d+) sent=(\d+) received=(\d+) first_error_ns=(-?\d+)'


def parse(text, design, variant, seed):
    matches = re.findall(PATTERN, text)
    if len(matches) != 1 or 'INCOMPLETE' in text:
        raise ValueError(f'missing or incomplete result: {design}/{variant}/{seed}')
    row = dict(zip(('seed', 'errors', 'sent', 'received', 'first_error_ns'),
                   map(int, matches[0])))
    row.update(design=design, variant=variant)
    target = 100 if design == 'arbiter' else 12
    if row['seed'] != seed:
        raise ValueError('wrong seed in result')
    if variant in ('baseline', 'repaired'):
        if row['errors'] or row['sent'] != target or row['received'] != target or row['first_error_ns'] != -1:
            raise ValueError(f'control/repair did not pass: {row}')
    elif variant == 'mutant':
        if row['errors'] <= 0 or row['first_error_ns'] < 0:
            raise ValueError(f'mutation escaped detection: {row}')
    else:
        raise ValueError(f'unknown variant: {variant}')
    return row


def summarize(root):
    rows = []
    for design in ('uart', 'axil', 'arbiter'):
        for variant in ('baseline', 'mutant', 'repaired'):
            for seed in (1, 7, 42):
                path = Path(root) / design / variant / f'seed-{seed}' / 'sim.log'
                rows.append(parse(path.read_text(), design, variant, seed))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', nargs='?', default='build/multidesign')
    print(json.dumps(summarize(parser.parse_args().root), indent=2))
