"""Ensure the benchmark cannot silently count an unfinished or ineffective test as success."""
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).parents[1] / 'examples/multidesign/check_results.py'
spec = importlib.util.spec_from_file_location('benchmark_results', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_complete_repaired_result():
    row = module.parse('RESULT seed=7 errors=0 sent=12 received=12 first_error_ns=-1',
                       'uart', 'repaired', 7)
    assert row['received'] == 12


@pytest.mark.parametrize('text', [
    '$finish',
    'RESULT seed=1 errors=0 sent=12 received=0 first_error_ns=-1',
    'RESULT seed=1 errors=0 sent=12 received=12 first_error_ns=-1\nINCOMPLETE',
    'RESULT seed=7 errors=0 sent=12 received=12 first_error_ns=-1',
])
def test_reject_incomplete_or_wrong_control(text):
    with pytest.raises(ValueError):
        module.parse(text, 'axil', 'baseline', 1)


def test_reject_undetected_mutant():
    with pytest.raises(ValueError, match='escaped detection'):
        module.parse('RESULT seed=1 errors=0 sent=100 received=100 first_error_ns=-1',
                     'arbiter', 'mutant', 1)
