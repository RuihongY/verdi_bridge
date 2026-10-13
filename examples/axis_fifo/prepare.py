"""Fetch a pinned MIT RTL file and create explicit, independently runnable mutants."""
import hashlib
import json
import urllib.request
from pathlib import Path

COMMIT = "48ff7a7e2ef782cf778d47910cf85835c64b1bce"
URL = f"https://raw.githubusercontent.com/alexforencich/verilog-axis/{COMMIT}/rtl/axis_fifo.v"
MUTATIONS = {
    "stalled_read_pointer": ("rd_ptr_reg <= rd_ptr_reg + 1;", "rd_ptr_reg <= rd_ptr_reg;"),
    "wrong_full_compare": (
        "wire full = wr_ptr_reg == (rd_ptr_reg ^ {1'b1, {ADDR_WIDTH{1'b0}}});",
        "wire full = wr_ptr_reg == rd_ptr_reg;"),
}


def prepare(destination):
    destination = Path(destination)
    data = urllib.request.urlopen(URL, timeout=30).read()
    expected = "aefddc67fc3552d919280424606fc6b048e61d7df9ee7ee0f8801c082c1cfc39"
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("pinned upstream source hash mismatch")
    text = data.decode()
    manifest = {"repository": "https://github.com/alexforencich/verilog-axis",
                "commit": COMMIT, "source_url": URL,
                "sha256": hashlib.sha256(data).hexdigest(), "license": "MIT", "cases": {}}
    for case in ["baseline", *MUTATIONS]:
        code = text
        metadata = {}
        if case in MUTATIONS:
            old, new = MUTATIONS[case]
            if text.count(old) != 1:
                raise ValueError("mutation anchor must occur exactly once")
            code = text.replace(old, new)
            metadata = {"line": text[:text.index(old)].count("\n") + 1,
                        "original": old, "mutated": new}
        folder = destination / case
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "axis_fifo.v").write_text(code)
        manifest["cases"][case] = metadata
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", nargs="?", default="build/axis_fifo")
    print(json.dumps(prepare(parser.parse_args().destination), indent=2))
