"""Jarvis-owned WhatsApp admission contracts; no live transport or model calls."""
import pytest

from gateway.config import PlatformConfig
from plugins.platforms.whatsapp.adapter import WhatsAppAdapter

GROUP = '120363000000001@g.us'
BOT = '15550000009@s.whatsapp.net'


@pytest.fixture
def adapter():
    return WhatsAppAdapter(PlatformConfig(enabled=True, extra={
        'dm_policy': 'disabled', 'group_policy': 'allowlist',
        'group_allow_from': [GROUP], 'require_mention': True,
    }))


def message(**changes):
    return dict({'isGroup': True, 'chatId': GROUP, 'body': 'Can you help?',
                 'senderId': '15550000001@s.whatsapp.net', 'senderName': 'Alice',
                 'mentionedIds': [], 'botIds': [BOT], 'quotedParticipant': ''}, **changes)


@pytest.mark.parametrize('trigger', [{'mentionedIds': [BOT]}, {'quotedParticipant': BOT}])
def test_allowed_group_can_address_jarvis(adapter, trigger):
    assert adapter._should_process_message(message(**trigger))


@pytest.mark.parametrize('trigger', [{'mentionedIds': [BOT]}, {'quotedParticipant': BOT}])
def test_addressing_jarvis_does_not_bypass_group_allowlist(adapter, trigger):
    assert not adapter._should_process_message(message(chatId='120363000000002@g.us', **trigger))


def test_ordinary_group_chat_does_not_trigger_a_reply(adapter):
    assert not adapter._should_process_message(message())


def test_disabled_dm_policy_cannot_be_bypassed_by_mention(adapter):
    assert not adapter._should_process_message(message(
        isGroup=False, chatId='15550000001@s.whatsapp.net', mentionedIds=[BOT]))


def test_display_name_does_not_grant_group_access(adapter):
    assert not adapter._should_process_message(message(
        chatId='120363000000002@g.us', senderName='Owner / Administrator', mentionedIds=[BOT]))
