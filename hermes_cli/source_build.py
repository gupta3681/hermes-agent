"""Source launch/update composition over the shared JavaScript builders."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def source_product_current(project_root: Path, product: str, out: Path) -> bool:
    """Read the compiler's receipt without acquiring tools or dependencies."""
    from pm import env_for, installed_package

    installed = installed_package("node")
    if installed is None or installed.binary is None:
        return False  # Only PM's Node may run the receipt reader; never the user's PATH copy.
    node, env = str(installed.binary), env_for("node")
    try:
        result = subprocess.run(
            [node, str(project_root / "scripts/build/freshness.mjs"),
             "--source", str(project_root), "--product", product, "--out", str(out)],
            cwd=project_root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
        )
        return result.stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def source_build_env(base_env: dict | None = None, *, explicit: bool = False, verify: bool = True) -> dict[str, str]:
    from pm import ensure
    from pm.environments import project_python, running_from_selected_environment
    from pm.paths import repo_root
    from hermes_constants import get_hermes_home

    # The historical update runs on store Python with the selected environment
    # activated in-process. Icon generation starts an isolated child, which needs
    # the selected venv executable rather than the store interpreter.
    root = repo_root()
    python = str(project_python(root)) if running_from_selected_environment(root) else sys.executable
    env = {**os.environ, **(base_env or {}), "CI": "1", "HERMES_PYTHON": python,
           "PYTHON": python}
    # Electron's installer unpacks its binary with a native module that imports
    # VCRUNTIME140.dll, which a fresh Windows lacks. Our Python ships one, and
    # scripts/build/electron-runtime.mjs copies it beside that module.
    vc_runtime = Path(sys.base_prefix) / "vcruntime140.dll"
    if vc_runtime.is_file():
        env["HERMES_VC_RUNTIME"] = str(vc_runtime)
    env.pop("ESBUILD_BINARY_PATH", None)
    npmrc = get_hermes_home() / "npmrc"
    if npmrc.is_file():
        env.setdefault("NPM_CONFIG_USERCONFIG", str(npmrc))
    return ensure("npm", base_env=env, explicit=explicit, verify=verify).env


def run_in_custody(project_root: Path, command: list, label: str, **kwargs):
    """``pm.progress.run_contained`` for a build command that writes the checkout (node, npm):
    it and everything it starts stay in the update's custody (POSIX: the checkout lock fd, the
    caller's process group, and every descendant killed when it exits; Windows: the owner's
    kill-on-close job), so the checkout is never handed to a contender while one of them still
    writes. Outside an update it is ``run_contained`` as is."""
    from pm.progress import run_contained
    from hermes_cli.update_custody import contained_command

    with contained_command(command, root=project_root) as (argv, custody):
        return run_contained(argv, label, **kwargs, **custody)


def run_source_script(project_root: Path, script: str, *args: str, env: dict, label: str) -> None:
    command = [shutil.which("node", path=env["PATH"]), str(project_root / script), *args]
    # npm's deprecation warnings are the loudest lines and never actionable
    # here; they still land in the failure tail.
    run_in_custody(project_root, command, label, hide=lambda line: line.lower().startswith("npm warn"),
                   indent="  ", cwd=project_root, env=env)


def prepare_source_dependencies(project_root: Path, workspaces: tuple[str, ...], *, env: dict,
                                explicit: bool = False) -> None:
    from pm import lazy_installs_allowed

    run_source_script(
        project_root, "scripts/build/node-deps.mjs", "--source", str(project_root), "--reuse",
        *(() if explicit or lazy_installs_allowed() else ("--no-install",)),
        *(arg for workspace in workspaces for arg in ("--workspace", workspace)), env=env,
        label="Preparing Node dependencies",
    )


def prepare_launch_dependencies(project_root: Path, *, env: dict) -> None:
    """A launch rebuild must not prune another installed source frontend."""
    prepare_source_dependencies(project_root, source_frontends(project_root), env=env)


def build_source_tui(project_root: Path, *, env: dict) -> None:
    run_source_script(project_root, "scripts/build/tui.mjs", env=env, label="Building the TUI")


def build_source_web(project_root: Path, *, env: dict, icons: Path | None = None) -> None:
    # Bounded build (#63338): the Vite/Rolldown dashboard build saturates small
    # hosts; cap the V8 heap and the native bundler's rayon thread pool.
    from hermes_cli.web_build_limits import apply_web_build_limits

    apply_web_build_limits(env)
    # Default-brand icons are committed; installs never render them.
    icons = icons or project_root
    run_source_script(project_root, "scripts/build/web.mjs", "--source", str(project_root),
                      "--icons", str(icons), "--out", str(project_root / "hermes_cli/web_dist"), env=env,
                      label="Building the web UI")


def source_frontends(project_root: Path) -> tuple[str, ...]:
    """The frontend workspaces this checkout carries. A source slice without them
    (python-only installs, the installer's acceptance fixture) has no products
    to build; it still publishes commands and runs the maintenance tail."""
    return tuple(name for name in ("ui-tui", "web") if (project_root / name / "package.json").is_file())


class ProductBuildError(RuntimeError):
    """One or more products failed; every independent product was still attempted."""

    def __init__(self, failures: list[tuple[str, BaseException]]):
        self.failures = failures
        super().__init__("; ".join(f"{name}: {_failure_text(exc)}" for name, exc in failures))


def _failure_text(exc: BaseException) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        return f"{' '.join(map(str, exc.cmd)) if isinstance(exc.cmd, (list, tuple)) else exc.cmd} exited {exc.returncode}"
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


def _headless_linux() -> bool:
    return sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def build_update_products(project_root: Path, *, desktop: bool) -> None:
    """Refresh source dependencies and migrations; accept old desktop markers without building it."""
    # Both current updates and historical takeover reach this in a fresh target
    # interpreter, never in the updater's pre-sync import graph.
    from hermes_cli.main_install_repair import _install_configured_features_missing_deps
    from hermes_cli.update_stage import publish_stage

    failures: list[tuple[str, BaseException]] = []

    def attempt(name: str, step) -> bool:
        try:
            step()
            return True
        except Exception as exc:  # health: allow BLE001 -- collected and raised after the independent steps
            print(f"  ⚠ {name} failed: {_failure_text(exc)}")
            failures.append((name, exc))
            return False

    attempt("feature dependencies", lambda: _install_configured_features_missing_deps(project_root))
    frontends = source_frontends(project_root)
    if frontends:
        env = source_build_env(explicit=True, verify=False)
        publish_stage("Updating Node dependencies")
        prepared = attempt("Node dependencies", lambda: prepare_source_dependencies(
            project_root, frontends, env=env, explicit=True))
        if prepared:
            for workspace, product, output, builder in (
                ("ui-tui", "tui", project_root / "ui-tui/dist", build_source_tui),
                ("web", "web", project_root / "hermes_cli/web_dist", build_source_web),
            ):
                if workspace not in frontends or source_product_current(project_root, product, output):
                    continue
                publish_stage(f"Building {product}")
                attempt(f"{product} build", lambda builder=builder: builder(project_root, env=env))
    # A configured memory provider that no longer ships in core is installed from the
    # catalog for every profile home sharing this venv (config, data and tool names
    # unchanged). The update must finish even if the migration blows up.
    try:
        from hermes_cli.memory_provider_migration import migrate_all_homes

        migrate_all_homes()
    except Exception as exc:  # health: allow BLE001 -- post-commit boundary: printed as ⚠, never fails the committed update; every later update/tail re-runs it
        print(f"  ⚠ Memory provider migration skipped: {exc}")
    # Same for a gateway platform / toolset that left core (Home Assistant): every home that used
    # it gets its catalog plugin (hermes_cli/left_core_migration.py).
    try:
        from hermes_cli.left_core_migration import migrate_all_homes as migrate_left_core

        migrate_left_core()
    except Exception as exc:  # health: allow BLE001 -- post-commit boundary: printed as ⚠, never fails the committed update; every later update/tail re-runs it
        print(f"  ⚠ Plugin migration skipped: {exc}")
    if failures:
        raise ProductBuildError(failures)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build source-install frontends")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--desktop", action="store_true")
    args = parser.parse_args()
    build_update_products(args.source.resolve(), desktop=args.desktop)
