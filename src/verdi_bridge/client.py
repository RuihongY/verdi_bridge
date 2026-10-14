"""Typed client; arguments never become executable Tcl or shell fragments."""
import base64
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from builtins import max as builtin_max
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import remote_io


class BridgeError(RuntimeError):
    pass


# Same default as bridge.tcl; "~" expands on the Verdi host, not the client.
DEFAULT_DIR = "~/.verdi-bridge/session"
# The remote login shell may be sh, bash or csh/tcsh. Keep the command to one
# short line without newlines or "!"; the helper source arrives on stdin.
REMOTE_BOOTSTRAP = "python3 -u -c 'import base64,sys;exec(base64.b64decode(sys.stdin.readline()))'"


@dataclass
class Config:
    directory: str = DEFAULT_DIR
    host: str | None = None
    control_path: str | None = None
    timeout: float = 15
    persistent: bool = True
    poll_ms: int = 10

    @classmethod
    def from_env(cls):
        directory = os.environ.get("VERDI_BRIDGE_DIR") or DEFAULT_DIR
        return cls(directory, os.getenv("VERDI_BRIDGE_HOST"),
                   os.getenv("VERDI_BRIDGE_CONTROL_PATH"),
                   persistent=os.getenv("VERDI_BRIDGE_PERSISTENT", "1") != "0",
                   poll_ms=int(os.getenv("VERDI_BRIDGE_POLL_MS", "10")))


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
        self._lock = threading.Lock()
        self._process = None
        self._stderr = None

    def close(self):
        with self._lock:
            self._stop()

    def _stop(self):
        if self._process is not None:
            proc, self._process = self._process, None
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            with suppress(OSError):
                proc.stdin.close()
            with suppress(OSError):
                proc.stdout.close()
        if self._stderr is not None:
            self._stderr.close()
            self._stderr = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _command(self, stream=False):
        cfg = self.config
        if cfg.host:
            if cfg.host.startswith("-") or any(c.isspace() for c in cfg.host):
                raise ValueError("host must be an SSH hostname or user@hostname")
            command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
            if cfg.control_path:
                command += ["-S", cfg.control_path]
            remote = REMOTE_BOOTSTRAP + (" --stream" if stream else "")
            return command + [cfg.host, remote]
        return [sys.executable, str(Path(remote_io.__file__))]

    def _preamble(self):
        # First stdin line for REMOTE_BOOTSTRAP: the helper source in base64.
        if not self.config.host:
            return ""
        return base64.b64encode(Path(remote_io.__file__).read_bytes()).decode() + "\n"

    def _stream_exchange(self, payload):
        # One in-flight request per helper. A broken/slow helper is discarded;
        # never replay a request whose GUI execution status is unknown.
        with self._lock:
            if self._process is not None and self._process.poll() is not None:
                self._stop()
                raise BridgeError("Transport disconnected; execution status unknown")
            if self._process is None:
                self._stderr = tempfile.TemporaryFile(mode="w+t")
                try:
                    self._process = subprocess.Popen(
                        self._command(stream=True), stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=self._stderr, text=True, bufsize=1)
                    self._process.stdin.write(self._preamble())
                    self._process.stdin.flush()
                except Exception:
                    self._stop()
                    raise
            proc = self._process
            result = queue.Queue()

            def transact():
                try:
                    proc.stdin.write(payload + "\n")
                    proc.stdin.flush()
                    result.put((proc.stdout.readline(), None))
                except Exception as exc:
                    result.put((None, exc))

            worker = threading.Thread(target=transact, daemon=True)
            worker.start()
            try:
                line, error = result.get(timeout=self.config.timeout + 15)
            except queue.Empty as exc:
                self._stop()
                raise BridgeError("Transport timeout; execution status unknown") from exc
            if error or not line:
                self._stderr.seek(0)
                detail = self._stderr.read()[-1500:]
                self._stop()
                raise BridgeError("Transport disconnected; execution status unknown: " + detail)
            try:
                return json.loads(line)
            except ValueError as exc:
                self._stop()
                raise BridgeError("Invalid helper response; execution status unknown") from exc

    def _call(self, operation, *args):
        cfg = self.config
        payload = json.dumps({"directory": cfg.directory, "operation": operation,
                              "args": list(args), "timeout": cfg.timeout, "poll_ms": cfg.poll_ms})
        if len(payload.encode()) > 262144:
            raise ValueError("request too large")
        if cfg.host and cfg.persistent:
            response = self._stream_exchange(payload)
        else:
            try:
                proc = subprocess.run(self._command(), input=self._preamble() + payload, text=True,
                                      capture_output=True, timeout=cfg.timeout + 15)
            except subprocess.TimeoutExpired as exc:
                raise BridgeError("Transport timeout; execution status unknown") from exc
            try:
                response = json.loads(proc.stdout)
            except ValueError as exc:
                raise BridgeError("Transport failed: " + proc.stderr[-1500:]) from exc
            if proc.returncode and "transport_error" not in response:
                raise BridgeError("Transport failed: " + proc.stderr[-1500:])
        if "transport_error" in response:
            raise BridgeError(response["transport_error"])
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

    def before_error(self, error_time: str, period: str | None = None, cycles: int = 20,
                     unit: str = "ns", clock_signal: str | None = None,
                     window: str | None = None):
        if not 0 <= cycles <= 1000000:
            raise ValueError("cycles must be 0..1000000")
        if period is None:
            if not clock_signal:
                raise ValueError("supply period or clock_signal")
            measured = self.measure_clock(clock_signal, error_time, unit, window)
            if not measured["constant_in_window"]:
                raise BridgeError("Clock is not constant in the measured window")
            period = measured["period"]
        if Decimal(number(period)) <= 0:
            raise ValueError("period must be positive")
        target = Decimal(number(error_time)) - Decimal(number(period)) * cycles
        snapped = None
        if clock_signal and target >= 0:
            measured = self.measure_clock(clock_signal, str(target), unit, window)
            if (not measured["constant_in_window"] or
                    abs(Decimal(measured["period"])-Decimal(period)) >
                    Decimal(period)*Decimal("1e-9")):
                raise BridgeError("Clock period near target disagrees with requested period")
            earlier = [Decimal(e) for e in measured["rising_edges"] if Decimal(e) <= target]
            if not earlier:
                raise BridgeError("No observed rising edge before target; expand window")
            snapped = max(earlier)
        cursor = snapped if snapped is not None else max(Decimal(0), target)
        result = self.set_cursor(str(cursor), unit)
        return {**result, "clamped_at_zero": target < 0, "cycles": cycles,
                "period": period, "snapped_to_rising_edge": snapped is not None,
                "note": ("Snapped to an observed edge at/before target; assumes constant clock between windows"
                         if snapped is not None else
                         "Preserves timestamp phase; does not snap to clock edges")}

    def sample(self, signals: list[str], times: list[str], unit: str = "ns", radix: str = "Bin"):
        if not 1 <= len(signals) <= 128 or not 1 <= len(times) <= 128:
            raise ValueError("supply 1..128 signals and times")
        if len(signals) * len(times) > 1024:
            raise ValueError("at most 1024 samples per request")
        if radix not in ("Bin", "Hex", "UDec", "Dec", "SDec"):
            raise ValueError("radix must be Bin, Hex, UDec, Dec or SDec")
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

    def find_transitions(self, signal: str, start: str, end: str, max: int = 64,
                         unit: str = "ns", radix: str = "Bin", budget_ms: int = 200):
        return self.get_value_changes([signal], start, end, max, unit, radix, budget_ms)

    def get_value_changes(self, signals: list[str], start: str, end: str,
                          max: int = 64, unit: str = "ns", radix: str = "Bin", budget_ms: int = 200):
        if not 1 <= budget_ms <= 2000:
            raise ValueError("budget_ms must be 1..2000")
        if not 1 <= len(signals) <= 128 or not 1 <= max <= 4096:
            raise ValueError("supply 1..128 signals; max must be 1..4096 (per signal)")
        if len(signals) * max > 4096:
            raise ValueError("at most 4096 changes across signals")
        if Decimal(number(end)) <= Decimal(number(start)):
            raise ValueError("end must be greater than start")
        if radix not in ("Bin", "Hex", "UDec", "Dec", "SDec"):
            raise ValueError("radix must be Bin, Hex, UDec, Dec or SDec")
        return self._call("changes", number(start), number(end), unit, radix, str(max), str(budget_ms), *signals)

    def find_signals(self, pattern: str, scope: str = "/", max: int = 100,
                     depth: int = 16, glob: bool = False, budget_ms: int = 1000):
        if not pattern or len(pattern) > 4096 or not 1 <= max <= 1000 or not 0 <= depth <= 64:
            raise ValueError("pattern required; max 1..1000; depth 0..64")
        if not 1 <= budget_ms <= 2000:
            raise ValueError("budget_ms must be 1..2000")
        return self._call("find_signals", pattern, scope, str(max), str(depth),
                          "1" if glob else "0", str(budget_ms))

    def source_file(self, file: str, start: int = 1, count: int = 80):
        if start < 1 or not 1 <= count <= 200:
            raise ValueError("start >= 1 and count 1..200 required")
        return self._call("source_file", file, str(start), str(count))

    def read_log(self, path: str, pattern: str = "ERROR", max_lines: int = 40):
        if not 1 <= max_lines <= 200 or len(pattern) > 4096:
            raise ValueError("max_lines 1..200; pattern at most 4096 characters")
        return self._call("read_log", path, pattern, str(max_lines))

    def measure_clock(self, signal: str, around_time: str, unit: str = "ns",
                      window: str | None = None, max: int = 256):
        if window is None:
            defaults = {"fs": "100000000", "ps": "100000", "ns": "100",
                        "us": "0.1", "ms": "0.0001", "s": "0.0000001"}
            if unit not in defaults:
                raise ValueError("unit must be fs/ps/ns/us/ms/s")
            window = defaults[unit]
        center, width = Decimal(number(around_time)), Decimal(number(window))
        if width <= 0:
            raise ValueError("window must be positive")
        result = self.find_transitions(signal, str(builtin_max(Decimal(0), center-width)),
                                       str(center+width), max, unit)
        edges = [Decimal(c["time"]) for c in result["signals"][0]["changes"]
                 if c["before"].strip() == "0" and c["after"].strip() == "1"]
        if len(edges) < 3 or result["truncated"]:
            raise BridgeError("Need at least three rising edges in an untruncated window; adjust window/max")
        periods = [b-a for a, b in zip(edges, edges[1:])]
        ordered = sorted(periods)
        period = ordered[len(ordered)//2]
        constant = all(abs(p-period) <= abs(period)*Decimal("1e-9") for p in periods)
        return {"signal": signal, "unit": unit, "period": str(period),
                "phase": str(edges[0] % period), "rising_edges": [str(e) for e in edges],
                "constant_in_window": constant, "window": result["interval"],
                "note": "Local observation only; skipped glitches and gated/missing edges can bias period"}
