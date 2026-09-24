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

    def update_contact(self, contact_id: int,
                       custom_attributes: dict) -> dict:
        """Update a contact's custom_attributes."""
        resp = requests.patch(
            f"{self._base}/contacts/{contact_id}",
            headers=self._headers,
            json={"custom_attributes": custom_attributes},
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
                if c.get("meta", {}).get("assignee", {}).get("id") == agent_id]
