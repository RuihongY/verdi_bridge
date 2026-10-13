"""Standalone stdlib helper, also executed over SSH with Python 3.6+."""
import base64
import json
import os
import re
import stat
import sys
import time
import uuid
from pathlib import Path


def private_root(path):
    root = Path(path)
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("bridge directory must be absolute and not a symlink")
    info = root.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("bridge directory must be owned by you with mode 0700")
    return root


def exchange(config):
    root = private_root(config["directory"])
    session = (root / "session").read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session):
        raise ValueError("invalid session metadata")
    request_id = uuid.uuid4().hex
    values = [session, request_id, config["operation"]] + config.get("args", [])
    if len(values) > 260 or any(len(str(v).encode()) > 65536 for v in values):
        raise ValueError("request too large")
    payload = "\n".join(base64.b64encode(str(v).encode()).decode() for v in values)
    pending = root / (request_id + ".req")
    temp = root / (request_id + ".tmp")
    response = root / (request_id + ".res")
    with open(str(temp), "x") as stream:
        stream.write(payload + "\n")
    os.replace(str(temp), str(pending))
    deadline = time.monotonic() + float(config.get("timeout", 15))
    while time.monotonic() < deadline:
        if response.exists():
            data = json.loads(response.read_text())
            response.unlink()
            if data.get("id") != request_id or data.get("session") != session:
                raise RuntimeError("response identity mismatch")
            return data
        if (root / "session").read_text().strip() != session:
            if pending.exists():
                pending.unlink()
            raise RuntimeError("Verdi session changed during request")
        time.sleep(0.05)
    try:
        pending.unlink()
        state = "cancelled before execution"
    except FileNotFoundError:
        state = "execution status unknown; inspect GUI before retrying"
    raise TimeoutError("bridge timeout: " + state)


def main():
    try:
        print(json.dumps(exchange(json.load(sys.stdin))))
    except Exception as exc:
        print(json.dumps({"transport_error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
