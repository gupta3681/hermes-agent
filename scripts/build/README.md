# Shared headless build layer

Jarvis retains Hermes's package manager and runnable Python payload format. Desktop
packaging, signing, Store publication, channel publication, and desktop build entrypoints
are removed. These modules do not depend on `scripts/bundles` or a desktop checkout.

| Module | Responsibility |
|---|---|
| `source.py` | Stdlib-only Git revision admission and commit/version checks |
| `payload.py` | Source snapshots, PM tool facts, sealed PM runtime metadata, portable links |
| `native.py` | Isolated preparation of pinned tools, dependencies and offline cache |
| `native_prepared.py` | Verify prepared paths, digests, ownership and selected revision |
| `native_build.py` | Prepare or consume a standalone native payload |
| `toolchain.py` | Child-scoped build environment and compiler-sensitive cache identity |
| `bytecode.py` | Bake bytecode using the staged interpreter |
| `inputs.py`, `agent.py` | Validate prepared inputs and assemble a runnable agent |
| `launchers.py`, `launcher_wrapper.py`, `mint_launchers.py` | Generate runtime entrypoints |

Build dependencies through PM:

```sh
python -m pm.build_env --source /work/source --out /work/venv --sealed
```

Stage a headless payload through PM's existing command:

```sh
hermes pm bundle --out /work/payload --ref HEAD --cache /work/cache
```

For separated preparation and consumption:

```sh
python -m scripts.build.native_build --source /work/source --work /work/build \
  --cache /work/cache --out /work/payload --ref HEAD --prepare-only
python -m scripts.build.native_build --prepared /work/payload.prepared.json
```

The source must be clean at the selected revision. Preparation owns its temporary state,
never the user's live installation. Finishing verifies the prepared bytes before writing
`manifest.json`; a failure must not leave a success manifest. Native payloads preserve the
pinned tool inventory, independent PM runtime, relocatable dependency links and offline
wheel cache. Compiler prerequisites remain PM's responsibility.

Container assembly continues through `docker/build_agent.py` and `scripts.build.agent`.
Shared CI object storage, attribution, container publication and source-version utilities
remain under `scripts/releases`; they do not contain desktop signing or package publication.
Runtime channel readers parse refs through `hermes_cli.release_refs` and retain their wire
validation. Reader tests use synthetic records served over loopback HTTP.

Helper tests do not establish a complete production image, native cross-platform build,
or device-installation result. Check the task's validation report before deployment.
