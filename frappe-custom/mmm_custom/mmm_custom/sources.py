"""Lead channels (D-100): the one list of where customers come from. The bot stamps a new Lead's
standard `source` from the Chatwoot conversation's channel, the manager dashboard groups Leads by it,
and channels not connected yet (Zalo, TikTok) are shown as planned so the demo presents the roadmap.

Adding a channel = one row here. A chat channel reaches the bot through a Chatwoot inbox; channels
without a native Chatwoot inbox (Zalo OA, TikTok) arrive through an API inbox whose adapter sets
`conversation.additional_attributes.channel_key` to the row's key, and may set `campaign`."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

# status: live = running today · ready = supported, needs only an inbox connected in Chatwoot ·
# planned = needs an adapter · manual = staff enter these Leads
CHANNELS = (
    {"key": "facebook_messenger", "source": "Facebook Messenger", "label": "Facebook Messenger", "status": "live",
     "how": "Hộp thư Facebook Page trong Chatwoot, bot tư vấn và tạo Lead", "legacy": ("Messenger", "Messenger Bot")},
    {"key": "facebook_lead_ads", "source": "Facebook", "label": "Facebook Lead Ads", "status": "live",
     "how": "Form quảng cáo Facebook, CRM tự kéo Lead về (lead syncing)", "legacy": ()},
    {"key": "instagram", "source": "Instagram", "label": "Instagram Direct", "status": "ready",
     "how": "Kết nối Instagram vào Chatwoot, dùng chung bot và định tuyến", "legacy": ()},
    {"key": "website", "source": "Website", "label": "Chat trên website", "status": "ready",
     "how": "Nhúng widget chat Chatwoot vào website, dùng chung bot", "legacy": ()},
    {"key": "zalo", "source": "Zalo OA", "label": "Zalo OA", "status": "planned",
     "how": "Adapter Zalo OA → hộp thư API của Chatwoot (chờ Zalo duyệt OA)", "legacy": ()},
    {"key": "tiktok", "source": "TikTok", "label": "TikTok", "status": "planned",
     "how": "TikTok Lead Gen + tin nhắn → hộp thư API của Chatwoot", "legacy": ()},
    {"key": "hotline", "source": "Hotline", "label": "Gọi hotline", "status": "manual",
     "how": "Tư vấn viên tạo Lead khi nhận cuộc gọi", "legacy": ()},
    {"key": "walk_in", "source": "Đến trực tiếp", "label": "Đến trực tiếp", "status": "manual",
     "how": "Lễ tân tạo Lead khi khách đến chi nhánh", "legacy": ()},
    {"key": "referral", "source": "Giới thiệu", "label": "Học viên giới thiệu", "status": "live",
     "how": "Mã giới thiệu của học viên cũ, bot nhận ra trong tin nhắn", "legacy": ()},
)
BY_KEY = {c["key"]: c for c in CHANNELS}
UNKNOWN = "Khác"

# Chatwoot inbox channel types (chatwoot/app/models/channel/*) → channel key
CHATWOOT_CHANNELS = {
    "Channel::FacebookPage": "facebook_messenger",
    "Channel::Instagram": "instagram",
    "Channel::WebWidget": "website",
}


def channel_key(conversation):
    """Channel key of a Chatwoot conversation payload (webhook `conversation`), or "" when unknown."""
    conversation = conversation if isinstance(conversation, dict) else {}
    extra = conversation.get("additional_attributes") if isinstance(conversation.get("additional_attributes"), dict) else {}
    if extra.get("channel_key") in BY_KEY:  # set by an API-inbox adapter (Zalo, TikTok)
        return extra["channel_key"]
    if extra.get("type") == "instagram_direct_message":  # Instagram through a Facebook Page inbox
        return "instagram"
    return CHATWOOT_CHANNELS.get(conversation.get("channel") or "", "")


def campaign_of(conversation):
    """Campaign or landing page the conversation started from, when the channel tells us."""
    conversation = conversation if isinstance(conversation, dict) else {}
    extra = conversation.get("additional_attributes") if isinstance(conversation.get("additional_attributes"), dict) else {}
    return str(extra.get("campaign") or extra.get("referer") or "")[:140]


def source_name(key):
    """CRM Lead Source name for a channel key ("" when the key is unknown)."""
    return BY_KEY[key]["source"] if key in BY_KEY else ""


def channel_of_source(source):
    """Channel key of a stored CRM Lead `source`, legacy names included ("" = not one of ours)."""
    for c in CHANNELS:
        if source == c["source"] or source in c["legacy"]:
            return c["key"]
    return ""


def ensure_sources():
    """after_install / after_migrate: one CRM Lead Source per channel."""
    for c in CHANNELS:
        if not frappe.db.exists("CRM Lead Source", c["source"]):
            frappe.get_doc({"doctype": "CRM Lead Source", "source_name": c["source"]}).insert(ignore_permissions=True)
    frappe.db.commit()
