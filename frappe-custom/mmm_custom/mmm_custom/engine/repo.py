"""Database side of the engine: the catalog snapshot (cached in Redis, cleared on edits) and
Bot Conversation state. Verified against a running bench (the offline tests use FakeRepo)."""

import json

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.dedupe import find_matching_lead, normalize_phone
from mmm_custom.engine.lead import PLACEHOLDER_NAMES, contact_prefill, prefill_slots
from mmm_custom.engine.catalog import DEFAULT_SETTINGS, build_catalog
from mmm_custom.engine.render import WEEKDAYS
from mmm_custom.engine.state import ConversationState

CACHE_KEY = "lead_engine_catalog_rows"


def _children(doctype, parent_doctype, parentfield, fields):
    rows = frappe.get_all(doctype, filters={"parenttype": parent_doctype, "parentfield": parentfield},
                          fields=["parent", *fields], order_by="idx asc", parent_doctype=parent_doctype)
    out = {}
    for r in rows:
        out.setdefault(r.parent, []).append({f: r.get(f) for f in fields})
    return out


def _territories():
    rows = frappe.get_all("CRM Territory", fields=[
        "name", "parent_crm_territory", "is_group", "branch_code", "button_label", "branch_tier", "address",
        "hotline", "map_url", "aliases"])
    by_name = {r.name: r for r in rows}
    areas = {}
    for r in rows:
        parent = by_name.get(r.parent_crm_territory)
        if r.is_group or not parent:
            continue
        area = areas.setdefault(parent.name, {"territory_name": parent.name, "button_label": parent.button_label,
                                              "aliases": parent.aliases, "branches": []})
        area["branches"].append({"territory_name": r.name, "branch_code": r.branch_code, "button_label": r.button_label,
                                 "tier": r.branch_tier, "address": r.address, "hotline": r.hotline,
                                 "map_url": r.map_url, "aliases": r.aliases})
    return {"areas": list(areas.values())}


def load_rows():
    """The whole engine catalog from the database, in the demo-dataset shape build_catalog expects."""
    products = frappe.get_all("CRM Product", filters={"disabled": 0, "course_group": ["is", "set"]}, fields=[
        "name", "product_code", "product_name", "button_label", "course_group", "standard_rate", "duration_text",
        "audience", "min_age", "max_age", "certificate", "offer", "aliases", "image"])
    code_of = {p.name: p.product_code for p in products}
    nexts = _children("Course Link", "CRM Product", "next_courses", ["course"])
    courses = [{**p, "next_courses": [code_of.get(n["course"], n["course"]) for n in nexts.get(p.name, [])]}
               for p in products]
    groups = frappe.get_all("Course Group", fields=["group_name", "button_label", "emoji", "sort_order", "aliases",
                                                    "description"], order_by="sort_order asc")
    slots = frappe.get_all("Bot Slot", filters={"active": 1}, fields=[
        "slot_key", "label", "slot_type", "catalog_source", "required", "sort_order", "ask_template",
        "depends_on_slot", "depends_on_value", "lead_field"])
    options = _children("Bot Slot Option", "Bot Slot", "options", ["value", "label", "button_label", "aliases"])
    skills = frappe.get_all("Bot Skill", filters={"active": 1}, fields=[
        "skill_key", "title", "jev_description", "examples", "aliases", "missing_policy", "action_type",
        "action_config", "media", "creates_lead", "handoff_after", "sort_order"])
    params = _children("Bot Slot Link", "Bot Skill", "parameters", ["bot_slot"])
    templates = _children("Bot Skill Template", "Bot Skill", "templates", ["variant_key", "when", "template"])
    follow_ups = _children("Bot Skill Follow Up", "Bot Skill", "follow_ups", ["title", "target_type", "target"])
    for s in skills:
        s["action_config"] = json.loads(s.action_config) if s.action_config else {}
        s["parameters"] = [p["bot_slot"] for p in params.get(s.skill_key, [])]
        s["templates"] = templates.get(s.skill_key, [])
        s["follow_ups"] = follow_ups.get(s.skill_key, [])
    settings_doc = frappe.get_single("Lead Engine Settings").as_dict()
    settings = {k: v for k, v in settings_doc.items() if k in DEFAULT_SETTINGS or k.endswith("_template")}
    return {
        "areas": _territories(), "course_groups": [dict(g) for g in groups], "courses": courses,
        "bot_slots": [{**s, "options": options.get(s.slot_key, [])} for s in slots],
        "bot_skills": [dict(s) for s in skills], "settings": settings,
    }


def load_catalog():
    cache = frappe.cache()
    rows = cache.get_value(CACHE_KEY)
    if rows is None:
        rows = load_rows()
        cache.set_value(CACHE_KEY, rows)
    return build_catalog(rows)


def clear_catalog_cache(doc=None, method=None):
    """doc_events hook: any edit to catalog, slot, skill or settings data takes effect on the next message."""
    frappe.cache().delete_value(CACHE_KEY)


def _json(value):
    if isinstance(value, dict):
        return value
    return json.loads(value) if value else {}


def find_lead(contact_id, contact, phone=None, email=None):
    """The Lead for a Chatwoot contact: crm_lead_id → chatwoot_contact_id → phone/email match."""
    attrs = contact.get("custom_attributes") or {}
    if attrs.get("crm_lead_id") and frappe.db.exists("CRM Lead", attrs["crm_lead_id"]):
        return attrs["crm_lead_id"]
    if contact_id:
        name = frappe.db.get_value("CRM Lead", {"chatwoot_contact_id": str(contact_id)})
        if name:
            return name
    if phone or email:
        matched = find_matching_lead(email, phone)
        if matched:
            return matched.name if hasattr(matched, "name") else matched.get("name")
    return None


def _append_products(doc, courses):
    have = {p.product_code for p in doc.get("products") or []}
    for c in courses:
        if c.code not in have:
            doc.append("products", {"product_code": c.code, "product_name": c.name, "qty": 1, "rate": c.fee,
                                    "amount": c.fee, "net_amount": c.fee})
    names = [p.product_name or p.product_code for p in doc.get("products") or []]
    if names:
        doc.course_interest = ", ".join(names)[:140]  # readable summary kept beside products (D-014)


def add_products(lead_name, courses):
    doc = frappe.get_doc("CRM Lead", lead_name)
    _append_products(doc, courses)
    doc.flags.lead_engine = True
    doc.save(ignore_permissions=True)


def save_lead(state, fields, courses, contact):
    """Create or update the conversation's Lead. Never overwrites a real name or a different phone a
    person entered; courses are appended, not replaced (D-022)."""
    name = state.lead if state.lead and frappe.db.exists("CRM Lead", state.lead) else None
    name = name or find_lead(state.contact_id, contact, fields.get("mobile_no"), contact.get("email"))
    if name:
        doc = frappe.get_doc("CRM Lead", name)
    else:
        raw_name = " ".join(str(contact.get("name") or "").split())
        doc = frappe.new_doc("CRM Lead")
        doc.update({"first_name": raw_name or PLACEHOLDER_NAMES[0], "email": contact.get("email") or None})
        if frappe.db.exists("CRM Lead Source", "Messenger Bot"):  # created by after_install; older sites may lack it
            doc.source = "Messenger Bot"
    if state.contact_id and not doc.get("chatwoot_contact_id"):
        doc.chatwoot_contact_id = state.contact_id  # link a phone-matched Lead so the next conversation finds it
    for field, val in fields.items():
        if not doc.meta.has_field(field):
            continue
        if field == "first_name":
            if doc.first_name not in PLACEHOLDER_NAMES:
                continue
            doc.lead_name = val
        if field == "mobile_no":
            val = normalize_phone(val)
            if doc.mobile_no and doc.mobile_no != val:
                continue
        doc.set(field, val)
    _append_products(doc, courses)
    doc.flags.lead_engine = True  # learning.on_lead_update skips the engine's own saves (D-057)
    if name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    return doc.name


class FrappeRepo:
    def __init__(self, sandbox=False, sandbox_lead=None):
        self.sandbox, self.sandbox_lead = sandbox, sandbox_lead
        self._catalog = None

    def catalog(self):
        if self._catalog is None:
            self._catalog = load_catalog()
        return self._catalog

    def today(self):
        return frappe.utils.getdate()

    def load_state(self, event):
        name = frappe.db.get_value("Bot Conversation", {"conversation_id": event.conversation_id})
        if not name:
            return self.new_state(event)
        d = frappe.get_doc("Bot Conversation", name)
        return ConversationState(
            conversation_id=d.conversation_id, contact_id=d.contact_id or "", inbox_id=d.inbox_id or "",
            lead=d.lead or "", status=d.status or "active", slots=_json(d.slots), pending=_json(d.pending),
            pending_skill=d.pending_skill or "", stuck_turns=d.stuck_turns or 0,
            last_message_id=int(d.last_message_id or 0), consultant_replied=bool(d.consultant_replied),
            consultant=d.consultant or "", is_sandbox=bool(d.is_sandbox), is_returning=bool(d.is_returning),
            turns=d.turns or 0)

    def new_state(self, event):
        """A new conversation starts from what CRM already knows about the contact (D-022, D-070)."""
        catalog = self.catalog()
        state = ConversationState(conversation_id=event.conversation_id, contact_id=str(event.contact.get("id") or ""),
                                  inbox_id=event.inbox_id, is_sandbox=self.sandbox,
                                  slots=contact_prefill(event.contact, catalog))
        lead = self.sandbox_lead if self.sandbox else find_lead(state.contact_id, event.contact)
        if not lead or not frappe.db.exists("CRM Lead", lead):
            return state
        meta = frappe.get_meta("CRM Lead")
        fields = sorted({s.lead_field for s in catalog.slots
                         if s.lead_field and s.lead_field != "products" and meta.has_field(s.lead_field)})
        values = (frappe.db.get_value("CRM Lead", lead, fields, as_dict=True) or {}) if fields else {}
        state.slots.update(prefill_slots(values, catalog))
        state.lead = lead
        earlier = state.contact_id and frappe.db.exists("Bot Conversation", {"contact_id": state.contact_id, "is_sandbox": 0})
        has_products = frappe.db.count("CRM Products", {"parenttype": "CRM Lead", "parent": lead})
        state.is_returning = bool(earlier or has_products or values.get("territory"))
        return state

    def save_state(self, state):
        values = {
            "conversation_id": state.conversation_id, "contact_id": state.contact_id, "inbox_id": state.inbox_id,
            "lead": state.lead or None, "status": state.status, "slots": json.dumps(state.slots, ensure_ascii=False),
            "pending": json.dumps(state.pending, ensure_ascii=False), "pending_skill": state.pending_skill or None,
            "stuck_turns": state.stuck_turns, "last_message_id": state.last_message_id,
            "consultant_replied": int(state.consultant_replied), "consultant": state.consultant or None,
            "is_sandbox": int(state.is_sandbox), "is_returning": int(state.is_returning), "turns": state.turns,
        }
        name = frappe.db.get_value("Bot Conversation", {"conversation_id": state.conversation_id})
        if name:
            doc = frappe.get_doc("Bot Conversation", name)
            doc.update(values)
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({"doctype": "Bot Conversation", **values}).insert(ignore_permissions=True)

    def open_schedules(self, course, branch, shift, today, limit):
        filters = {"course": course, "status": "Open", "start_date": [">=", today]}
        if branch:
            filters["branch"] = branch
        if shift:
            filters["shift"] = ["like", f"{shift}%"]
        rows = frappe.get_all("Course Schedule", filters=filters, fields=["start_date", "shift", "weekdays", "branch", "seats"],
                              order_by="start_date asc", limit=limit)
        return [{"date": r.start_date, "weekday": WEEKDAYS[r.start_date.weekday()], "shift": r.shift,
                 "weekdays": r.weekdays, "branch": r.branch, "seats_left": r.seats} for r in rows]

    def active_promotions(self, today):
        rows = frappe.get_all("Course Promotion", filters={"active": 1},
                              fields=["name", "title", "discount_type", "discount_value", "valid_from", "valid_to"])
        rows = [r for r in rows if (not r.valid_from or r.valid_from <= today) and (not r.valid_to or today <= r.valid_to)]
        courses = _children("Course Link", "Course Promotion", "courses", ["course"])
        groups = _children("Course Group Link", "Course Promotion", "course_groups", ["course_group"])
        branches = _children("Territory Link", "Course Promotion", "branches", ["branch"])
        return [{"title": r.title, "discount_type": r.discount_type, "discount_value": r.discount_value,
                 "courses": [c["course"] for c in courses.get(r.name, [])],
                 "course_groups": [g["course_group"] for g in groups.get(r.name, [])],
                 "branches": [b["branch"] for b in branches.get(r.name, [])]} for r in rows]

    def write_log(self, row):
        frappe.get_doc({"doctype": "AI Decision Log", **row}).insert(ignore_permissions=True)

    def write_signal(self, row):
        frappe.get_doc({"doctype": "Bot Learning Signal", **row}).insert(ignore_permissions=True)
