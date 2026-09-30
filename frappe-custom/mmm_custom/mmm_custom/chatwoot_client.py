"""Thin REST client for the Chatwoot API v1.

Used by the bot engine to send messages, update contacts, toggle conversation
status, and assign agents. All methods are synchronous and raise on HTTP errors.
"""

import logging

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


class ChatwootClient:
    """Wrapper around Chatwoot's Account-scoped REST API v1."""

    def __init__(self, base_url: str, api_token: str, account_id: int):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.account_id = account_id

    @property
    def _base(self) -> str:
        return f"{self.base_url}/api/v1/accounts/{self.account_id}"

    @property
    def _headers(self) -> dict:
        return {"api_access_token": self.api_token}

    def send_message(self, conversation_id: int, content: str,
                     content_type: str = "text",
                     content_attributes: dict | None = None) -> dict:
        """Send a message in a conversation."""
        payload = {
            "content": content,
            "message_type": "outgoing",
            "content_type": content_type,
        }
        if content_attributes:
            payload["content_attributes"] = content_attributes
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/messages",
            headers=self._headers, json=payload, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def send_quick_replies(self, conversation_id: int, content: str,
                           items: list[dict]) -> dict:
        """Send a message with Quick Reply buttons (input_select)."""
        return self.send_message(
            conversation_id, content,
            content_type="input_select",
            content_attributes={"items": items},
        )

    def update_contact(self, contact_id: int, custom_attributes: dict,
                       phone_number: str | None = None) -> dict:
        """Merge custom_attributes into a contact (Chatwoot merges them) and optionally set its phone."""
        body = {"custom_attributes": custom_attributes}
        if phone_number:
            body["phone_number"] = phone_number
        resp = requests.patch(
            f"{self._base}/contacts/{contact_id}",
            headers=self._headers,
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def toggle_status(self, conversation_id: int, status: str) -> dict:
        """Toggle a conversation's status (e.g. pending -> open)."""
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/toggle_status",
            headers=self._headers, json={"status": status},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def assign_conversation(self, conversation_id: int,
                            assignee_id: int) -> dict:
        """Assign a conversation to an agent."""
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/assignments",
            headers=self._headers, json={"assignee_id": assignee_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def conversation_viewers(self, conversation_id: int) -> list[int]:
        """Agents looking at the conversation right now (DX-OSD Chatwoot fork, staff assist)."""
        resp = requests.get(f"{self._base}/conversations/{conversation_id}/viewers", headers=self._headers,
                            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("viewers") or []

    def list_agents(self) -> list[dict]:
        """List all agents in the account."""
        resp = requests.get(
            f"{self._base}/agents",
            headers=self._headers, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def list_agent_conversations(self, agent_id: int,
                                 status: str = "open") -> list[dict]:
        """List conversations assigned to a specific agent."""
        resp = requests.get(
            f"{self._base}/conversations",
            headers=self._headers,
            params={"assignee_type": "assigned", "status": status},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # Filter to only this agent's conversations
        convos = data.get("data", {}).get("payload", []) if isinstance(data, dict) else []
        return [c for c in convos
                if ((c.get("meta") or {}).get("assignee") or {}).get("id") == agent_id]

    def add_labels(self, conversation_id: int, labels: list[str]) -> dict:
        """Add labels to a conversation, keeping the ones it already has.

        Chatwoot's POST /labels replaces the whole list, so read it first and merge;
        otherwise the bot hand-off would wipe labels set by agents or the AI layer.
        """
        url = f"{self._base}/conversations/{conversation_id}/labels"
        resp = requests.get(url, headers=self._headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        existing = resp.json().get("payload") or []
        merged = existing + [label for label in dict.fromkeys(labels) if label not in existing]
        if len(merged) == len(existing):
            return {"payload": existing}
        resp = requests.post(url, headers=self._headers, json={"labels": merged}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def list_messages(self, conversation_id: int) -> dict:
        """Conversation messages plus `meta` (labels, contact with custom_attributes)."""
        resp = requests.get(
            f"{self._base}/conversations/{conversation_id}/messages",
            headers=self._headers, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def list_contact_conversations(self, contact_id: int) -> list[dict]:
        """A contact's conversations (the newest first, as Chatwoot returns them)."""
        resp = requests.get(f"{self._base}/contacts/{contact_id}/conversations", headers=self._headers,
                            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("payload") or []

    def send_private_note(self, conversation_id: int, content: str) -> dict:
        """Post a note only agents can see."""
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/messages",
            headers=self._headers,
            json={"content": content, "message_type": "outgoing", "private": True},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    # Account administration (used by the CRM → Chatwoot staff sync, mmm_custom.staff_sync).

    def list_inboxes(self) -> list[dict]:
        resp = requests.get(f"{self._base}/inboxes", headers=self._headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()["payload"]

    def create_agent(self, name: str, email: str, role: str = "agent") -> dict:
        resp = requests.post(f"{self._base}/agents", headers=self._headers,
                             json={"name": name, "email": email, "role": role}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def list_teams(self) -> list[dict]:
        resp = requests.get(f"{self._base}/teams", headers=self._headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def create_team(self, name: str, description: str = "") -> dict:
        resp = requests.post(f"{self._base}/teams", headers=self._headers,
                             json={"name": name, "description": description}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def add_team_members(self, team_id: int, user_ids: list[int]) -> list:
        resp = requests.post(f"{self._base}/teams/{team_id}/team_members", headers=self._headers,
                             json={"user_ids": user_ids}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def update_team_members(self, team_id: int, user_ids: list[int]) -> list:
        """Replace the team's members with exactly `user_ids`."""
        resp = requests.patch(f"{self._base}/teams/{team_id}/team_members", headers=self._headers,
                              json={"user_ids": user_ids}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def list_agent_bots(self) -> list[dict]:
        resp = requests.get(f"{self._base}/agent_bots", headers=self._headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def set_agent_bot(self, inbox_id: int, bot_id: int) -> None:
        resp = requests.post(f"{self._base}/inboxes/{inbox_id}/set_agent_bot", headers=self._headers,
                             json={"agent_bot": bot_id}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

    def add_inbox_members(self, inbox_id: int, user_ids: list[int]) -> list:
        resp = requests.post(f"{self._base}/inbox_members", headers=self._headers,
                             json={"inbox_id": inbox_id, "user_ids": user_ids}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # Channel connections (mmm_custom.channels.facebook); endpoints of our Chatwoot fork, admin token only.

    def connect_facebook_page(self, page_id: str, page_access_token: str, user_access_token: str = "",
                              inbox_name: str = "") -> dict:
        """Create the page's channel and inbox, or renew the token of one connected before. Returns the inbox."""
        resp = requests.post(f"{self._base}/callbacks/connect_facebook_page", headers=self._headers, json={
            "page_id": page_id, "page_access_token": page_access_token, "user_access_token": user_access_token,
            "inbox_name": inbox_name}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def disconnect_facebook_page(self, page_id: str) -> None:
        resp = requests.post(f"{self._base}/callbacks/disconnect_facebook_page", headers=self._headers,
                             json={"page_id": page_id}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

    # Handoff (mmm_custom.engine.effects.ChatwootEffects.handoff).

    def assign_team(self, conversation_id: int, team_id: int) -> dict:
        resp = requests.post(f"{self._base}/conversations/{conversation_id}/assignments", headers=self._headers,
                             json={"team_id": team_id}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def set_conversation_attributes(self, conversation_id: int, attributes: dict, merge: bool = False) -> dict:
        """Replace the conversation's custom attributes, or with `merge` update only the keys sent."""
        body = {"custom_attributes": attributes, **({"merge": True} if merge else {})}
        resp = requests.post(f"{self._base}/conversations/{conversation_id}/custom_attributes", headers=self._headers,
                             json=body, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def list_custom_attributes(self, model: str = "conversation_attribute") -> list:
        resp = requests.get(f"{self._base}/custom_attribute_definitions", headers=self._headers,
                            params={"attribute_model": model}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def create_custom_attribute(self, key: str, display_name: str, model: str = "conversation_attribute",
                                display_type: str = "text") -> dict:
        resp = requests.post(f"{self._base}/custom_attribute_definitions", headers=self._headers, json={
            "attribute_display_name": display_name, "attribute_key": key, "attribute_model": model,
            "attribute_display_type": display_type}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()


def platform_user_token(base_url: str, platform_token: str, name: str, email: str) -> str:
    """A user's own Chatwoot access token through the Platform API. For an existing email Chatwoot returns
    that user (and grants the platform app access to it) instead of creating one."""
    resp = requests.post(f"{base_url.rstrip('/')}/platform/api/v1/users", headers={"api_access_token": platform_token},
                         json={"name": name, "email": email}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("access_token") or ""
