"""Messaging channels a manager connects from /crm/admin/channels (spec 2026-09-28-multi-channel-connections).

Each connected page/account is one Channel Connection row. Facebook is live (channels/facebook.py); the other
providers are listed so the screen shows what comes next, and get their own module with the same shape:
start the login, list the accounts it gives, connect the chosen ones, disconnect, check health.
"""

PROVIDERS = (
    {"key": "facebook", "provider": "Facebook", "label": "Facebook Messenger", "status": "live",
     "description": "Tin nhắn Messenger và Lead Ads của nhiều Fanpage, đăng nhập Facebook một lần"},
    {"key": "instagram", "provider": "Instagram", "label": "Instagram", "status": "soon",
     "description": "Tin nhắn Instagram của tài khoản gắn với Fanpage"},
    {"key": "zalo", "provider": "Zalo OA", "label": "Zalo OA", "status": "soon",
     "description": "Tin nhắn Zalo Official Account (cần Zalo duyệt ứng dụng)"},
    {"key": "tiktok", "provider": "TikTok", "label": "TikTok", "status": "soon",
     "description": "Tin nhắn và lead từ TikTok Business"},
)

STATUSES = ("Connected", "Token expired", "Disconnected", "Error")
