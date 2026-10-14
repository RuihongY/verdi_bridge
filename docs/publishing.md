# Publishing and discovery

The package is named `verdi-bridge`; the official MCP Registry name is
`io.github.RuihongY/verdi-bridge`. `server.json` describes the stdio launch command
and required session configuration. Installing the package does not install Verdi.

Version **0.3.1** is published on [PyPI](https://pypi.org/project/verdi-bridge/0.3.1/)
and registered as `io.github.RuihongY/verdi-bridge` in the official MCP Registry.
The [first publishing run](https://github.com/RuihongY/verdi_bridge/actions/runs/38503861850)
completed all build, PyPI and registry jobs successfully. A fresh PyPI installation
and a cache-free uvx invocation both verified the packaged CLI and Tcl adapter.

## Release workflow

`.github/workflows/publish.yml` builds/tests a release tag, publishes distributions
to PyPI through Trusted Publishing, then registers the same version in the MCP
Registry using GitHub OIDC. No long-lived PyPI or registry token is stored.

For first-time setup, the PyPI owner registers a pending trusted publisher:

| Field | Value |
|---|---|
| PyPI project name | `verdi-bridge` |
| GitHub owner | `RuihongY` |
| Repository | `verdi_bridge` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Bump `pyproject.toml`, `src/verdi_bridge/__init__.py`, and both versions in
`server.json` together; update the lockfile and changelog. Keep the `mcp-name`
marker in the package README: the registry uses it to verify package ownership.
Run the usual tests/build and `twine check --strict` before creating a release.

The workflow runs when a GitHub Release is published. It can also be dispatched
manually with an existing release tag. A retry skips artifacts already on PyPI;
never replace files under an existing PyPI version. Check the PyPI listing and
registry API after publishing, then verify `uvx verdi-bridge tcl-path` in a fresh
cache. The adapter and Python package must use the same version.

References: [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/),
[MCP package ownership](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx),
[MCP GitHub Actions](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/github-actions.mdx).

## Community directories

The awesome-mcp-servers entry belongs under Embedded System and links to the
repository. Its description states the live-waveform/RTL capabilities and the
licensed-Verdi requirement. [The directory submission](https://github.com/punkpeye/awesome-mcp-servers/pull/16374)
is awaiting review. A submitted pull request is not a confirmed listing;
maintainers decide whether to accept it.
