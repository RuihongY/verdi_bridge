"""Score simulation outcomes; simulation exit status alone is insufficient."""
import json
import re
import sys
from pathlib import Path


def summarize(root):
    rows = []
    for case in ("baseline", "stalled_read_pointer", "wrong_full_compare"):
        for seed in (1, 7, 42):
            text = (Path(root) / case / ("seed-%d" % seed) / "sim.log").read_text()
            match = re.search(r"RESULT seed=(\d+) errors=(\d+) sent=(\d+) received=(\d+) first_error_ns=(-?\d+)", text)
            if not match:
                raise RuntimeError("missing completed result: %s seed %d" % (case, seed))
            values = list(map(int, match.groups()))
            row = dict(zip(("seed", "errors", "sent", "received", "first_error_ns"), values))
            row["case"] = case
            if case == "baseline":
                assert row["errors"] == 0 and row["sent"] == row["received"] == 64, row
            else:
                assert row["errors"] > 0, row
            rows.append(row)
    return rows


if __name__ == "__main__":
    print(json.dumps(summarize(sys.argv[1]), indent=2))
