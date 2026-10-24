# Jarvis's test contracts

These are tests we maintain for our fork. Their purpose is to preserve the behavior Jarvis
needs while we design its architecture and integrate future Hermes updates. They exercise
upstream code directly; no earlier Jarvis harness implementation has been imported.

## Run our suite

Use the test-environment preparation in `tests/AGENTS.md`, then run from the repository root:

```sh
scripts/run_tests.sh tests/gateway/test_jarvis_session_contracts.py tests/gateway/test_jarvis_whatsapp_contracts.py -q
python scripts/check
```

The runner also supports an explicitly supplied `HERMES_PYTHON` interpreter with pytest for
minimal validation. That is useful for these narrow contracts but does not establish full
lockfile/environment parity. Prefer the checkout's managed test environment for broader CI.

## What the first suite verifies

| Contract file | Behavior protected |
|---|---|
| `tests/gateway/test_jarvis_session_contracts.py` | Members share a group session when configured; groups, DMs, and profile namespaces have distinct keys; display names do not change routing; sender identity survives serialization; serialized input cannot claim trusted relay provenance. |
| `tests/gateway/test_jarvis_whatsapp_contracts.py` | The real WhatsApp adapter accepts mentions/replies in allowed groups, rejects other groups, ignores ordinary unaddressed chat, and enforces an explicitly disabled DM policy. |

All IDs and names are synthetic fixtures. Tests do not connect to WhatsApp, call a model,
read production memory, or send messages. The upstream fixture system supplies temporary
Hermes state and removes credential environment variables.

The WhatsApp policy values are explicit test configurations, not new product defaults.
In particular, the disabled-DM test verifies that disabling DMs works; it does not settle
whether the final Jarvis product should offer private DMs.

## What passing does not prove

Distinct session keys do not prove private memory, files, credentials, tools, or jobs are
isolated. These tests do not establish end-to-end WhatsApp delivery, voice behavior, group
membership synchronization, account-owner approvals, prompt-injection resistance, billing,
or readiness to host multiple customers.

Add those contracts alongside their real implementation after the architecture decision.
Do not add passing placeholders or skipped future tests that make unfinished work look done.
For an actual bug fix, first reproduce failure on the base revision; these initial tests are
baseline compatibility contracts and are expected to pass on unmodified upstream behavior.

## Ownership and review

Use the `test_jarvis_*` prefix in the corresponding source area's test directory. Describe
an observable guarantee in each test name. Test the real boundary, not a copy of its logic.
When upstream changes an interface, determine whether the contract or the implementation
needs to change; do not simply weaken an assertion to restore green results.

Keep the inherited tests too. Our focused suite complements them and is not a replacement.
