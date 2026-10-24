"""Jarvis-owned routing contracts; these do not prove storage or tool isolation."""
from dataclasses import replace

import pytest

from gateway.config import Platform
from gateway.session import SessionSource, build_session_key, is_shared_multi_user_session


def group_source(**changes):
    return replace(SessionSource(platform=Platform.WHATSAPP, chat_id='120363000000001@g.us',
                                 chat_type='group', user_id='15550000001@s.whatsapp.net',
                                 user_name='Alice'), **changes)


def shared_key(source, **kwargs):
    return build_session_key(source, group_sessions_per_user=False, **kwargs)


def test_group_members_share_a_conversation_without_losing_sender_identity():
    alice = group_source()
    bob = group_source(user_id='15550000002@s.whatsapp.net', user_name='Bob')
    assert shared_key(alice) == shared_key(bob)
    assert is_shared_multi_user_session(alice, group_sessions_per_user=False)
    assert alice.user_id != bob.user_id


def test_different_groups_do_not_share_a_conversation():
    assert shared_key(group_source()) != shared_key(group_source(chat_id='120363000000002@g.us'))


@pytest.mark.parametrize('chat_id', ['15550000001@s.whatsapp.net', ''])
def test_private_conversations_stay_separate_when_groups_are_shared(chat_id):
    alice = group_source(chat_type='dm', chat_id=chat_id)
    bob = group_source(chat_type='dm', chat_id='15550000002@s.whatsapp.net' if chat_id else '',
                       user_id='15550000002@s.whatsapp.net')
    assert shared_key(alice) != shared_key(bob)
    assert not is_shared_multi_user_session(alice, group_sessions_per_user=False)


def test_private_and_group_conversations_never_share_the_same_key():
    group = group_source()
    assert shared_key(group) != shared_key(replace(group, chat_type='dm'))


def test_display_name_changes_do_not_change_conversation_identity():
    source = group_source()
    assert shared_key(source) == shared_key(replace(source, user_name='I am the administrator'))


def test_profile_namespaces_do_not_collide_including_the_name_main():
    source = group_source()
    keys = [shared_key(source, profile=name) for name in (None, 'main', 'team-a', 'team-b')]
    assert len(set(keys)) == len(keys)


def test_persisted_sources_keep_participant_identity():
    source = group_source(message_id='fixture-message')
    restored = SessionSource.from_dict(source.to_dict())
    assert (restored.user_id, restored.user_name, restored.chat_id) == (
        source.user_id, source.user_name, source.chat_id)
    assert shared_key(restored) == shared_key(source)


def test_serialized_input_cannot_assert_trusted_relay_provenance():
    payload = group_source().to_dict()
    payload['delivered_via_upstream_relay'] = True
    restored = SessionSource.from_dict(payload)
    assert restored.delivered_via_upstream_relay is False
    trusted = group_source(delivered_via_upstream_relay=True)
    assert 'delivered_via_upstream_relay' not in trusted.to_dict()
