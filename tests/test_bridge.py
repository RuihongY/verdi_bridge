import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
                assert len(names) == 10
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
