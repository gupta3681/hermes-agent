"""Runtime final/attempt refs are parsed independently of the removed publisher."""

import pytest

from hermes_cli.release_refs import version_from_tag



def test_final_tag_is_its_version():
    assert version_from_tag("v0.21.5") == "0.21.5"


@pytest.mark.parametrize("ref", [
    "v0.21.5-rc",
    "v0.21.4+canary.20260922T001400Z",
    "v2026.9.21",
    "canary-0.21.4+canary.20260922T001400Z",
    "v0.0.7+channel.20260922T001400Z.98765",
    "v0.0.0+commit.20260922T001400Z.98766",
])
def test_non_final_refs_are_not_versions(ref):
    assert version_from_tag(ref) is None


def test_attempt_ref_carries_version_and_attempt():
    from hermes_cli.release_refs import parse_attempt_ref

    assert parse_attempt_ref("rc.1-v0.21.5") == ("0.21.5", 1)
    assert parse_attempt_ref("rc.12-v1.0.0") == ("1.0.0", 12)




@pytest.mark.parametrize("ref", [
    "v0.21.5-rc", "v0.21.5-rc.1", "rc.01-v0.21.5", "rc.0-v0.21.5",
    "rc.1-v2026.9.21", "v0.21.5", "abandoned-rc.1-v0.21.5",
    "rc.1-v0.21.5+canary.20260922T001400Z", "rc.1-v0.21", "rc.-v0.21.5",
])
def test_attempt_ref_rejects_other_shapes(ref):
    from hermes_cli.release_refs import parse_attempt_ref

    assert parse_attempt_ref(ref) is None








def test_canary_compares_equal_to_its_stable():
    from scripts.releases.semver import compare, is_canary_version
    assert is_canary_version("0.21.4+canary.20260922T001400Z")
    assert compare("0.21.4+canary.20260922T001400Z", "0.21.4") == 0
