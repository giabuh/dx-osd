"""Every side effect of a bot turn goes through an Effects object (D-060): real Chatwoot/CRM calls
in production (`ChatwootEffects`), a recorder in the Playground and in tests (`RecordingEffects`)."""

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.engine import events


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


def chatwoot_effects(conf):
    base = conf.get("chatwoot_base_url") or conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000"
    account = int(conf.get("chatwoot_bot_account_id") or conf.get("chatwoot_account_id") or 1)
    bot_token = conf.get("chatwoot_bot_api_token") or ""
    return ChatwootEffects(ChatwootClient(base, bot_token, account),
                           ChatwootClient(base, conf.get("chatwoot_api_token") or bot_token, account))
