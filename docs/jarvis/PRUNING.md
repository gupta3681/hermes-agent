# Jarvis removal record

This fork keeps Hermes's agent runtime and WhatsApp integrations. This first removal
batch reduces shipped product surfaces; it does not redesign multiplayer permissions.

## Removed

- Electron desktop app and native bootstrap installer.
- Ink terminal frontend and browser dashboard frontend.
- Documentation site application/build (reference docs, catalog generators, and assets stay).
- Desktop/site release and end-to-end workflows, plus tests specific to those removed products.
- Nix distribution, whose packages and acceptance checks require the removed frontends.
- Unused frontend npm workspaces and dedicated native smoke-test dependencies.

The remaining npm workspaces are `apps/shared` and `tests-js`. The WhatsApp bridge has its
own package manifest and is preserved. Python dependency declarations are unchanged.

## Deliberately retained

- Agent loop, tools, providers, memory, skills, compaction, cron, and package management.
- Both WhatsApp transports, gateway authorization, sessions, and the classic CLI.
- `tui_gateway`: shared session contracts, credential scoping, and RPC backend code.
- `apps/shared`: generated contracts and shared client code still verified by tests.
- Backend web routers, headless serving, and shared launcher/build/update helpers. Removing
  the React dashboard does not make all these Python modules frontend-only.
- Other messaging adapters and optional integrations: shared delivery helpers still import
  some adapters. These require their own migration rather than deleting directories.
- Upstream license, attribution, history, and reference documentation.

A shared execution-event fixture formerly under the desktop app now lives under
`tests/gateway/fixtures/`; backend coverage using that fixture remains.

## Operational changes

Use `hermes --cli` or `hermes gateway run`. An absent Ink workspace now produces an
explanation rather than running `git restore`. The container no longer builds or copies
frontend bundles; its optional legacy `dashboard` service slot starts the headless `serve`
backend. It retains the existing authentication gate.

This is local source cleanup. No production instance has been changed. The container build
requires separate validation on a Docker-capable host before deployment. Existing upstream
release/install helpers may still describe desktop distributions; they are not a supported
Jarvis release pipeline.

## Verification

Run our contracts and the WhatsApp/session backend suites through `scripts/run_tests.sh`,
using a PM-built test environment with the `messaging` and `web` extras. Run the retained
JavaScript workspace checks and `python scripts/check`. See the task's final report for
actual results and any remaining limitations; this document is not a blanket green claim.

### Local verification results

- All 12 `scripts/check` guards pass, including code health and Ruff.
- 162 WhatsApp tests across 19 files pass; all 16 Jarvis session/WhatsApp contracts pass.
- Retained JS workspaces pass type checking and lint (shared code has existing warnings);
  all 88 JS tests pass. On macOS, use a canonical `TMPDIR` path to avoid `/var` versus
  `/private/var` differences in upstream npm path assertions.
- The shared artifact assembler's 17 tests pass. The relocated event fixture and new
  missing-frontend regression test pass.
- Broader tests are not uniformly green: two session client-environment assertions fail
  both here and in an untouched upstream worktree with the same managed test interpreter.
  CI workflow replay also hits macOS's old Bash (`mapfile` is unavailable); the retained
  non-replay CI checks pass. These limitations are not hidden by new skips.
- Docker daemon unavailable locally: the updated image recipe was not built or deployed.

## Second pass: unused chat transports

Removed the bundled IRC, ntfy, SimpleX, BlueBubbles, SMS/Twilio, and Photon iMessage
adapters, their dedicated tests, and Photon's Node sidecar. The container no longer
installs Spectrum/Photon dependencies. The vulnerability scanner no longer references
the deleted Photon or website lockfiles.

Mixed test suites retain their other cases: scoped credential reads, per-profile settings,
private credential file permissions, managed Node resolution, and message deduplication.
Standalone-send secret redaction now exercises the WhatsApp sender instead of the retired
IRC/ntfy senders. Shared queue behavior still has its Signal and other adapter cases.

Existing built-in platform enum identifiers and configuration metadata remain for
persisted-session compatibility; they do not provide an adapter or install one. Dynamic
platform identifiers require a bundled or independently registered adapter. The generic platform plugin
interface also remains, so an independently installed adapter can still register itself.
Tests that register a synthetic IRC entry exercise that generic interface and remain.

Further candidates need a separate migration: Telegram and Matrix are imported by shared
outbound delivery helpers. Discord and the remaining adapters participate in broader relay
and authorization tests. Browser, meeting, MCP, model-provider, sandbox, memory, and skill
integrations remain useful agent capabilities; removing them just because WhatsApp is the
chat surface would reduce what Jarvis can do.

Second-pass verification: 325 affected tests passed across 33 files after updating the
registry's dynamic-platform example from removed IRC to retained A2A; six tests are
platform-gated on this Mac. This includes the WhatsApp contracts, shared authorization
and profile tests, private credential writers, Node resolution, registry, queue, and
send-error redaction tests. All 12 repository checks passed, with Ruff rerun after the
final test edit. Container image execution remains unverified because no local Docker
daemon is available.

## Third pass: Raft and dashboard achievements

Removed the Raft channel bridge and the standalone achievements dashboard plugin,
including its compiled frontend, screenshots, and dedicated tests. Neither is used by
Jarvis's WhatsApp path. Shared child-process credential-scrubbing coverage remains for
language servers/installers and Buzz. The wake/admission test now exercises the same
shared lifecycle under WhatsApp and Telegram platform identities rather than Raft.
Plugin API authorization still verifies the retained Kanban routes and arbitrary plugin
namespaces before route discovery.

The next large candidates are the legacy desktop release/bundling helpers. They cannot
be removed as one directory: `pm.cli` imports native staging, the container's shared
assembler imports link handling from `scripts.bundles.payload`, and the source updater
imports release-version handling. Their useful primitives need to be separated from
retired distribution commands first. The updater's upstream release assumptions also
need an explicit Jarvis release policy before we change them.

Third-pass verification: all 255 affected tests passed across seven files, including the
complete backend web-server suite, shared wake/admission, child-process credential
scrubbing, plugin setup, registry, and the Jarvis contracts. All 12 repository checks
passed. No container image or production service was changed.

## Fourth pass: extract shared bundling and retire desktop release tooling

Moved snapshots, portable links, PM runtime sealing, tool facts, native preparation,
prepared-input validation, bytecode baking and child build environments to `scripts/build`.
`hermes pm bundle`, the container assembler, and Termux helpers now import that layer.
The shared source-admission helpers no longer depend on desktop preparation. Runtime
channel readers and container identity checks parse release refs through
`hermes_cli/release_refs.py`, with no publisher import.

Removed the `scripts/bundles` package, desktop signing/packaging entrypoints, MSIX/Store
composition, desktop build-cache action, desktop build recipe, release orchestrators,
channel publishers, desktop feed finalization/pruning and their dedicated tests. DMG
creation is no longer registered or pinned in PM. Ordinary install stamps continue to
work; the retired desktop `--channel-request` stamping extension is removed.

Retained general CI object storage, upload receipts, attribution, source-version validation,
container publication, and runtime update readers. Existing runtime/update compatibility
helpers are distinct from the retired release publisher; this change does not set a new
Jarvis release policy or deploy an update service. Channel-reader tests now construct
synthetic records directly instead of calling the retired publisher.

Fourth-pass verification: the 46-file regression run passed 630 tests with 12 platform
skips; a focused rerun after the final native/transport edits passed 62 tests, including
offline wheelhouse rebuilding. Nine new source-admission cases passed. Both retained JS
workspaces passed their checks (88 tests), and all 12 repository guards passed; Ruff was
rerun after the final test annotation. Shell syntax and the new native-builder CLI were
also checked. Docker image execution remains unverified because the local daemon is down.
