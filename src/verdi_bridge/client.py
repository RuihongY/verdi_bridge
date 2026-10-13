"""Typed client; arguments never become executable Tcl or shell fragments."""
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import remote_io


class BridgeError(RuntimeError):
    pass


@dataclass
class Config:
    directory: str
    host: str | None = None
    control_path: str | None = None
    timeout: float = 15

    @classmethod
    def from_env(cls):
        directory = os.environ.get("VERDI_BRIDGE_DIR")
        if not directory:
            raise BridgeError("Set VERDI_BRIDGE_DIR to the private bridge directory")
        return cls(directory, os.getenv("VERDI_BRIDGE_HOST"),
                   os.getenv("VERDI_BRIDGE_CONTROL_PATH"))


def number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("time must be numeric") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("time must be finite and nonnegative")
    return str(result)


class Client:
    def __init__(self, config: Config):
        self.config = config

    def _call(self, operation, *args):
        cfg = self.config
        payload = {"directory": cfg.directory, "operation": operation,
                   "args": list(args), "timeout": cfg.timeout}
        if cfg.host:
            if cfg.host.startswith("-") or any(c.isspace() for c in cfg.host):
                raise ValueError("host must be an SSH hostname or user@hostname")
            command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
            if cfg.control_path:
                command += ["-S", cfg.control_path]
            command += [cfg.host, "python3 -c " + shlex.quote(Path(remote_io.__file__).read_text())]
        else:
            command = [sys.executable, str(Path(remote_io.__file__))]
        try:
            proc = subprocess.run(command, input=json.dumps(payload), text=True,
                                  capture_output=True, timeout=cfg.timeout + 15)
        except subprocess.TimeoutExpired as exc:
            raise BridgeError("Transport timeout; execution status unknown") from exc
        try:
            response = json.loads(proc.stdout)
        except ValueError as exc:
            raise BridgeError("Transport failed: " + proc.stderr[-1500:]) from exc
        if proc.returncode or "transport_error" in response:
            raise BridgeError(response.get("transport_error", proc.stderr[-1500:]))
        if not response["ok"]:
            raise BridgeError(response["error"])
        return response["result"]

    def status(self):
        return self._call("status")

    def browse(self, scope: str = "/"):
        return self._call("browse", scope)

    def add_signals(self, signals: list[str]):
        if not 1 <= len(signals) <= 128:
            raise ValueError("supply 1..128 signals")
        return self._call("add_signals", *signals)

    def set_cursor(self, time: str, unit: str = "ns"):
        return self._call("cursor", number(time), unit)

    def set_window(self, start: str, end: str, unit: str = "ns"):
        if Decimal(number(end)) <= Decimal(number(start)):
            raise ValueError("end must be greater than start")
        return self._call("window", number(start), number(end), unit)

    def before_error(self, error_time: str, period: str, cycles: int = 20, unit: str = "ns"):
        if not 0 <= cycles <= 1000000 or Decimal(number(period)) <= 0:
            raise ValueError("cycles must be 0..1000000; period must be positive")
        target = Decimal(number(error_time)) - Decimal(number(period)) * cycles
        result = self.set_cursor(str(max(Decimal(0), target)), unit)
        return {**result, "clamped_at_zero": target < 0, "cycles": cycles,
                "note": "Preserves timestamp phase; does not snap to clock edges"}

    def sample(self, signals: list[str], times: list[str], unit: str = "ns", radix: str = "Bin"):
        if not 1 <= len(signals) <= 128 or not 1 <= len(times) <= 128:
            raise ValueError("supply 1..128 signals and times")
        if len(signals) * len(times) > 1024:
            raise ValueError("at most 1024 samples per request")
        if radix not in ("Bin", "Hex", "UDec"):
            raise ValueError("radix must be Bin, Hex or UDec")
        return self._call("sample", unit, radix, str(len(signals)), *signals,
                          *(number(t) for t in times))

    def trace_driver(self, signal: str):
        return self._call("trace_driver", signal)

    def source(self, signal: str, start: int = 1, count: int = 80):
        if start < 1 or not 1 <= count <= 200:
            raise ValueError("start >= 1 and count 1..200 required")
        return self._call("source", signal, str(start), str(count))

    def goto_source(self, scope: str, line: int):
        if line < 1:
            raise ValueError("line must be positive")
        return self._call("goto_source", scope, str(line))
