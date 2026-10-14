"""Waveform double mirroring tests/fake_verdi.tcl (1 ps ticks)."""
import io
import os
import re
import time


class VctFormat_e:
    BinStrVal, OctStrVal, DecStrVal, HexStrVal = range(4)


def _clock():
    return [(t, str((t // 5000) % 2)) for t in range(0, 1000001, 5000)]


# Aliased signals: slow to read unless their changes were loaded from time 0.
ALIASES = {"tb.alias0", "tb.alias1", "tb.alias2", "tb.alias3"}
# Per-signal loaded range start. Like the vendor reader, a signal that is already
# loaded keeps its range until unload_vc(), even if a later load asks for time 0.
LOADED = {}
SIG_LIST = []

SIGNALS = {
    "tb.clk": _clock(),
    "tb.pulse": [(0, "0"), (5000, "1"), (5001, "0")],
    "tb.flat": [(0, "x")],
    "tb.signed": [(0, "11111111")],
    "tb.sleepy": [(0, "1")],
}
SIGNALS.update({name: [(0, "0"), (7000, "1")] for name in ALIASES})


def is_fsdb(name):
    return name.endswith(".fsdb")


def open(name):
    if os.environ.get("FAKE_NPI_NO_LICENSE") or not os.path.isfile(name):
        return None
    return FileHandle()


def close(handle):
    return None


class FileHandle:
    def scale_unit(self):
        return "1ps"

    def has_glitch(self):
        return False

    def sig_by_name(self, name):
        name = re.sub(r"\[[0-9]+:[0-9]+\]$", "", name)
        return SigHandle(name) if name in SIGNALS else None

    def reset_sig_list(self):
        del SIG_LIST[:]
        return True

    def add_to_sig_list(self, signal):
        SIG_LIST.append(signal.name)
        return True

    def load_vc_by_range(self, start, end):
        for name in SIG_LIST:
            LOADED.setdefault(name, start)
        if os.environ.get("FAKE_NPI_LOG"):
            with io.open(os.environ["FAKE_NPI_LOG"], "a") as log:
                log.write("load %d %d\n" % (start, end))
        time.sleep(float(os.environ.get("FAKE_NPI_LOAD_SECONDS", "0")))
        # Real loads allocate per value change; let tests ask for a large allocation.
        self.buffer = bytearray(int(os.environ.get("FAKE_NPI_ALLOC_MB", "0")) << 20)
        return True

    def unload_vc(self):
        LOADED.clear()
        return True


class SigHandle:
    def __init__(self, name):
        self.name = name

    def create_vct(self):
        return Vct(self.name)


class Vct:
    def __init__(self, name):
        self.name, self.changes, self.index = name, SIGNALS[name], 0

    def goto_time(self, t):
        before = [i for i, (time, _) in enumerate(self.changes) if time <= t]
        self.index = before[-1] if before else 0
        return bool(before)

    def goto_first(self):
        self.index = 0
        return True

    def goto_next(self):
        if self.index + 1 >= len(self.changes):
            return False
        self.index += 1
        return True

    def time(self):
        return self.changes[self.index][0]

    def value(self, fmt=VctFormat_e.BinStrVal):
        if self.name in ALIASES and LOADED.get(self.name) != 0:
            time.sleep(0.05)
            if os.environ.get("FAKE_NPI_LOG"):
                with io.open(os.environ["FAKE_NPI_LOG"], "a") as log:
                    log.write("slow %s\n" % self.name)
        bits = self.changes[self.index][1]
        if fmt == VctFormat_e.BinStrVal or not re.fullmatch("[01]+", bits):
            return bits
        number = int(bits, 2)
        if fmt == VctFormat_e.HexStrVal:
            return format(number, "0%dx" % ((len(bits) + 3) // 4))
        return str(number)

    def release(self):
        return None
