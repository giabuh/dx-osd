"""Every side effect of a bot turn goes through an Effects object (D-060): real Chatwoot/CRM calls
in production (`ChatwootEffects`), a recorder in the Playground and in tests (`RecordingEffects`)."""

import logging

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.data_quality import compute_data_quality
from mmm_custom.engine import events

logger = logging.getLogger(__name__)


class RecordingEffects:
    """Dry run: remembers what would have happened, touches nothing."""

    def __init__(self):
        self.calls = []

    def of(self, kind):
        return [payload for name, payload in self.calls if name == kind]

    def send(self, conversation_id, reply):
        self.calls.append(("send", {"messages": list(reply.messages), "buttons": [b["title"] for b in reply.buttons]}))

    def emit(self, event, payload):
        self.calls.append(("emit", {"event": event, **payload}))

    def save_lead(self, state, fields, courses, contact):
        self.calls.append(("save_lead", {"fields": dict(fields), "courses": [c.code for c in courses]}))
        return state.lead


class ChatwootEffects:
    """Customer-facing calls use the Agent Bot token so Chatwoot marks them as the bot's own messages
    (which the webhook then ignores); contact updates need the admin user token."""

    def __init__(self, bot_client, user_client):
        self.bot, self.user = bot_client, user_client

    def send(self, conversation_id, reply):
        last = len(reply.messages) - 1
        for i, text in enumerate(reply.messages):
            if i == last and reply.buttons:
                items = [{"title": b["title"], "value": b["title"]} for b in reply.buttons]
                self.bot.send_quick_replies(conversation_id, text, items)
            else:
                self.bot.send_message(conversation_id, text)

    def emit(self, event, payload):
        events.emit(event, payload)

    def save_lead(self, state, fields, courses, contact):
        from mmm_custom.engine import repo

        name = repo.save_lead(state, fields, courses, contact)
        if state.contact_id and (contact.get("custom_attributes") or {}).get("crm_lead_id") != name:
            try:
                self.user.update_contact(state.contact_id, {"crm_lead_id": name})
            except Exception:
                logger.exception("crm_lead_id write-back to Chatwoot failed")
        try:
            compute_data_quality(name)
        except Exception:
            logger.exception("data quality update failed")
        return name


def chatwoot_effects(conf):
    base = conf.get("chatwoot_base_url") or conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000"
    account = int(conf.get("chatwoot_bot_account_id") or conf.get("chatwoot_account_id") or 1)
    bot_token = conf.get("chatwoot_bot_api_token") or ""
    return ChatwootEffects(ChatwootClient(base, bot_token, account),
                           ChatwootClient(base, conf.get("chatwoot_api_token") or bot_token, account))
