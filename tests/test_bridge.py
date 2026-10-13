import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from verdi_bridge import client as client_module
from verdi_bridge.client import BridgeError, Client, Config
from verdi_bridge.remote_io import exchange


@pytest.fixture
def running(tmp_path):
    if not shutil.which("tclsh"):
        pytest.fail("Tcl 8.6+ is required for transport tests")
    root = tmp_path / "bridge"
    root.mkdir(mode=0o700)
    source = tmp_path / "source.sv"
    source.write_text('module fifo;\n// quote " slash \\ unicode 中文\nendmodule\n')
    env = {**os.environ, "VERDI_BRIDGE_DIR": str(root),
           "VERDI_BRIDGE_SOURCE_ROOTS": str(tmp_path), "TEST_SOURCE": str(source),
           "TEST_LITERAL_SIGNAL": '/tb/a[3:0]; [exec touch INJECTED] $env(HOME) {} "'}
    tcl = Path(client_module.__file__).with_name("bridge.tcl")
    proc = subprocess.Popen(["tclsh", str(Path(__file__).with_name("fake_verdi.tcl")), str(tcl)],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for _ in range(100):
        if (root / "session").exists():
            break
        if proc.poll() is not None:
            pytest.fail(proc.stderr.read().decode())
        time.sleep(0.02)
    else:
        proc.kill()
        pytest.fail("Tcl fixture did not start")
    yield Client(Config(str(root), timeout=2)), env
    proc.terminate()
    proc.communicate(timeout=3)


def test_units_navigation_and_xz(running):
    client, _ = running
    assert client.status()["time_unit"] == "1ps"
    assert float(client.before_error("356", "10")["cursor"][1]) == pytest.approx(156000)
    assert client.before_error("5", "10")["clamped_at_zero"]
    assert list(map(float, client.set_window("0.1", "0.2", "us")["viewport"][1:])) == pytest.approx([100000, 200000])
    assert client.sample(["/tb/full"], ["0"])["samples"][0]["value"] == "10xz"
    assert client.browse()["scopes"] == ["/tb/dut"]
    assert client.goto_source("tb.dut", 2)["line"] == 2


def test_arguments_are_data_not_tcl(running, tmp_path):
    client, _ = running
    sentinel = tmp_path / "injected"
    signal = running[1]['TEST_LITERAL_SIGNAL']
    assert client.add_signals([signal])["signals"] == [signal]
    assert not Path("INJECTED").exists()
    assert not sentinel.exists()
    with pytest.raises(BridgeError, match="unsupported operation"):
        client._call("eval", "exec touch " + str(sentinel))
    assert not sentinel.exists()


def test_source_and_path_boundary(running, tmp_path):
    client, env = running
    assert '中文' in client.source("tb.dut", 2, 1)["lines"][0]["text"]
    # A symlink cannot escape the source root because the adapter normalizes it.
    source = Path(env["TEST_SOURCE"])
    source.unlink()
    source.symlink_to("/etc/hosts")
    with pytest.raises(BridgeError, match="outside"):
        client.source("tb.dut")


def test_concurrent_requests_are_correlated(running):
    client, _ = running
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda n: client.sample([f"/tb/s{n}"], [str(n)]), range(16)))
    assert [r["samples"][0]["signal"] for r in results] == [f"/tb/s{n}" for n in range(16)]


def test_validation(running):
    client, _ = running
    for value in ["NaN", "Infinity", "-1", "[exit]"]:
        with pytest.raises(ValueError):
            client.set_cursor(value)
    with pytest.raises(ValueError):
        client.sample(["a"] * 128, ["0"] * 128)
    with pytest.raises(ValueError):
        client.set_window("10", "5")
    with pytest.raises(BridgeError, match="unit must"):
        client.set_cursor("1", "fortnight")


def test_timeout_does_not_accept_stale_result(tmp_path):
    tmp_path.chmod(0o700)
    (tmp_path / "session").write_text("stale-session")
    (tmp_path / "old.res").write_text(json.dumps({"ok": True, "result": "old"}))
    with pytest.raises(TimeoutError, match="cancelled before execution"):
        exchange({"directory": str(tmp_path), "operation": "status", "timeout": .1})
    assert not list(tmp_path.glob("*.req"))


def test_private_directory_required(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match="0700"):
        exchange({"directory": str(tmp_path), "operation": "status"})


def test_mcp_stdio_end_to_end(running):
    _, env = running

    async def run():
        params = StdioServerParameters(command=sys.executable,
                                      args=["-c", "from verdi_bridge.cli import main; main()", "serve"],
                                      env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert len(names) == 16
                assert {p.name for p in (await session.list_prompts()).prompts} == {"debug_failure"}
                assert "sample_signals" in names
                result = await session.call_tool("jump_before_error", {"error_time": "356", "period": "10"})
                assert not result.isError
                assert float(result.structuredContent["cursor"][1]) == pytest.approx(156000)
                bad = await session.call_tool("set_cursor", {"time": "NaN"})
                assert bad.isError
    asyncio.run(run())


def test_missing_signal_is_error(running):
    client, _ = running
    with pytest.raises(BridgeError, match="signal not found"):
        client.sample(["/tb/missing"], ["1"])
    with pytest.raises(BridgeError, match="signal not found"):
        client.add_signals(["/tb/missing"])


def test_interval_narrow_pulse_boundaries_and_restoration(running):
    client, _ = running
    client.set_cursor("22")
    before = client.status()
    result = client.find_transitions("/tb/pulse", "0", "6")
    assert result["signals"][0]["changes"] == [
        {"time": "5", "before": "0", "after": "1"},
        {"time": "5.001", "before": "1", "after": "0"}]
    assert not result["truncated"]
    assert client.status() == before
    assert client.find_transitions("/tb/pulse", "5", "5.001")["signals"][0]["changes"] == [
        {"time": "5.001", "before": "1", "after": "0"}]
    assert client.find_transitions("/tb/pulse", "0", "6", max=1)["truncated"]
    assert not client.find_transitions("/tb/pulse", "0", "5", max=1)["truncated"]
    batch = client.get_value_changes(["/tb/flat", "/tb/pulse"], "0", "6", max=8)
    assert batch["signals"][0]["initial"] == "x"
    assert batch["signals"][0]["changes"] == []
    assert client.sample(["/tb/signed"], ["0"], radix="Dec")["samples"][0]["value"] == "-1"


def test_clock_measurement_and_edge_snap(running):
    client, _ = running
    result = client.measure_clock("/tb/clk", "50", window="40")
    assert Decimal(result["period"]) == 10
    assert Decimal(result["phase"]) == 5
    assert result["constant_in_window"]
    snap = client.before_error("86", cycles=2, clock_signal="/tb/clk")
    assert snap["snapped_to_rising_edge"]
    assert float(snap["cursor"][1]) == 65000
    with pytest.raises(BridgeError, match="three rising edges"):
        client.measure_clock("/tb/flat", "10")
    with pytest.raises(BridgeError, match="disagrees"):
        client.before_error("86", "9", clock_signal="/tb/clk", cycles=2)


def test_recursive_search_limits_and_literal_bus(running):
    client, _ = running
    result = client.find_signals("ptr[3:0]")
    assert "/tb/dut/nested/ptr[3:0]" in result["signals"]
    assert not result["truncated"]
    assert client.find_signals("ptr", depth=0)["truncated"]
    assert client.find_signals("ptr", max=1)["truncated"]
    assert client.find_signals("*/pulse", scope="/tb/dut", depth=1)["signals"] == [
        "/tb/dut/pulse", "/tb/dut/nested/pulse"]


def test_file_reads_log_limits_and_symlinks(running, tmp_path):
    client, env = running
    assert client.source_file(env["TEST_SOURCE"], 2, 1)["lines"][0]["line"] == 2
    log = tmp_path / "sim.log"
    log.write_text("start\nERROR at 10\nerror at 11\nERROR at 12\n")
    result = client.read_log(str(log), max_lines=1)
    assert result["lines"] == [{"line": 2, "text": "ERROR at 10"}]
    assert result["truncated"]
    log.unlink()
    log.symlink_to("/etc/hosts")
    with pytest.raises(BridgeError, match="outside"):
        client.read_log(str(log), pattern="")
    with pytest.raises(BridgeError, match="outside"):
        client.source_file(str(log))


@pytest.mark.parametrize("persistent", [False, True])
def test_ssh_shell_quoting_and_helper_reuse(running, tmp_path, monkeypatch, persistent):
    local, _ = running
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = tmp_path / "ssh-calls"
    shim = bindir / "ssh"
    shim.write_text("#!/usr/bin/env python3\nimport os,sys\n"
                    "with open(os.environ['SSH_CALLS'], 'a') as f: f.write('start\\n')\n"
                    "os.execl('/bin/sh', 'sh', '-c', sys.argv[-1])\n")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("SSH_CALLS", str(calls))
    # Exercise shlex.quote on the *whole helper*, including executable shell-looking text.
    helper = tmp_path / "helper.py"
    helper.write_text(Path(client_module.remote_io.__file__).read_text() +
                      "\n# quotes ' \" `touch INJECTED` $(touch INJECTED) \\ \n")
    monkeypatch.setattr(client_module.remote_io, "__file__", str(helper))
    with Client(Config(local.config.directory, host="test-host", timeout=2,
                       persistent=persistent)) as remote:
        assert remote.status()["time_unit"] == "1ps"
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda n: remote.sample([f"/tb/s{n}"], [str(n)]), range(4)))
        assert [r["samples"][0]["signal"] for r in results] == [f"/tb/s{n}" for n in range(4)]
        with pytest.raises(BridgeError, match="signal not found"):
            remote.sample(["/tb/missing"], ["0"])
        assert remote.status()["time_unit"] == "1ps"
        if persistent:
            proc = remote._process
            proc.kill()
            proc.wait()
            with pytest.raises(BridgeError, match="disconnected"):
                remote.status()
            # A separate explicit next call may establish a new connection.
            assert remote.status()["time_unit"] == "1ps"
    assert len(calls.read_text().splitlines()) == (2 if persistent else 7)
    assert not Path("INJECTED").exists()


def test_interval_error_restores_gui(running):
    client, _ = running
    client.set_cursor('17')
    before = client.status()
    with pytest.raises(BridgeError, match='did not advance'):
        client.find_transitions('/tb/stuck_search', '0', '10')
    assert client.status() == before


def test_parent_symlink_cannot_escape(running, tmp_path):
    client, _ = running
    (tmp_path / 'escape').symlink_to('/etc', target_is_directory=True)
    with pytest.raises(BridgeError, match='outside'):
        client.source_file(str(tmp_path / 'escape/hosts'))


def test_persistent_timeout_is_not_replayed(tmp_path, monkeypatch):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    counter = tmp_path / 'calls'
    shim = bindir / 'ssh'
    shim.write_text('#!/usr/bin/env python3\nimport os,time\n'
                    "with open(os.environ['SSH_CALLS'], 'a') as f: f.write('start\\n')\n"
                    'time.sleep(60)\n')
    shim.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('SSH_CALLS', str(counter))
    original_queue = client_module.queue.Queue

    class ShortDeadlineQueue(original_queue):
        def get(self, block=True, timeout=None):
            return super().get(block=block, timeout=.3)

    monkeypatch.setattr(client_module.queue, 'Queue', ShortDeadlineQueue)
    with Client(Config(str(tmp_path), host='test-host')) as remote:
        with pytest.raises(BridgeError, match='execution status unknown'):
            remote.set_cursor('10')
        assert remote._process is None
    assert counter.read_text().splitlines() == ['start']
