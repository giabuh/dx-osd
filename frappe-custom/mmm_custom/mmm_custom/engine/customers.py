"""Customer dashboard (D-101) for managers at /crm/admin/customers: who the customers are, where they
come from, which courses and branches they want, who serves them and why. Covers every CRM Lead of
the period, not only the bot's. `build` is pure; `overview` reads the rows."""

from collections import Counter

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.desk import can_open_bot
from mmm_custom.lifecycle import CONVERTED, LABELS, QUALIFIED, TRIAL_BOOKED, reached
from mmm_custom.sources import BY_KEY, CHANNELS, UNKNOWN, channel_of_source

PERIODS = (7, 30, 90, 365)
HOTNESS = (("hot", "Nóng"), ("warm", "Ấm"), ("cold", "Lạnh"), ("", "Chưa rõ"))
NO_GROUP, NO_BRANCH = "Chưa rõ khóa", "Chưa rõ chi nhánh"


def _count(rows):
    """[{name, count}] biggest first; the "unknown" bucket always last."""
    order = lambda kv: (kv[0] in (NO_GROUP, NO_BRANCH), -kv[1], kv[0])
    return [{"name": k, "count": v} for k, v in sorted(Counter(rows).items(), key=order)]


def build(leads, groups_by_lead, consultants, reasons, latest=15):
    """leads: CRM Lead rows (name, lead_name, first_name, mobile_no, source, territory, lead_owner, status,
    converted, ai_hotness, creation); groups_by_lead: {lead: [course group, ...]}; consultants: Consultant rows
    (user, full_name, branch, level, handles_b2b); reasons: {lead: why the bot assigned it}."""
    people = {c["user"]: c for c in consultants}
    qualified = lambda r: reached(r.get("status"), QUALIFIED, r.get("converted"))  # D-116: or any later step
    channel = {r["name"]: channel_of_source(r.get("source") or "") for r in leads}

    by_channel = Counter(channel.values())
    # `values`: the Lead.source values of the channel, so the dashboard can open the filtered Leads list
    sources = [{**{k: c[k] for k in ("key", "label", "status", "how")}, "count": by_channel.get(c["key"], 0),
                "values": [c["source"], *c["legacy"]]} for c in CHANNELS]
    if by_channel.get(""):
        sources.append({"key": "", "label": UNKNOWN, "status": "other", "how": "Nguồn khác do nhân viên nhập",
                        "count": by_channel[""]})

    staff = {}
    for r in leads:
        owner = r.get("lead_owner")
        if not owner:
            continue
        p = people.get(owner, {})
        row = staff.setdefault(owner, {"user": owner, "full_name": p.get("full_name") or owner,
                                       "branch": p.get("branch") or ("Doanh nghiệp (B2B)" if p.get("handles_b2b") else "Tổng đài"),
                                       "level": p.get("level", ""), "leads": 0, "qualified": 0, "converted": 0})
        row["leads"] += 1
        row["qualified"] += int(bool(qualified(r)))
        row["converted"] += int(bool(r.get("converted")))
    for row in staff.values():
        row["rate"] = round(100 * row["converted"] / row["leads"]) if row["leads"] else 0

    b2b = sum(1 for r in leads if people.get(r.get("lead_owner"), {}).get("handles_b2b"))
    totals = {"leads": len(leads), "with_phone": sum(1 for r in leads if r.get("mobile_no")),
              "qualified": sum(1 for r in leads if qualified(r)), "assigned": sum(1 for r in leads if r.get("lead_owner")),
              "trial": sum(1 for r in leads if reached(r.get("status"), TRIAL_BOOKED, r.get("converted"))),
              "converted": sum(1 for r in leads if r.get("converted")),
              "hot": sum(1 for r in leads if r.get("ai_hotness") == "hot"), "b2b": b2b}
    funnel = [{"stage": "Lead mới", "count": totals["leads"]}, {"stage": "Có số điện thoại", "count": totals["with_phone"]},
              {"stage": LABELS[QUALIFIED], "count": totals["qualified"]}, {"stage": "Đã giao tư vấn", "count": totals["assigned"]},
              {"stage": "Hẹn học thử", "count": totals["trial"]}, {"stage": LABELS[CONVERTED], "count": totals["converted"]}]

    hot_labels = dict(HOTNESS)
    newest = sorted(leads, key=lambda r: str(r.get("creation") or ""), reverse=True)[:latest]
    return {
        "totals": totals,
        "funnel": funnel,
        "sources": sources,
        "groups": _count(g for r in leads for g in (groups_by_lead.get(r["name"]) or [NO_GROUP])),
        "branches": _count(r.get("territory") or NO_BRANCH for r in leads),
        "hotness": [{"name": label, "count": sum(1 for r in leads if (r.get("ai_hotness") or "") == key)}
                    for key, label in HOTNESS],
        "consultants": sorted(staff.values(), key=lambda s: (-s["converted"], -s["qualified"], -s["leads"], s["full_name"])),
        "latest": [{
            "name": r["name"], "customer": r.get("lead_name") or r.get("first_name") or r["name"],
            "source": BY_KEY[channel[r["name"]]]["label"] if channel[r["name"]] else (r.get("source") or UNKNOWN),
            "groups": ", ".join(groups_by_lead.get(r["name"]) or []) or "—",
            "territory": r.get("territory") or "—",
            "owner": people.get(r.get("lead_owner"), {}).get("full_name") or r.get("lead_owner") or "—",
            "status": LABELS[CONVERTED] if r.get("converted") else LABELS.get(r.get("status"), r.get("status") or "—"),
            "hotness": hot_labels.get(r.get("ai_hotness") or "", "Chưa rõ"),
            "why": reasons.get(r["name"], ""), "creation": r.get("creation"),
        } for r in newest],
    }


def handoff_why(reason):
    """The routing part of a logged handoff reason: "Đã đủ thông tin · CN Q7 · ít khách nhất · Lead: Đủ thông tin" →
    "CN Q7 · ít khách nhất"."""
    parts = [p.strip() for p in (reason or "").split("·")]
    return " · ".join(p for p in parts[1:] if p and not p.startswith("Lead:"))


@frappe.whitelist() if frappe else (lambda fn: fn)
def overview(days=30):
    if not can_open_bot():
        frappe.throw("Bạn không có quyền xem trang này.", frappe.PermissionError)
    days = int(days) if str(days).isdigit() and int(days) in PERIODS else 30
    since = frappe.utils.add_days(frappe.utils.today(), -days + 1)
    return {"days": days, **report(since)}


def report(since):
    """`build` over every CRM Lead created on or after `since` (a date string); the caller checks access."""
    leads = [dict(r) for r in frappe.get_all(
        "CRM Lead", filters={"creation": [">=", f"{since} 00:00:00"]}, limit_page_length=0,
        fields=["name", "lead_name", "first_name", "mobile_no", "source", "territory", "lead_owner", "status",
                "converted", "ai_hotness", "creation"])]
    names = [r["name"] for r in leads]
    groups_by_lead, reasons = {}, {}
    if names:
        products = frappe.get_all("CRM Products", filters={"parenttype": "CRM Lead", "parent": ["in", names]},
                                  fields=["parent", "product_code"], limit_page_length=0)
        group_of = dict(frappe.get_all("CRM Product", fields=["name", "course_group"], as_list=True, limit_page_length=0))
        for p in products:
            group = group_of.get(p.product_code)
            if group and group not in groups_by_lead.setdefault(p.parent, []):
                groups_by_lead[p.parent].append(group)
        for log in frappe.get_all("AI Decision Log", filters={"decision_type": "handoff", "is_sandbox": 0,
                                                                "lead": ["in", names]},
                                  fields=["lead", "reason"], order_by="creation asc", limit_page_length=0):
            reasons[log.lead] = handoff_why(log.reason)
    consultants = [dict(c) for c in frappe.get_all("Consultant", fields=["user", "full_name", "branch", "level", "handles_b2b"],
                                                    limit_page_length=0)]
    return {"since": since, **build(leads, groups_by_lead, consultants, reasons)}
