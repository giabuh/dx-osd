"""House tone for what customers read (D-106): gentle, cheerful, and addressing people the way a
consultant does. The bot never writes free text (Jev only decides), so every customer-facing template is
checked here: by the tests over the demo data and when a manager saves a quiz in /crm/admin.

- Pronouns come from Lead Engine Settings: {{ brand.me }} ("em") and {{ brand.you }} ("anh/chị");
  "mình", "bạn", "tôi", "cậu" are never hard-coded.
- A message opens with "Dạ", or addresses the customer ({{ brand.you | capitalize }} …?), and is polite ("ạ").
- At most one emoji, where there is a feeling to share (😊 🎉 🎁 👏).
"""

import re

BANNED = re.compile(r"(?<![\wÀ-ỹ])(mình|bạn|tôi|cậu)(?![\wÀ-ỹ])", re.IGNORECASE)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)
ADDRESSES_CUSTOMER = re.compile(r"^\s*(\{%.*?%\}\s*)*\{\{\s*brand\.you")
MAX_EMOJI = 1
QUOTED = re.compile(r'"[^"]*"|“[^”]*”')  # what the customer is told to type ("tôi muốn đăng ký học"), not a pronoun


def problems(template):
    """What breaks the house tone in one customer-facing template ([] when fine). Pure."""
    template = template or ""
    text = QUOTED.sub("", JINJA.sub("", template)).strip()
    if not text:
        return []
    found = []
    words = sorted({m.group(0).lower() for m in BANNED.finditer(text)})
    if words:
        found.append(f"xưng hô viết cứng: {', '.join(words)} (dùng {{{{ brand.me }}}} / {{{{ brand.you }}}})")
    if not (text.startswith("Dạ") or ADDRESSES_CUSTOMER.match(template)):
        found.append("nên mở đầu bằng \"Dạ\" hoặc gọi khách ({{ brand.you | capitalize }} …)")
    if "ạ" not in (text[2:] if text.startswith("Dạ") else text):
        found.append("thiếu \"ạ\" cho lịch sự")
    if len(EMOJI.findall(text)) > MAX_EMOJI:
        found.append(f"nhiều hơn {MAX_EMOJI} emoji")
    return found
