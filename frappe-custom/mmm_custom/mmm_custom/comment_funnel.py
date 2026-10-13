"""Comment funnel (D-124, spec 2026-10-01-comment-funnel-design.md): a comment under one of our Facebook posts
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
from mmm_custom.engine.text import fold, is_smalltalk

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

QUIZ, PRICE, INTEREST, PRAISE, GREETING, OTHER = "quiz", "price", "interest", "praise", "greeting", "other"
INTENTS = (QUIZ, PRICE, INTEREST, PRAISE, GREETING, OTHER)
# Folded phrases, checked in this order: a question beats praise ("hay quá, học phí sao ạ" is a fee question).
QUIZ_WORDS = ("test", "kiem tra trinh do", "bai kiem tra")
PRICE_WORDS = ("hoc phi", "gia", "bao nhieu", "chi phi", "bn", "nhieu tien", "lich hoc", "khai giang",
               "khi nao hoc", "may gio", "hoc may buoi")
INTEREST_WORDS = ("tu van", "dang ky", "dang ki", "inbox", "ib", "ibx", "info", "thong tin", "chi tiet", "quan tam",
                  "cho xin", "xin thong tin", "lop", "hoc o dau", "dia chi", "co so", "chi nhanh", "cho minh hoi", "hoi", "hoc")
PRAISE_WORDS = ("hay", "dep", "tuyet", "thich", "chat", "good", "great", "love", "tot", "huu ich", "cam on", "ok",
                "xuat sac", "dinh", "xin")  # folded "xịn"; "xin" as a request is caught above as "cho xin"…
SENTIMENTS = {QUIZ: "Quan tâm khóa học", INTEREST: "Quan tâm khóa học", PRICE: "Hỏi học phí / lịch",
              PRAISE: "Tích cực", GREETING: "Tích cực", OTHER: "Spam / Khác"}
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
    if is_smalltalk(folded):  # "hi", "chào shop": someone saying hello gets a hello back, never a private message
        return GREETING
    return OTHER


def sentiment(intent):
    """The `Facebook Post Comment.sentiment` label of an intent."""
    return SENTIMENTS.get(intent, SENTIMENTS[OTHER])


def plan(intent):
    """(public reply, private reply) for an intent."""
    if intent in (QUIZ, PRICE, INTEREST):
        return True, True
    return intent in (PRAISE, GREETING), False


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
    facts: dict = field(default_factory=dict)  # marketing_plan.build_facts of the post: what a reply may state
    writer: object = None  # generate(prompt, system=...) -> text: Gemini writes the replies (D-129), else templates


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
        key = {PRAISE: "comment_thanks_template", GREETING: "comment_greeting_template"}.get(
            intent, "comment_public_template")
        out["public"] = render_text(_template(ctx.settings, key), values, ctx.renderer)
    if private:
        out["private"] = render_text(_template(ctx.settings, "comment_private_template"), values, ctx.renderer)
    return out


def _parse_time(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return None


WRITER_SYSTEM = (
    "Bạn là nhân viên tư vấn tuyển sinh của một trung tâm đào tạo, trả lời bình luận trên trang Facebook. "
    "Viết tiếng Việt tự nhiên, lễ phép như nhân viên thật: bắt đầu bằng \"Dạ\", xưng \"em\", gọi khách là "
    "\"anh/chị\" (kèm tên nếu có), có \"ạ\"; không dùng mình/bạn/tôi; tối đa 1 emoji; không markdown. "
    "Chỉ dùng thông tin trong DỮ LIỆU; không bịa học phí, ưu đãi, phần trăm, số điện thoại, địa chỉ hay đường link. "
    "Trả về đúng một JSON: {\"public\": \"...\", \"private\": \"...\"}.")
MAX_PUBLIC, MAX_PRIVATE = 320, 760
# What a customer types in Messenger to start registering (the bot reads it as a registration, D-121): the private reply
# ends with it, so the chat that follows is not pushed into registration on a remark like "giá sao đắt thế".
REGISTER_PHRASE = "tôi muốn đăng ký học"
REGISTER_HINT = f'Nếu anh/chị muốn đăng ký học, anh/chị nhắn "{REGISTER_PHRASE}" để em hỗ trợ ngay ạ.'


def states_a_price(text):
    """True when a text names an amount or a percentage: a public reply never shows a price (the fee and offers go
    in the private message only). Pure."""
    import re as _re

    from mmm_custom.engine.staff_replies import MONEY_RE

    return bool(MONEY_RE.search(text or "") or _re.search(r"\d+(?:[.,]\d+)?\s*%", text or ""))


def with_register_hint(text):
    """The private reply ends with how to start registering, once. Pure."""
    text = (text or "").rstrip()
    if not text or fold(REGISTER_PHRASE) in fold(text):
        return text
    return f"{text} {REGISTER_HINT}"


def writer_prompt(intent, name, comment, ctx, public, private):
    """What Gemini is asked for one comment: the comment, what to write and the CRM facts it may use. Pure."""
    from mmm_custom.marketing_plan import facts_lines

    asks = []
    if public:
        asks.append("- public: trả lời công khai dưới bình luận, 1-2 câu ngắn (dưới 35 chữ)"
                    + ("; cảm ơn khách" if intent == PRAISE else "")
                    + ("; chào lại và mời nhắn tin cho trang" if intent == GREETING else "")
                    + ("; chỉ báo đã nhắn tin riêng và mời xem hộp thư Messenger" if private else "")
                    + "; KHÔNG nêu học phí, ưu đãi, phần trăm hay con số nào")
    if private:
        asks.append("- private: tin nhắn riêng gửi vào Messenger, 2-4 câu (dưới 70 chữ): trả lời đúng điều khách hỏi"
                    " bằng DỮ LIỆU, và mời khách trả lời tin nhắn để được tư vấn lịch học, giữ suất học thử")
    if private and ctx.quiz_keyword:
        asks.append(f'- trong private, mời khách nhắn "{ctx.quiz_keyword}" để làm bài test trình độ miễn phí')
    if private:  # the system appends REGISTER_HINT after the checks (its quoted "tôi" would fail the tone check)
        asks.append("- private: không cần viết câu hướng dẫn đăng ký, hệ thống tự thêm vào cuối")
    if not public:
        asks.append('- public: ""')
    if not private:
        asks.append('- private: ""')
    data = "\n".join(f"  • {x}" for x in facts_lines(ctx.facts or {})) or "  • (không có)"
    return (f"Loại bình luận: {intent}\nTên khách: {name or '(không rõ)'}\nBình luận: \"{(comment or '')[:500]}\"\n"
            f"Bài đăng: {ctx.title or ''}\nDỮ LIỆU:\n{data}\nViết:\n" + "\n".join(asks))


def _parse_texts(raw):
    import json
    import re as _re

    if not raw:
        return {}
    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}
    return {k: " ".join(str(data.get(k) or "").replace("**", "").split()) for k in ("public", "private")}


def acceptable(text, facts, limit, public=False):
    """Why a generated reply may not be sent ("" = fine): the house tone (D-106), no amount, percentage or phone
    the CRM data does not back, no link, a sane length. Pure."""
    from mmm_custom.engine.tone import problems
    from mmm_custom.marketing_plan import unsupported_claims

    if not text:
        return "trống"
    if len(text) > limit:
        return "quá dài"
    if "http" in text.lower() or "www." in text.lower():
        return "có đường link"
    if public and states_a_price(text):
        return "nêu giá công khai"
    found = problems(text) + unsupported_claims(text, facts or {})
    return "; ".join(found)


def ai_texts(intent, name, comment, ctx):
    """{"public": ..., "private": ...} written by `ctx.writer` (Gemini) for the parts the intent plans; a part that
    fails `acceptable` is left out (the template answers it), so a bad generation is never sent."""
    public, private = plan(intent)
    if not ctx.writer or not (public or private):
        return {}
    texts = _parse_texts(ctx.writer(writer_prompt(intent, name, comment, ctx, public, private), system=WRITER_SYSTEM))
    out = {}
    for kind, wanted, limit in (("public", public, MAX_PUBLIC), ("private", private, MAX_PRIVATE)):
        text = texts.get(kind) or ""
        if wanted and not acceptable(text, ctx.facts, limit, public=kind == "public"):
            if kind == "private" and ctx.quiz_keyword and fold(ctx.quiz_keyword) not in fold(text):
                text = f'{text} Anh/chị nhắn "{ctx.quiz_keyword}" để làm bài test trình độ miễn phí ạ.'
            out[kind] = text
    return out


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
    wanted = [k for k in ("public", "private") if texts[k]]
    try:
        written = ai_texts(row["intent"], row["from_name"], comment.get("message"), ctx)
    except Exception:
        written = {}
    texts.update(written)
    texts["private"] = with_register_hint(texts["private"])
    row["writer"] = ("gemini" if wanted and all(k in written for k in wanted)
                     else "mixed" if written else "template")
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


def page_credentials(page):
    """(page id, token) of the Facebook Page a post was published on; a post without one uses the site's default
    page (site config facebook_page_id / facebook_page_access_token)."""
    if page and frappe.db.exists("Facebook Page", page):
        row = frappe.db.get_value("Facebook Page", page, ["name", "access_token"], as_dict=True)
        if row and row.access_token:
            return row.name, row.access_token
    return frappe.conf.get("facebook_page_id"), frappe.conf.get("facebook_page_access_token")


def _post_facts(post):
    from mmm_custom.marketing_plan import post_facts

    return post_facts(post.get("course"), page=post.get("facebook_page")) if post.get("course") else {}


def _gemini_writer():
    """Gemini writes the replies when a key is set and site config `comment_funnel_gemini` is not 0 (D-129)."""
    from mmm_custom import llm

    if str(frappe.conf.get("comment_funnel_gemini", 1)) == "0" or not llm.api_key():
        return None
    return lambda prompt, system="": llm.generate(prompt, system=system, temperature=0.5)


def run(dry_run=False):
    """Scheduler (every 5 minutes): answer new comments on posts published in the last POST_DAYS days.
    `bench execute mmm_custom.comment_funnel.run --kwargs "{'dry_run': 1}"` lists what it would send."""
    if not dry_run and not frappe.conf.get("comment_funnel_enabled"):
        return {"status": "disabled"}
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo, load_catalog

    catalog, today = load_catalog(), frappe.utils.getdate()
    promotions = FrappeRepo().active_promotions(today)
    cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -POST_DAYS)
    posts = frappe.get_all("Facebook Post", filters={"status": "Posted", "fb_post_id": ["is", "set"],
                                                     "posted_at": [">=", cutoff]},
                           fields=["name", "title", "course", "fb_post_id", "facebook_page"])
    posts = [p for p in posts if not str(p.fb_post_id).startswith("demo-")]  # sample posts (scripts/seed-demo.sh)
    now, rows, senders = datetime.now(timezone.utc), [], {}
    for post in posts:
        page_id, token = page_credentials(post.get("facebook_page"))
        if not (page_id and token):
            frappe.log_error(title="Comment funnel: no page token", message=f"{post.name}: {post.get('facebook_page')}")
            continue
        if page_id not in senders:
            senders[page_id] = DrySender() if dry_run else GraphSender(page_id, token)
        sender = senders[page_id]
        ctx = post_context(post, catalog, promotions, frappe_renderer)
        ctx.facts = _post_facts(post)
        ctx.writer = _gemini_writer()
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


@whitelist()
def run_now():
    """Manager button "Trả lời bình luận ngay" (Facebook Marketing): the 5-minute job, right away (a live demo does
    not wait for the scheduler). Same switch as the job: nothing is sent while comment_funnel_enabled is off."""
    from mmm_custom.desk import can_open_bot

    if not can_open_bot():
        frappe.throw("Chỉ quản lý được chạy trả lời bình luận.", frappe.PermissionError)
    if not frappe.conf.get("comment_funnel_enabled"):
        return {"status": "disabled"}
    return run()


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
