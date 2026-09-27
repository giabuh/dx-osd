"""Every side effect of a bot turn goes through an Effects object (D-060): real Chatwoot/CRM calls
in production (`ChatwootEffects`), a recorder in the Playground and in tests (`RecordingEffects`)."""

import logging

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.data_quality import compute_data_quality
from mmm_custom.engine import events
from mmm_custom.engine.lead import contact_update

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

    def handoff(self, conversation_id, plan, lead, inbox_id=""):
        self.calls.append(("handoff", {"agent_id": plan.agent_id, "team": plan.team, "labels": list(plan.labels),
                                       "attributes": dict(plan.attributes), "summary": plan.summary,
                                       "owner": plan.owner, "lead": lead}))
        return []

    def mark_spam(self, conversation_id):
        self.calls.append(("mark_spam", {"conversation_id": conversation_id}))


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

    def mark_spam(self, conversation_id):
        self.bot.add_labels(conversation_id, ["spam"])
        self.bot.toggle_status(conversation_id, "resolved")

    def save_lead(self, state, fields, courses, contact):
        from mmm_custom.engine import repo

        name = repo.save_lead(state, fields, courses, contact)
        if state.contact_id:
            try:
                self._update_contact(int(state.contact_id), contact_update(fields, courses, name))
            except (ValueError, TypeError):
                pass
        try:
            compute_data_quality(name)
        except Exception:
            logger.exception("data quality update failed")
        return name

    def _update_contact(self, contact_id, update):
        """Write the Lead link and what the bot learned onto the Chatwoot contact. Chatwoot refuses a phone
        another contact already has (422): the attributes are then written without it."""
        try:
            self.user.update_contact(contact_id, update["custom_attributes"], phone_number=update.get("phone_number"))
            return
        except Exception:
            if not update.get("phone_number"):
                logger.exception("contact write-back to Chatwoot failed")
                return
        try:
            self.user.update_contact(contact_id, update["custom_attributes"])
        except Exception:
            logger.exception("contact write-back to Chatwoot failed")

    def handoff(self, conversation_id, plan, lead, inbox_id=""):
        """D-058 steps 2–3; each step is independent so one failing call never blocks the rest.
        The consultant joins the conversation's inbox first, so staff only belong to the pages
        they actually got customers from (mmm_custom.staff_sync)."""
        from mmm_custom.engine import repo

        errors = []

        def step(name, fn, *args):
            try:
                fn(*args)
            except Exception as e:
                errors.append({"type": "handoff_step_failed", "step": name, "detail": str(e)[:300]})

        team_id = None
        try:
            team_id = next((t["id"] for t in self.user.list_teams() if t["name"].lower() == plan.team.lower()), None)
        except Exception as e:
            errors.append({"type": "handoff_step_failed", "step": "list_teams", "detail": str(e)[:300]})
        if team_id:  # team before agent: Chatwoot keeps the agent when they belong to the team
            step("assign_team", self.bot.assign_team, conversation_id, team_id)
        if plan.agent_id and inbox_id:
            step("inbox_member", self.user.add_inbox_members, int(inbox_id), [plan.agent_id])
        if plan.agent_id:
            step("assign_agent", self.bot.assign_conversation, conversation_id, plan.agent_id)
        step("open", self.bot.toggle_status, conversation_id, "open")
        if plan.labels:
            step("labels", self.bot.add_labels, conversation_id, plan.labels)
        if plan.attributes:
            step("attributes", self.bot.set_conversation_attributes, conversation_id, plan.attributes)
        if plan.summary:
            step("summary_note", self.bot.send_private_note, conversation_id, plan.summary)
        if plan.owner and lead:
            step("lead_owner", repo.set_lead_owner, lead, plan.owner)
        return errors


def chatwoot_effects(conf):
    base = conf.get("chatwoot_base_url") or conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000"
    account = int(conf.get("chatwoot_bot_account_id") or conf.get("chatwoot_account_id") or 1)
    bot_token = conf.get("chatwoot_bot_api_token") or ""
    return ChatwootEffects(ChatwootClient(base, bot_token, account),
                           ChatwootClient(base, conf.get("chatwoot_api_token") or bot_token, account))
