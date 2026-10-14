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
from verdi_bridge.client import BridgeError, Client, Config, EngineUnavailable
from verdi_bridge.remote_io import exchange

ADAPTER = Path(client_module.__file__).with_name("bridge.tcl")
FAKE_VERDI = Path(__file__).with_name("fake_verdi.tcl")


def launch_adapter(env, session):
    """Start the fake GUI; return once `session` exists or the adapter exited."""
    proc = subprocess.Popen(["tclsh", str(FAKE_VERDI), str(ADAPTER)],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for _ in range(150):
        if session.exists() or proc.poll() is not None:
            break
        time.sleep(0.02)
    return proc


def stop_adapter(proc):
    proc.terminate()
    return proc.communicate(timeout=3)


@pytest.fixture
def running(tmp_path):
    if not shutil.which("tclsh"):
        pytest.fail("Tcl 8.6+ is required for transport tests")
    root = tmp_path / "bridge"
    root.mkdir(mode=0o700)
    (tmp_path / "logs").mkdir()
    source = tmp_path / "source.sv"
    source.write_text('module fifo;\n// quote " slash \\ unicode 中文\nendmodule\n')
    env = {**os.environ, "VERDI_BRIDGE_DIR": str(root),
           "VERDI_BRIDGE_SOURCE_ROOTS": str(tmp_path),
           "VERDI_BRIDGE_LOG_ROOTS": str(tmp_path / "logs"), "TEST_SOURCE": str(source),
           "TEST_LITERAL_SIGNAL": '/tb/a[3:0]; [exec touch INJECTED] $env(HOME) {} "'}
    proc = launch_adapter(env, root / "session")
    if proc.poll() is not None:
        pytest.fail(proc.stderr.read().decode())
    if not (root / "session").exists():
        proc.kill()
        pytest.fail("Tcl fixture did not start")
    yield Client(Config(str(root), timeout=2)), env
    stop_adapter(proc)


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
                assert len(names) == 18
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
    assert client.sample(["/tb/signed"], ["0"], radix="SDec")["samples"][0]["value"] == "-1"


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
    assert client.find_signals("*/pulse", scope="/tb/dut", depth=1, glob=True)["signals"] == [
        "/tb/dut/pulse", "/tb/dut/nested/pulse"]


def test_file_reads_log_limits_and_symlinks(running, tmp_path):
    client, env = running
    assert client.source_file(env["TEST_SOURCE"], 2, 1)["lines"][0]["line"] == 2
    log = tmp_path / "logs/sim.log"
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


# How sshd hands the remote command to the user's login shell.
LOGIN_SHELLS = {"sh-exec": ("/bin/sh", "'exec ' + sys.argv[-1]"),
                "sh-wrapper": ("/bin/sh", "sys.argv[-1] + '; :'"),
                "tcsh": (shutil.which("tcsh"), "sys.argv[-1]")}


@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("login_shell", list(LOGIN_SHELLS))
def test_ssh_shell_quoting_and_helper_reuse(running, tmp_path, monkeypatch, persistent, login_shell):
    shell, shell_command = LOGIN_SHELLS[login_shell]
    if not shell:
        pytest.skip("tcsh is not installed")
    local, _ = running
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = tmp_path / "ssh-calls"
    shim = bindir / "ssh"
    shim.write_text("#!/usr/bin/env python3\nimport os,sys\n"
                    "with open(os.environ['SSH_CALLS'], 'a') as f: f.write('start\\n')\n"
                    f"os.execl({shell!r}, {shell!r}, '-c', {shell_command})\n")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("SSH_CALLS", str(calls))
    # Exercise shlex.quote on the *whole helper*, including executable shell-looking text.
    helper = tmp_path / "helper.py"
    helper.write_text(Path(client_module.remote_io.__file__).read_text() +
                      "\n# quotes ' \" `touch INJECTED` $(touch INJECTED) \\ \n")
    monkeypatch.setattr(client_module.remote_io, "__file__", str(helper))
    # Transport only: the GUI engine keeps the helper launch count deterministic.
    with Client(Config(local.config.directory, host="test-host", timeout=2,
                       persistent=persistent, engine="gui")) as remote:
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
            # Start the response deadline only once the shim is running. Avoid
            # turning interpreter startup under CI load into a flaky assertion.
            deadline = time.monotonic() + 10
            while not counter.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            assert counter.exists(), "SSH shim failed to start"
            return super().get(block=block, timeout=.1)

    monkeypatch.setattr(client_module.queue, 'Queue', ShortDeadlineQueue)
    with Client(Config(str(tmp_path), host='test-host')) as remote:
        with pytest.raises(BridgeError, match='execution status unknown'):
            remote.set_cursor('10')
        assert remote._process is None
    assert counter.read_text().splitlines() == ['start']


@pytest.mark.parametrize("unit,end", [("fs","5001000"),("ps","5001"),("ns","5.001"),
                                      ("us","0.005001"),("ms","0.000005001"),("s","5.001e-9")])
def test_exact_tick_boundaries_all_units(running, unit, end):
    c,_ = running
    r = c.find_transitions("/tb/pulse", "0", end, unit=unit)
    assert len(r["signals"][0]["changes"]) == 2
    assert Decimal(r["signals"][0]["changes"][-1]["time"]) == Decimal(end)
    assert c.find_transitions("/tb/pulse", end, str(Decimal(end)*2), unit=unit)["signals"][0]["changes"] == []
    with pytest.raises(BridgeError, match="not aligned"):
        c.set_cursor("1.1", unit="ps")
    with pytest.raises(BridgeError, match="exact vendor tick range"):
        c.set_cursor("9007199254740992", unit="ps")


def test_radix_and_glob_are_explicit(running):
    c,_ = running
    assert c.sample(["/tb/clk"],["5"],radix="Dec")["samples"][0]["value"] == "1"
    assert c.sample(["/tb/signed"],["0"],radix="Dec")["samples"][0]["value"] == "255"
    r = c.find_signals("*/ptr[3:0]",glob=True)
    assert r["signals"] and all(p.endswith("ptr[3:0]") for p in r["signals"])
    assert c.find_signals("*/ptr[3:0]")["signals"] == []


def test_independent_log_roots(running):
    c,env = running
    with pytest.raises(BridgeError, match="LOG_ROOTS"):
        c.read_log(env["TEST_SOURCE"],pattern="")


def test_clock_default_is_physical_100ns(running):
    c,_ = running
    assert Decimal(c.measure_clock("/tb/clk","50000",unit="ps")["period"]) == 10000


def test_time_budget_partial_and_resume(running):
    c,_ = running
    before = c.status()
    r = c.get_value_changes(["/tb/slow_clk","/tb/pulse"],"0","100",budget_ms=10)
    assert r["truncated"] and "time budget" in r["reasons"]
    assert r["signals"][0]["resume_from"] == "5"
    assert r["signals"][1]["initial"] is None
    assert c.status() == before
    assert c.find_transitions("/tb/pulse",r["signals"][1]["resume_from"],"100")["signals"][0]["changes"]


def test_scope_cache_is_request_local(running):
    c,_ = running
    # Fixture deliberately fails a second scope lookup in one event-loop callback.
    assert len(c.sample(["/cache/s0","/cache/s1"],["0"])["samples"]) == 2
    assert len(c.sample(["/cache/s0","/cache/s1"],["1"])["samples"]) == 2


@pytest.mark.parametrize("native,unit,value,tick", [
    ("1fs", "ns", "0.000001", "1"),
    ("10ps", "ns", "156", "15600"),
    ("2ps", "ms", "0.000156", "78000"),
    ("0.1ns", "us", "0.001", "10"),
    ("1ps", "ps", "9007199254740991", "9007199254740991"),
])
def test_exact_conversion_native_factors(native, unit, value, tick):
    # Varied vendor resolutions, including the largest accepted integer tick.
    adapter = Path(client_module.__file__).with_name("bridge.tcl").read_text()
    adapter = adapter.rsplit("::vb::start", 1)[0]
    script = adapter + f"\nproc wvGetWindowTimeUnit {{args}} {{return {{{native}}}}}\n"
    script += f"puts [::vb::timevalue w {value} {unit}]\n"
    script += f"puts [::vb::physical_time w {tick} {unit}]\n"
    result = subprocess.run(["tclsh"], input=script, text=True, capture_output=True, check=True)
    assert not result.stderr
    ticks, physical = result.stdout.splitlines()
    assert ticks == tick
    assert Decimal(physical) == Decimal(value)


def test_response_decoding_ignores_helper_locale(running, monkeypatch):
    # An SSH session often runs the helper under LANG=C; Python 3.6 then has an
    # ASCII default encoding. Responses must still decode as UTF-8.
    client, _ = running
    for name, value in {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0",
                        "PYTHONCOERCECLOCALE": "0"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    assert "中文" in client.source("tb.dut", 2, 1)["lines"][0]["text"]


def test_non_utf8_source_lines_are_readable(running):
    client, env = running
    Path(env["TEST_SOURCE"]).write_bytes(b"module fifo;\n// latin-1 \xe9\xff\nendmodule\n")
    assert client.source("tb.dut", 2, 1)["lines"][0]["text"].startswith("// latin-1 ")


def test_file_roots_never_cover_home(tmp_path):
    home = (tmp_path / "home").resolve()
    (home / "proj").mkdir(parents=True)
    adapter = ADAPTER.read_text().rsplit("::vb::start", 1)[0]
    script = adapter + f"""
set ::env(HOME) {{{home}}}
foreach dir [list {{{tmp_path.resolve()}}} {{{home}}} {{{home / 'proj'}}}] {{
    cd $dir
    puts [llength [::vb::file_roots VERDI_BRIDGE_SOURCE_ROOTS]]
}}
foreach bad [list / {{{home}}} {{{tmp_path.resolve()}}} "{home / 'proj'}:{home}"] {{
    set ::env(VERDI_BRIDGE_SOURCE_ROOTS) $bad
    puts [catch {{::vb::file_roots VERDI_BRIDGE_SOURCE_ROOTS}}]
}}
set ::env(VERDI_BRIDGE_SOURCE_ROOTS) {{{home / 'proj'}}}
puts [::vb::file_roots VERDI_BRIDGE_SOURCE_ROOTS]
set ::vb::source_roots {{}}
puts [catch {{::vb::allowed_file {{{home / 'proj'}}}}} message]
puts $message
"""
    result = subprocess.run(["tclsh"], input=script, text=True, capture_output=True, check=True)
    lines = result.stdout.splitlines()
    # Default cwd roots: an ancestor of HOME and HOME itself are dropped.
    assert lines[:3] == ["0", "0", "1"]
    assert lines[3:7] == ["1", "1", "1", "1"]
    assert lines[7] == str(home / "proj")
    assert lines[8] == "1" and "VERDI_BRIDGE_SOURCE_ROOTS" in lines[9]


def test_find_signals_time_budget(running):
    c, _ = running
    start = time.monotonic()
    r = c.find_signals("nomatch", scope="/slow", budget_ms=100)
    assert r["truncated"] and r["reasons"] == ["time budget"]
    assert 1 <= r["visited_scopes"] < 65
    assert time.monotonic() - start < 1.5
    assert c.find_signals("ptr", depth=0)["reasons"] == ["depth"]
    assert c.find_signals("ptr", max=1)["reasons"] == ["max results"]
    with pytest.raises(ValueError, match="budget_ms"):
        c.find_signals("ptr", budget_ms=0)


def test_foreign_request_file_does_not_stall(running):
    client, env = running
    # Sorts before every request ID; it previously blocked all later requests.
    (Path(env["VERDI_BRIDGE_DIR"]) / "0.req").write_text("not a request")
    assert client.status()["time_unit"] == "1ps"


def test_mcp_tools_do_not_block_the_event_loop(running):
    _, env = running

    async def run():
        params = StdioServerParameters(command=sys.executable,
                                      args=["-c", "from verdi_bridge.cli import main; main()", "serve"],
                                      env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                slow = asyncio.create_task(session.call_tool(
                    "sample_signals", {"signals": ["/tb/sleepy"], "times": ["0"]}))
                await asyncio.sleep(0.3)
                start = time.monotonic()
                await session.send_ping()
                assert time.monotonic() - start < 0.5
                assert not slow.done()
                assert not (await slow).isError
    asyncio.run(run())


def test_default_directory_survives_restart(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    root = home / ".verdi-bridge" / "session"
    env = {k: v for k, v in os.environ.items() if not k.startswith("VERDI_BRIDGE_")}
    env.update(HOME=str(home), VERDI_BRIDGE_SOURCE_ROOTS=str(tmp_path / "src"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("VERDI_BRIDGE_DIR", raising=False)

    first = launch_adapter(env, root / "session")
    assert first.poll() is None, first.stderr.read().decode()
    assert (root.stat().st_mode & 0o777) == 0o700
    assert (root.parent.stat().st_mode & 0o777) == 0o700
    with Client(Config.from_env()) as client:
        assert client.config.directory == "~/.verdi-bridge/session"
        assert client.status()["time_unit"] == "1ps"

    # A second GUI must not share the directory while the first is alive.
    second = launch_adapter(env, root / "never")
    second.wait(timeout=5)
    assert second.returncode != 0
    assert "another Verdi GUI" in second.stderr.read().decode()

    # A killed GUI leaves gui.lock and old files behind; a restart recovers.
    stop_adapter(first)
    old_session = (root / "session").read_text()
    leftover = root / ("ab" * 16 + ".res")
    leftover.write_text("{}")
    restarted = launch_adapter(env, root / "never")
    try:
        for _ in range(150):
            if (root / "session").read_text() != old_session or restarted.poll() is not None:
                break
            time.sleep(0.02)
        assert restarted.poll() is None, restarted.stderr.read().decode()
        assert not leftover.exists()
        with Client(Config.from_env()) as client:
            assert client.status()["time_unit"] == "1ps"
    finally:
        stop_adapter(restarted)


def test_browse_pages_scopes_then_signals(running):
    c, _ = running
    first = c.browse("/tb/dut", limit=5)
    assert first["scopes"] == ["nested"] and len(first["signals"]) == 4
    assert first["total_scopes"] == 1 and first["next_offset"] == 5
    names, offset = list(first["signals"]), first["next_offset"]
    while offset is not None:
        page = c.browse("/tb/dut", offset=offset, limit=5)
        assert page["scopes"] == []
        names += page["signals"]
        offset = page["next_offset"]
    assert len(names) == first["total_signals"] == len(set(names))
    assert c.browse("/tb/dut", offset=10**6)["signals"] == []
    with pytest.raises(ValueError):
        c.browse("/", limit=0)


def test_status_and_timeout_bounds(running, monkeypatch):
    c, _ = running
    c.add_signals([f"/tb/s{n}" for n in range(16)])
    status = c.status()
    assert status["signals_total"] == 16 and status["signals_truncated"] is False
    monkeypatch.setenv("VERDI_BRIDGE_TIMEOUT", "45")
    assert Config.from_env().timeout == 45
    with pytest.raises(ValueError, match="timeout"):
        Client(Config(timeout=0))


def test_sample_budget_returns_pending_signals(running):
    c, _ = running
    # /tb/sleepy takes 1.5 s per value, like a slow first load in a huge flat scope.
    r = c.sample(["/tb/sleepy", "/tb/clk", "/tb/pulse"], ["5"], budget_ms=100)
    assert [s["signal"] for s in r["samples"]] == ["/tb/sleepy"]
    assert r["truncated"] is True and r["pending_signals"] == ["/tb/clk", "/tb/pulse"]
    rest = c.sample(r["pending_signals"], ["5"], budget_ms=100)
    assert rest["truncated"] is False and [s["value"] for s in rest["samples"]] == ["1", "1"]


def test_count_changes_summarizes_without_values(running):
    c, _ = running
    before = c.status()
    r = c.count_changes(["/tb/clk", "/tb/pulse"], "0", "100")
    clk, pulse = r["signals"]
    assert clk["count"] == 20 and clk["first_change"] == "5" and clk["last_change"] == "100"
    assert clk["complete"] and clk["initial"] == "0" and clk["final"] == "0"
    assert pulse["count"] == 2 and pulse["last_change"] == "5.001" and pulse["final"] == "0"
    assert c.status() == before
    slow = c.count_changes(["/tb/slow_clk"], "0", "100", budget_ms=10)
    assert slow["truncated"] is True and slow["signals"][0]["complete"] is False
    assert "final" not in slow["signals"][0] and slow["signals"][0]["resume_from"]


def test_sample_on_clock_pre_and_post_edge(running):
    c, _ = running
    before = c.status()
    pre = c.sample_on_clock("/tb/clk", ["/tb/pulse", "/tb/clk"], "0", "30")
    assert [row["time"] for row in pre["cycles"]] == ["5", "15", "25"]
    assert pre["cycles"][0]["values"] == ["0", "0"] and pre["truncated"] is False
    post = c.sample_on_clock("/tb/clk", ["/tb/pulse"], "0", "30", sample="post")
    assert post["cycles"][0]["values"] == ["1"]
    both = c.sample_on_clock("/tb/clk", ["/tb/pulse"], "0", "30", edge="both")
    assert [row["edge"] for row in both["cycles"]][:2] == ["rising", "falling"]
    page = c.sample_on_clock("/tb/clk", ["/tb/pulse"], "0", "30", max_cycles=2)
    assert page["truncated"] is True and page["reason"] == "max cycles"
    rest = c.sample_on_clock("/tb/clk", ["/tb/pulse"], page["resume_from"], "30")
    assert [row["time"] for row in page["cycles"] + rest["cycles"]] == ["5", "15", "25"]
    assert c.status() == before
    with pytest.raises(ValueError, match="4096"):
        c.sample_on_clock("/tb/clk", ["/tb/pulse"] * 2, "0", "30", max_cycles=4096)


FAKE_VERDI_HOME = Path(__file__).with_name("fake_npi")


@pytest.fixture
def npi_running(tmp_path):
    root = tmp_path / "bridge"
    root.mkdir(mode=0o700)
    fsdb = tmp_path / "wave.fsdb"
    fsdb.write_text("fake")
    env = {**os.environ, "VERDI_BRIDGE_DIR": str(root), "VERDI_BRIDGE_SOURCE_ROOTS": str(tmp_path),
           "VERDI_BRIDGE_LOG_ROOTS": str(tmp_path), "TEST_FSDB": str(fsdb),
           "VERDI_HOME": str(FAKE_VERDI_HOME), "TEST_SOURCE": str(fsdb)}
    proc = launch_adapter(env, root / "session")
    assert proc.poll() is None, proc.stderr.read().decode()

    def make(engine):
        return Client(Config(str(root), timeout=5, engine=engine, npi_python=sys.executable))
    yield make, fsdb
    stop_adapter(proc)


def strip_engine(result):
    if isinstance(result, dict):
        return {k: strip_engine(v) for k, v in result.items()
                if k not in ("engine", "engine_note", "budget_ms", "npi_load", "npi_peak_mb")}
    if isinstance(result, list):
        return [strip_engine(v) for v in result]
    return result


def test_npi_engine_matches_gui_results(npi_running):
    make, _ = npi_running
    gui, npi = make("gui"), make("npi")
    queries = [
        ("get_value_changes", dict(signals=["/tb/clk", "/tb/pulse", "/tb/flat"], start="0",
                                   end="30", radix="Bin")),
        ("get_value_changes", dict(signals=["/tb/clk"], start="0", end="100", max=3)),
        ("sample", dict(signals=["/tb/clk", "/tb/pulse", "/tb/flat"],
                        times=["0", "4.999", "5", "5.001", "15"])),
        ("sample", dict(signals=["/tb/signed"], times=["0"], radix="SDec")),
        ("count_changes", dict(signals=["/tb/clk", "/tb/pulse", "/tb/flat"], start="0",
                               end="100")),
        ("sample_on_clock", dict(clock="/tb/clk", signals=["/tb/pulse", "/tb/clk"], start="0",
                                 end="30")),
        ("sample_on_clock", dict(clock="/tb/clk", signals=["/tb/pulse"], start="0", end="30",
                                 sample="post", edge="both", max_cycles=3)),
        ("measure_clock", dict(signal="/tb/clk", around_time="50", window="40")),
    ]
    for method, kwargs in queries:
        a, b = getattr(gui, method)(**kwargs), getattr(npi, method)(**kwargs)
        assert strip_engine(a) == strip_engine(b), method
    assert npi.count_changes(["/tb/clk"], "0", "100")["engine"] == "npi"


def test_auto_engine_routing_and_escalation(npi_running):
    make, _ = npi_running
    auto = make("auto")
    # Whole-window summaries go straight to NPI; small queries stay in the GUI.
    assert auto.count_changes(["/tb/clk"], "0", "100")["engine"] == "npi"
    assert auto.sample(["/tb/clk"], ["5"])["engine"] == "gui"
    # A GUI time-budget miss is redone in full through NPI.
    r = auto.sample(["/tb/sleepy", "/tb/clk"], ["5"], budget_ms=100)
    assert r["engine"] == "npi" and "redone with NPI" in r["engine_note"]
    assert r["truncated"] is False and len(r["samples"]) == 2
    # A signal NPI cannot resolve keeps the GUI result and does not disable NPI.
    r = auto.count_changes(["/tb/s3"], "0", "100")
    assert r["engine"] == "gui" and "signal not found" in r["engine_note"]
    assert auto.count_changes(["/tb/clk"], "0", "100")["engine"] == "npi"


def test_npi_unavailable_falls_back_or_raises(npi_running, monkeypatch):
    make, fsdb = npi_running
    monkeypatch.setenv("FAKE_NPI_NO_LICENSE", "1")
    auto = make("auto")
    r = auto.count_changes(["/tb/clk"], "0", "100")
    assert r["engine"] == "gui" and "could not open" in r["engine_note"]
    assert r["signals"][0]["count"] == 20
    with pytest.raises(EngineUnavailable, match="could not open"):
        make("npi").count_changes(["/tb/clk"], "0", "100")
    monkeypatch.delenv("FAKE_NPI_NO_LICENSE")
    fsdb.unlink()
    with pytest.raises(EngineUnavailable, match="not a readable file"):
        make("npi").sample(["/tb/clk"], ["5"])
    with pytest.raises(ValueError, match="npi_python"):
        Client(Config(engine="auto", npi_python="python3; rm -rf /"))


def test_npi_budget_starts_after_load_and_makes_progress(npi_running, monkeypatch):
    make, _ = npi_running
    monkeypatch.setenv("FAKE_NPI_LOAD_SECONDS", "0.3")
    npi = make("npi")
    r = npi.get_value_changes(["/tb/clk", "/tb/pulse"], "0", "1000", max=512, budget_ms=1)
    assert r["signals"][0]["changes"], "a slow load must not consume the whole budget"
    r = npi.count_changes(["/tb/clk"], "0", "1000", budget_ms=1)
    assert r["signals"][0]["count"] >= 1
    r = npi.sample_on_clock("/tb/clk", ["/tb/pulse"], "0", "1000", budget_ms=1)
    assert r["cycles"]


def test_npi_loads_window_then_switches_slow_signals_to_full_load(npi_running, monkeypatch,
                                                                  tmp_path):
    make, _ = npi_running
    log = tmp_path / "loads"
    monkeypatch.setenv("FAKE_NPI_LOG", str(log))
    npi = make("npi")
    # Dense signals: only the requested window is loaded.
    npi.sample(["/tb/clk", "/tb/pulse"], ["500", "600"])
    assert log.read_text().split("\n")[:1] == ["load 500000 600000"]
    log.unlink()
    # Aliased signals: after two slow first reads, everything not known to be fast is
    # reloaded from time 0 (after unloading), and no further read is slow.
    signals = ["/tb/clk", "/tb/alias0", "/tb/alias1", "/tb/alias2", "/tb/alias3"]
    r = npi.sample(signals, ["6", "8"])
    assert log.read_text().splitlines() == [
        "load 6000 8000", "slow tb.alias0", "slow tb.alias1", "load 0 8000", "load 6000 8000"]
    assert [s["value"] for s in r["samples"] if s["signal"] == "/tb/alias3"] == ["0", "1"]
    assert r["npi_load"] == {"window_loaded": 1, "loaded_from_zero": 4}


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="RLIMIT_AS is not enforced on this platform")
def test_npi_memory_limit_failure_falls_back(npi_running):
    make, _ = npi_running
    # A tiny address-space limit makes the engine fail; "auto" must use the GUI instead.
    cfg = make("auto").config
    cfg.npi_max_mb = 1
    auto = Client(cfg)
    r = auto.count_changes(["/tb/clk"], "0", "100")
    assert r["engine"] == "gui" and r["signals"][0]["count"] == 20


def test_npi_removes_work_dirs_of_dead_engines(npi_running, monkeypatch, tmp_path):
    make, _ = npi_running
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    parent = tmp_path / f"verdi-bridge-npi-{os.getuid()}"
    parent.mkdir(mode=0o700)
    dead = subprocess.Popen(["true"])
    dead.wait()
    stale = parent / str(dead.pid)
    (stale / "npiLog").mkdir(parents=True)
    make("npi").count_changes(["/tb/clk"], "0", "100")
    assert not stale.exists()
    assert list(parent.iterdir()) == []
