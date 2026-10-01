"""Comment funnel (D-122, spec 2026-10-01-comment-funnel-design.md): a comment under one of our Facebook posts
is classified, answered from CRM data (public reply, and a private reply that brings the customer into
Messenger, where Chatwoot and the bot take over), and the Lead that follows remembers the post it came from.

Pure helpers (classify, plan, post_context, compose, handle, psid_of, lead_updates) are tested offline; `run`
(scheduler, every 5 minutes, off unless site config `comment_funnel_enabled`) and `attribute` (called from the
Chatwoot webhook) touch the database and the Graph API."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine import actions, voucher
from mmm_custom.engine.catalog import DEFAULT_SETTINGS
from mmm_custom.engine.context import brand_context, course_context
from mmm_custom.engine.quiz import quiz_for
from mmm_custom.engine.render import render_text
from mmm_custom.engine.text import fold

QUIZ, PRICE, INTEREST, PRAISE, OTHER = "quiz", "price", "interest", "praise", "other"
INTENTS = (QUIZ, PRICE, INTEREST, PRAISE, OTHER)
# Folded phrases, checked in this order: a question beats praise ("hay quá, học phí sao ạ" is a fee question).
QUIZ_WORDS = ("test", "kiem tra trinh do", "bai kiem tra")
PRICE_WORDS = ("hoc phi", "gia", "bao nhieu", "chi phi", "bn", "nhieu tien", "lich hoc", "khai giang",
               "khi nao hoc", "may gio", "hoc may buoi")
INTEREST_WORDS = ("tu van", "dang ky", "dang ki", "inbox", "ib", "ibx", "info", "thong tin", "chi tiet", "quan tam",
                  "cho xin", "xin thong tin", "lop", "hoc o dau", "dia chi", "co so", "chi nhanh", "cho minh hoi", "hoi", "hoc")
PRAISE_WORDS = ("hay", "dep", "tuyet", "thich", "chat", "good", "great", "love", "tot", "huu ich", "cam on", "ok",
                "xuat sac", "dinh", "xin")  # folded "xịn"; "xin" as a request is caught above as "cho xin"…
SENTIMENTS = {QUIZ: "Quan tâm khóa học", INTEREST: "Quan tâm khóa học", PRICE: "Hỏi học phí / lịch",
              PRAISE: "Tích cực", OTHER: "Spam / Khác"}
PRIVATE_REPLY_DAYS = 7  # Facebook accepts one private reply per comment, within 7 days of it
POST_DAYS = 14  # posts whose comments are still watched
GRAPH = "https://graph.facebook.com/v21.0"
CAMPAIGN_PREFIX = "Bình luận: "


def _has(folded, phrases):
    padded = f" {folded} "
    return any(f" {p} " in padded for p in phrases)


def classify(text, quiz_aliases=()):
    """quiz / price (fee or schedule) / interest / praise / other for one comment. Pure."""
    folded = fold(text)
    if not folded:
        return OTHER
    if _has(folded, tuple(fold(a) for a in quiz_aliases) + QUIZ_WORDS):
        return QUIZ
    for intent, words in ((PRICE, PRICE_WORDS), (INTEREST, INTEREST_WORDS), (PRAISE, PRAISE_WORDS)):
        if _has(folded, words):
            return intent
    return OTHER


def sentiment(intent):
    """The `Facebook Post Comment.sentiment` label of an intent."""
    return SENTIMENTS.get(intent, SENTIMENTS[OTHER])


def plan(intent):
    """(public reply, private reply) for an intent."""
    if intent in (QUIZ, PRICE, INTEREST):
        return True, True
    return intent == PRAISE, False


@dataclass
class PostContext:
    post: object = None
    title: str = ""
    course: dict = field(default_factory=dict)
    promo: dict = field(default_factory=dict)
    quiz_keyword: str = ""
    quiz_aliases: tuple = ()
    settings: dict = field(default_factory=dict)
    renderer: object = None


def _course_of(code, catalog):
    if not code:
        return None
    return catalog.courses.get(code) or next((c for c in catalog.courses.values() if c.name == code), None)


def post_context(post, catalog, promotions, renderer):
    """What a post's replies are built from: its course, the best active promotion for it, its level test."""
    course = _course_of(post.get("course"), catalog)
    ctx = PostContext(post=post.get("name"), title=post.get("title") or "", settings=catalog.settings,
                      renderer=renderer)
    if not course:
        return ctx
    ctx.course = course_context(course, catalog)
    best, off = voucher.best_promotion(promotions, ctx.course, "", actions.applicable, actions.discount)
    if best:
        ctx.promo = {"title": best["title"], "final_fee": max(course.fee - off, 0)}
    quiz = catalog.skills.get(quiz_for(catalog.skills, course.code, course.group))
    if quiz and quiz.aliases:
        ctx.quiz_keyword, ctx.quiz_aliases = quiz.aliases[0], tuple(quiz.aliases)
    return ctx


def _template(settings, key):
    return (settings or {}).get(key) or DEFAULT_SETTINGS[key]


def compose(intent, name, ctx):
    """{"public": text, "private": text} for a comment; "" where nothing is sent. Pure."""
    public, private = plan(intent)
    values = {"brand": brand_context({**DEFAULT_SETTINGS, **(ctx.settings or {})}),
              "customer": {"name": " ".join(str(name or "").split())}, "course": ctx.course, "promo": ctx.promo,
              "quiz": {"keyword": ctx.quiz_keyword}, "intent": intent}
    out = {"public": "", "private": ""}
    if public:
        key = "comment_thanks_template" if intent == PRAISE else "comment_public_template"
        out["public"] = render_text(_template(ctx.settings, key), values, ctx.renderer)
    if private:
        out["private"] = render_text(_template(ctx.settings, "comment_private_template"), values, ctx.renderer)
    return out


def _parse_time(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return None


def handle(comment, post_name, ctx, sender, page_id, now):
    """Answer one comment through `sender` (.public(id, text), .private(id, text) → psid) and return the
    `Facebook Comment Reply` row. Errors are recorded in the row, never raised."""
    author = comment.get("from") or {}
    created = _parse_time(comment.get("created_time"))
    row = {"comment_id": comment.get("id"), "facebook_post": post_name, "from_name": author.get("name") or "",
           "comment_message": (comment.get("message") or "")[:1000],
           "comment_time": created.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created else None,
           "intent": OTHER, "status": "Skipped", "public_reply": "", "private_reply": "", "psid": "", "error": ""}
    if page_id and str(author.get("id") or "") == str(page_id):
        return row
    row["intent"] = classify(comment.get("message"), ctx.quiz_aliases)
    texts = compose(row["intent"], row["from_name"], ctx)
    if created and now - created > timedelta(days=PRIVATE_REPLY_DAYS):
        texts["private"] = ""
    if not (texts["public"] or texts["private"]):
        return row
    try:
        if texts["public"]:
            sender.public(row["comment_id"], texts["public"])
            row["public_reply"] = texts["public"]
        if texts["private"]:
            row["psid"] = str(sender.private(row["comment_id"], texts["private"]) or "")
            row["private_reply"] = texts["private"]
        row["status"] = "Replied"
    except Exception as e:
        row.update(status="Failed", error=str(e)[:500])
    return row


def psid_of(conversation):
    """The customer's page-scoped id of a Facebook Messenger conversation (Chatwoot contact inbox `source_id`)."""
    conversation = conversation if isinstance(conversation, dict) else {}
    extra = conversation.get("additional_attributes") if isinstance(conversation.get("additional_attributes"), dict) else {}
    if conversation.get("channel") != "Channel::FacebookPage" or extra.get("type") == "instagram_direct_message":
        return ""
    contact_inbox = conversation.get("contact_inbox") if isinstance(conversation.get("contact_inbox"), dict) else {}
    return str(contact_inbox.get("source_id") or "")


def lead_updates(current, post_name, post_title):
    """Fields to write on a Lead the post brought: only empty ones (first touch, D-100). `current` holds the
    fields the Lead has."""
    out = {}
    if "facebook_post" in current and not current.get("facebook_post"):
        out["facebook_post"] = post_name
    if "source_campaign" in current and not current.get("source_campaign"):
        out["source_campaign"] = f"{CAMPAIGN_PREFIX}{post_title}"[:140]
    return out


def failure_note(rows):
    """The managers' message when comments could not be answered (no permission, expired token), else ""."""
    failed = [r for r in rows if r.get("status") == "Failed"]
    if not failed:
        return ""
    first = failed[0]
    return (f"{len(failed)} bình luận chưa trả lời được. Ví dụ: {first.get('from_name') or 'khách'}: "
            f"{(first.get('error') or '')[:160]}. Kiểm tra token và quyền trang Facebook.")


# ── Bench side ─────────────────────────────────────────────────────────────────────────────────────


class GraphSender:
    def __init__(self, page_id, token):
        self.page_id, self.token = page_id, token

    def public(self, comment_id, text):
        import requests

        resp = requests.post(f"{GRAPH}/{comment_id}/comments", data={"message": text, "access_token": self.token},
                             timeout=15)
        if not resp.ok:
            raise RuntimeError(f"public reply: {resp.text[:300]}")

    def private(self, comment_id, text):
        import requests

        resp = requests.post(f"{GRAPH}/{self.page_id}/messages", params={"access_token": self.token},
                             json={"recipient": {"comment_id": comment_id}, "message": {"text": text}}, timeout=15)
        if not resp.ok:
            raise RuntimeError(f"private reply: {resp.text[:300]}")
        return resp.json().get("recipient_id") or ""


class DrySender:
    """dry_run: nothing reaches Facebook."""

    def public(self, comment_id, text):
        pass

    def private(self, comment_id, text):
        return ""


def _comments(fb_post_id, token):
    import requests

    resp = requests.get(f"{GRAPH}/{fb_post_id}/comments", params={
        "access_token": token, "fields": "id,from,message,created_time", "filter": "toplevel",
        "order": "reverse_chronological", "limit": 100}, timeout=20)
    resp.raise_for_status()
    return resp.json().get("data", [])


def _claim(comment_id, post_name):
    """Insert the row first: the unique comment_id makes a second run skip this comment."""
    try:
        doc = frappe.get_doc({"doctype": "Facebook Comment Reply", "comment_id": comment_id,
                              "facebook_post": post_name, "status": "Processing"})
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc.name
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback()
        return ""


def run(dry_run=False):
    """Scheduler (every 5 minutes): answer new comments on posts published in the last POST_DAYS days.
    `bench execute mmm_custom.comment_funnel.run --kwargs "{'dry_run': 1}"` lists what it would send."""
    if not dry_run and not frappe.conf.get("comment_funnel_enabled"):
        return {"status": "disabled"}
    page_id = frappe.conf.get("facebook_page_id")
    token = frappe.conf.get("facebook_page_access_token")
    if not (page_id and token):
        return {"status": "no_token"}
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo, load_catalog

    catalog, today = load_catalog(), frappe.utils.getdate()
    promotions = FrappeRepo().active_promotions(today)
    cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -POST_DAYS)
    posts = frappe.get_all("Facebook Post", filters={"status": "Posted", "fb_post_id": ["is", "set"],
                                                     "posted_at": [">=", cutoff]},
                           fields=["name", "title", "course", "fb_post_id"])
    sender = DrySender() if dry_run else GraphSender(page_id, token)
    now, rows = datetime.now(timezone.utc), []
    for post in posts:
        ctx = post_context(post, catalog, promotions, frappe_renderer)
        try:
            comments = _comments(post.fb_post_id, token)
        except Exception as e:
            frappe.log_error(title="Comment funnel: comments not read", message=f"{post.name}: {e}")
            continue
        for c in comments:
            if not c.get("id") or frappe.db.exists("Facebook Comment Reply", {"comment_id": c["id"]}):
                continue
            if dry_run:
                rows.append(handle(c, post.name, ctx, sender, page_id, now))
                continue
            name = _claim(c["id"], post.name)
            if not name:
                continue
            row = handle(c, post.name, ctx, sender, page_id, now)
            frappe.db.set_value("Facebook Comment Reply", name, {k: v for k, v in row.items() if k != "comment_id"})
            frappe.db.commit()
            rows.append(row)
    if dry_run:
        return {"status": "dry_run", "rows": rows}
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    _tell_managers(failure_note(rows))
    return {"status": "ok", "handled": len(rows), **counts}


def _tell_managers(note):
    """At most one notification an hour: an expired token fails every comment of every run."""
    if not note or not frappe.cache().set("mmm_custom:comment_funnel:failure_note", 1, nx=True, ex=3600):
        return
    try:
        from crm.fcrm.doctype.crm_notification.crm_notification import notify_crm_users

        notify_crm_users(title="Phễu bình luận Facebook gặp lỗi", message=note, notification_type="System",
                         reference_doctype="Facebook Comment Reply")
    except Exception:
        frappe.log_error(title="Comment funnel: failure notification not sent", message=note)


def attribute(conversation, lead=""):
    """Chatwoot webhook: a Messenger customer we answered under a comment now has a Lead. Links the reply row
    and gives the Lead its post (first touch). Returns the Lead name or ""; never raises."""
    try:
        psid = psid_of(conversation)
        if not psid:
            return ""
        row = frappe.db.get_value("Facebook Comment Reply", {"psid": psid, "lead": ["is", "not set"]},
                                  ["name", "facebook_post"], as_dict=True)
        if not row:
            return ""
        if not lead:
            from mmm_custom.engine.repo import find_lead

            contact = ((conversation.get("meta") or {}).get("sender")
                       or (conversation.get("contact_inbox") or {}).get("contact") or {})
            lead = find_lead(str(contact.get("id") or ""), contact)
        if not lead:
            return ""
        frappe.db.set_value("Facebook Comment Reply", row.name, "lead", lead)
        doc = frappe.get_doc("CRM Lead", lead)
        current = {f: doc.get(f) for f in ("facebook_post", "source_campaign") if doc.meta.has_field(f)}
        title = frappe.db.get_value("Facebook Post", row.facebook_post, "title") if row.facebook_post else ""
        updates = lead_updates(current, row.facebook_post, title or f"#{row.facebook_post}") if row.facebook_post else {}
        if updates:
            doc.update(updates)
            doc.flags.lead_engine = True
            doc.save(ignore_permissions=True)
        return lead
    except Exception:
        if frappe:
            frappe.log_error(title="Comment funnel: attribution failed")
        return ""
