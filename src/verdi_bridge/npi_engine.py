"""Headless waveform queries through Verdi's Python NPI FSDB reader.

Runs on the Verdi host as a short-lived process per request (Python 3.6+), so long
scans never block the GUI and any license it checks out is released on exit.
Results use the same shapes, units and value formatting as the GUI adapter.
Input: one JSON line {"fsdb", "verdi_home", "env", "operation", "args"}.
Output: one JSON line {"ok": true, "result": ...} or {"ok": false, "error": ...}.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time
from fractions import Fraction

# A first value read slower than this means the signal is aliased or sparse.
SLOW_TOUCH_SECONDS = 0.03
SLOW_TOUCHES = 2
UNIT_EXP = {"fs": -15, "ps": -12, "ns": -9, "us": -6, "ms": -3, "s": 0}
MAX_TICK = 9007199254740991


class Unavailable(RuntimeError):
    """The engine cannot serve this request; the caller may use the GUI instead."""


def decimal_ratio(text):
    match = re.fullmatch(r"([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?", str(text))
    if not match or len(str(text)) > 128:
        raise ValueError("expected finite nonnegative decimal")
    whole, frac, exponent = match.group(1), match.group(2) or "", int(match.group(3) or 0)
    if abs(exponent) > 30:
        raise ValueError("decimal exponent out of range")
    return Fraction(int(whole + frac), 10 ** len(frac)) * Fraction(10) ** exponent


class Clock:
    """Exact conversion between physical times and integer FSDB ticks."""

    def __init__(self, scale_unit):
        match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(fs|ps|ns|us|ms|s)\s*", scale_unit)
        if not match:
            raise Unavailable("unsupported FSDB scale unit: " + scale_unit)
        self.tick = decimal_ratio(match.group(1)) * Fraction(10) ** UNIT_EXP[match.group(2)]

    def ticks(self, value, unit):
        if unit not in UNIT_EXP:
            raise ValueError("unit must be fs/ps/ns/us/ms/s")
        ticks = decimal_ratio(value) * Fraction(10) ** UNIT_EXP[unit] / self.tick
        if ticks.denominator != 1:
            raise ValueError("time is not aligned to a native waveform tick")
        if ticks > MAX_TICK:
            raise ValueError("time exceeds exact vendor tick range (2^53-1)")
        return int(ticks)

    def physical(self, ticks, unit):
        value = Fraction(ticks) * self.tick / Fraction(10) ** UNIT_EXP[unit]
        whole, rem = divmod(value.numerator, value.denominator)
        digits = ""
        while rem and len(digits) < 128:
            rem *= 10
            digit, rem = divmod(rem, value.denominator)
            digits += str(digit)
        if rem:
            raise ValueError("time cannot be represented as finite decimal")
        return str(whole) + ("." + digits if digits else "")


class Waves:
    def __init__(self, waveform, handle):
        self.waveform = waveform
        self.file = handle
        self.formats = waveform.VctFormat_e
        self.clock = Clock(handle.scale_unit())
        self.glitches = bool(handle.has_glitch())
        self.signals = {}
        self.load_info = None

    def signal(self, path):
        # nWave path /tb/u/sig[3:0] -> NPI name tb.u.sig[3:0]
        if path not in self.signals:
            if not path.startswith("/"):
                raise ValueError("use an absolute waveform path beginning with /")
            handle = self.file.sig_by_name(path[1:].replace("/", "."))
            if handle is None:
                raise Unavailable("signal not found by NPI: " + path)
            self.signals[path] = handle
        return self.signals[path]

    def _load(self, paths, lo, hi):
        self.file.reset_sig_list()
        for path in paths:
            self.file.add_to_sig_list(self.signal(path))
        self.file.load_vc_by_range(lo, hi)

    def load(self, paths, lo, hi):
        """Load value changes for [lo, hi] without either known failure mode.

        Measured on Verdi 2022.06 NPI: loading only the window is fast for dense
        signals, but aliased or sparse signals then take ~0.15 s each to resolve their
        value at lo. Loading from time 0 resolves those in one batch, but costs memory
        proportional to every change before hi (3.2 GB for 256 dense signals of a
        2.7 GB FSDB). So load the window, touch each signal once, and after
        SLOW_TOUCHES slow ones load the untouched remainder from time 0.
        """
        self._load(paths, lo, hi)
        fast, slow = [], []
        for path in paths:
            began = time.monotonic()
            vct = self.cursor(path)
            vct.goto_time(lo)
            vct.value(self.formats.BinStrVal)
            vct.release()
            (slow if time.monotonic() - began > SLOW_TOUCH_SECONDS else fast).append(path)
            if len(slow) >= SLOW_TOUCHES:
                break
        if len(slow) >= SLOW_TOUCHES:
            # A signal already loaded for the window is not reloaded from time 0, so
            # start over: slow and untouched signals from 0, fast ones for the window.
            from_zero = [path for path in paths if path not in fast]
            self.file.unload_vc()
            self._load(from_zero, 0, hi)
            if fast:
                self._load(fast, lo, hi)
        else:
            from_zero = []
        self.load_info = {"window_loaded": len(paths) - len(from_zero),
                          "loaded_from_zero": len(from_zero)}

    def cursor(self, path):
        vct = self.signal(path).create_vct()
        if vct is None:
            raise Unavailable("cannot traverse " + path)
        return vct

    def value(self, vct, radix):
        """Format like the GUI adapter: no leading zeros except SDec's full width."""
        if radix == "SDec":
            bits = vct.value(self.formats.BinStrVal)
            if not re.fullmatch(r"[01]+", bits):
                return bits
            number = int(bits, 2)
            return str(number - (1 << len(bits)) if bits[0] == "1" else number)
        fmt = {"Bin": self.formats.BinStrVal, "Hex": self.formats.HexStrVal,
               "UDec": self.formats.DecStrVal, "Dec": self.formats.DecStrVal}[radix]
        text = vct.value(fmt)
        if radix in ("Bin", "Hex"):
            text = text.lstrip("0") or "0"
        return text


def changes_after(vct, start_tick, end_tick):
    """Yield (time, None) for each timestamp with a change in (start, end]. Several
    changes at one timestamp collapse into one, like the GUI skipping glitches."""
    if not vct.goto_time(start_tick):
        vct.goto_first()
    last = None
    while vct.goto_next():
        t = vct.time()
        if t <= start_tick:
            continue
        if t > end_tick:
            break
        if t != last:
            last = t
            yield t


def check_budget(budget_ms, limit=10000):
    # Timed from after the batch load; each call returns some progress.
    if not isinstance(budget_ms, int) or not 1 <= budget_ms <= limit:
        raise ValueError("budget_ms must be 1..%d" % limit)


def op_count(w, a):
    clk, unit = w.clock, a["unit"]
    start, end = clk.ticks(a["start"], unit), clk.ticks(a["end"], unit)
    if end <= start:
        raise ValueError("end must exceed start")
    check_budget(a["budget_ms"])
    w.load(a["signals"], start, end)
    deadline = time.monotonic() + a["budget_ms"] / 1000.0
    rows, any_truncated = [], False
    for path in a["signals"]:
        if rows and time.monotonic() >= deadline:
            any_truncated = True
            rows.append({"signal": path, "count": None, "complete": False,
                         "resume_from": a["start"]})
            continue
        vct, probe = w.cursor(path), w.cursor(path)
        vct.goto_time(start)
        initial = w.value(vct, "Hex")
        count, first, t, complete = 0, None, start, True
        previous = initial
        for t_next in changes_after(vct, start, end):
            if (count or rows) and time.monotonic() >= deadline:
                complete, any_truncated = False, True
                break
            if w.glitches:
                # Changes that return to the old value within one timestamp are glitches.
                probe.goto_time(t_next)
                now = w.value(probe, "Hex")
                if now == previous:
                    continue
                previous = now
            count, t = count + 1, t_next
            first = t_next if first is None else first
        if complete:
            probe.goto_time(t)
            previous = w.value(probe, "Hex")
        vct.release()
        probe.release()
        row = {"signal": path, "count": count, "complete": complete, "initial": initial,
               "first_change": None if first is None else clk.physical(first, unit),
               "last_change": clk.physical(t, unit) if count else None}
        if complete:
            row["final"] = previous
        else:
            row["resume_from"] = clk.physical(t, unit)
        rows.append(row)
    return {"unit": unit, "interval": [a["start"], a["end"]],
            "boundary": "(start, end]; initial is the Hex value at start",
            "signals": rows, "truncated": any_truncated, "budget_ms": a["budget_ms"],
            "glitches_skipped": True}


def op_changes(w, a):
    clk, unit, radix, limit = w.clock, a["unit"], a["radix"], a["max"]
    start, end = clk.ticks(a["start"], unit), clk.ticks(a["end"], unit)
    if end <= start:
        raise ValueError("end must exceed start")
    check_budget(a["budget_ms"], 10000)
    w.load(a["signals"], start, end)
    deadline = time.monotonic() + a["budget_ms"] / 1000.0
    results, reasons, any_truncated = [], set(), False
    for path in a["signals"]:
        if results and time.monotonic() >= deadline:
            any_truncated = True
            reasons.add("time budget")
            results.append({"signal": path, "initial": None, "changes": [], "truncated": True,
                            "reason": "time budget", "resume_from": a["start"]})
            continue
        vct, probe = w.cursor(path), w.cursor(path)
        vct.goto_time(start)
        initial = previous = w.value(vct, radix)
        rows, t, reason = [], start, ""
        for t_next in changes_after(vct, start, end):
            if (rows or results) and time.monotonic() >= deadline:
                reason = "time budget"
                break
            probe.goto_time(t_next)
            after = w.value(probe, radix)
            if after == previous:
                continue
            if len(rows) == limit:
                reason = "max changes"
                break
            rows.append({"time": clk.physical(t_next, unit), "before": previous, "after": after})
            previous, t = after, t_next
        vct.release()
        probe.release()
        if reason:
            reasons.add(reason)
            any_truncated = True
        results.append({"signal": path, "initial": initial, "changes": rows,
                        "truncated": bool(reason), "reason": reason,
                        "resume_from": clk.physical(t, unit)})
    return {"unit": unit, "radix": radix, "interval": [a["start"], a["end"]],
            "boundary": "(start, end]; initial is the value at start", "signals": results,
            "truncated": any_truncated, "reasons": sorted(reasons),
            "budget_ms": a["budget_ms"], "glitches_skipped": True}


def op_sample(w, a):
    clk, unit, radix = w.clock, a["unit"], a["radix"]
    ticks = [clk.ticks(t, unit) for t in a["times"]]
    check_budget(a["budget_ms"])
    w.load(a["signals"], min(ticks), max(ticks))
    deadline = time.monotonic() + a["budget_ms"] / 1000.0
    rows, pending = [], []
    for path in a["signals"]:
        if rows and time.monotonic() >= deadline:
            pending.append(path)
            continue
        vct = w.cursor(path)
        for text, tick in zip(a["times"], ticks):
            vct.goto_time(tick)
            rows.append({"signal": path, "time": text, "unit": unit,
                         "value": w.value(vct, radix)})
        vct.release()
    return {"radix": radix, "samples": rows, "truncated": bool(pending),
            "pending_signals": pending, "budget_ms": a["budget_ms"]}


def op_clock_table(w, a):
    clk, unit, radix = w.clock, a["unit"], a["radix"]
    start, end = clk.ticks(a["start"], unit), clk.ticks(a["end"], unit)
    if end <= start:
        raise ValueError("end must exceed start")
    check_budget(a["budget_ms"])
    w.load([a["clock"]] + a["signals"], start, end)
    deadline = time.monotonic() + a["budget_ms"] / 1000.0
    edges, level_probe = w.cursor(a["clock"]), w.cursor(a["clock"])
    readers = [w.cursor(path) for path in a["signals"]]
    rows, t, reason = [], start, ""
    for nt in changes_after(edges, start, end):
        if rows and time.monotonic() >= deadline:
            reason = "time budget"
            break
        level_probe.goto_time(nt)
        level = w.value(level_probe, "Bin")
        if (level == "1" and a["edge"] != "falling") or (level == "0" and a["edge"] != "rising"):
            if len(rows) == a["max"]:
                reason = "max cycles"
                break
            # "pre" reads one FSDB tick before the edge: the values flops capture.
            st = nt - 1 if a["sample"] == "pre" and nt > 0 else nt
            values = []
            for vct in readers:
                vct.goto_time(st)
                values.append(w.value(vct, radix))
            rows.append({"time": clk.physical(nt, unit),
                         "edge": "rising" if level == "1" else "falling", "values": values})
        t = nt
    for vct in [edges, level_probe] + readers:
        vct.release()
    return {"clock": a["clock"], "unit": unit, "radix": radix, "edge": a["edge"],
            "sample": a["sample"], "signals": a["signals"], "cycles": rows,
            "truncated": bool(reason), "reason": reason,
            "resume_from": clk.physical(t, unit), "budget_ms": a["budget_ms"]}


OPERATIONS = {"count": op_count, "changes": op_changes, "sample": op_sample,
              "clock_table": op_clock_table}


def peak_megabytes():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    except ImportError:
        return None


def limit_memory(megabytes):
    """Fail this process, not the shared host, if a query would exhaust memory."""
    try:
        import resource
        if not megabytes:
            pages, page = os.sysconf("SC_PHYS_PAGES"), os.sysconf("SC_PAGE_SIZE")
            megabytes = pages * page // 2 // (1 << 20)
        limit = int(megabytes) << 20
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, ValueError, OSError):
        pass


def run(request):
    operation = OPERATIONS.get(request.get("operation"))
    if operation is None:
        raise ValueError("unsupported engine operation")
    fsdb = request["fsdb"]
    if not os.path.isabs(fsdb) or not os.path.isfile(fsdb):
        raise Unavailable("active waveform is not a readable file: " + fsdb)
    for name, value in request.get("env", {}).items():
        if name in ("SNPSLMD_LICENSE_FILE", "LM_LICENSE_FILE") and value:
            os.environ[name] = value
    os.environ["VERDI_HOME"] = request["verdi_home"]
    sys.path.append(os.path.join(request["verdi_home"], "share", "NPI", "python"))
    try:
        from pynpi import npisys, waveform
    except ImportError as exc:
        raise Unavailable("NPI Python bindings unavailable: %s" % exc)
    if not waveform.is_fsdb(fsdb):
        raise Unavailable("active waveform is not FSDB")
    if not npisys.init([sys.argv[0]]):
        raise Unavailable("NPI initialization failed")
    try:
        handle = waveform.open(fsdb)
        if handle is None:
            raise Unavailable("NPI could not open the FSDB (license or file access)")
        try:
            waves = Waves(waveform, handle)
            result = operation(waves, request["args"])
            result["npi_load"] = waves.load_info
            result["npi_peak_mb"] = peak_megabytes()
            return result
        finally:
            waveform.close(handle)
    finally:
        npisys.end()


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def private_workdir():
    """Per-process directory for vendor side files (npiLog/, crash reports).

    An engine that the memory limit aborts cannot clean up after itself, so each
    start removes directories left by engine processes that no longer exist.
    """
    parent = os.path.join(tempfile.gettempdir(), "verdi-bridge-npi-%d" % os.getuid())
    try:
        os.makedirs(parent, mode=0o700, exist_ok=True)
        info = os.lstat(parent)
        if (not os.path.isdir(parent) or os.path.islink(parent) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise OSError("unsafe engine work directory")
    except OSError:
        return tempfile.mkdtemp(prefix="verdi-bridge-npi-")
    for name in os.listdir(parent):
        if name.isdigit() and not pid_alive(int(name)):
            shutil.rmtree(os.path.join(parent, name), ignore_errors=True)
    path = os.path.join(parent, str(os.getpid()))
    os.mkdir(path, 0o700)
    return path


def main():
    request = json.loads(sys.stdin.readline())
    # NPI prints banners on stdout; keep the real stdout for the single JSON reply.
    reply = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    limit_memory(request.get("max_memory_mb"))
    workdir = private_workdir()
    os.chdir(workdir)  # npiLog/ and other vendor side files land here
    try:
        response = {"ok": True, "result": run(request)}
    except Unavailable as exc:
        response = {"ok": False, "unavailable": True, "error": str(exc)}
    except MemoryError:
        response = {"ok": False, "unavailable": True,
                    "error": "NPI engine reached its memory limit; narrow the window or signals"}
    except Exception as exc:
        response = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        os.chdir("/")
        shutil.rmtree(workdir, ignore_errors=True)
    reply.write(json.dumps(response) + "\n")
    reply.flush()


if __name__ == "__main__":
    main()
