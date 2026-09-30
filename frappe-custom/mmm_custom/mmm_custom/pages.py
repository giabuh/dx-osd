"""Which Facebook page a Lead messaged. Each connected page is its own Chatwoot inbox, so a person who
messages two pages is two Chatwoot contacts and usually two Leads; `facebook_page` tells them apart in
the Leads list and on the Lead's chat. A Lead matched from a second page (same phone) lists both."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

FIELD = "facebook_page"
# Same column as the default list in crm/crm/fcrm/doctype/crm_lead/crm_lead.py; keep the two alike.
COLUMN = {"label": "Facebook Page", "type": "Data", "key": FIELD, "width": "10rem"}


def merge_pages(current, page):
    """"A" + "B" → "A, B"; a page already listed is not repeated. Pure."""
    names = [p.strip() for p in (current or "").split(",") if p.strip()]
    if page and page not in names:
        names.append(page)
    return ", ".join(names)[:140]


def add_column(columns, after="lead_name"):
    """A list view's columns with the page column right after `after`; None when it is already there. Pure."""
    if any(c.get("key") == FIELD for c in columns):
        return None
    at = next((i + 1 for i, c in enumerate(columns) if c.get("key") == after), len(columns))
    return columns[:at] + [dict(COLUMN)] + columns[at:]


def page_of_inbox(inbox_id):
    """Name of the page connected as this Chatwoot inbox (Channel Connection), or ""."""
    if not str(inbox_id or "").strip().isdigit():
        return ""
    name = frappe.db.get_value("Channel Connection", {"chatwoot_inbox_id": int(inbox_id)}, "display_name")
    return (name or "").strip()


def record_page(lead, inbox_id):
    """Add the inbox's page to the Lead's pages, without touching `modified`."""
    page = page_of_inbox(inbox_id)
    if not lead or not page:
        return
    current = frappe.db.get_value("CRM Lead", lead, FIELD) or ""
    merged = merge_pages(current, page)
    if merged != current:
        frappe.db.set_value("CRM Lead", lead, FIELD, merged, update_modified=False)


def backfill():
    """Pages of the Leads the bot already talked to, from their Bot Conversations (run once, by a patch)."""
    names = {str(r.chatwoot_inbox_id): (r.display_name or "").strip()
             for r in frappe.get_all("Channel Connection", fields=["chatwoot_inbox_id", "display_name"])}
    wanted = {}
    for row in frappe.get_all("Bot Conversation", filters={"is_sandbox": 0, "lead": ["is", "set"],
                                                           "inbox_id": ["is", "set"]},
                              fields=["lead", "inbox_id"], order_by="creation asc"):
        if names.get(row.inbox_id):
            wanted.setdefault(row.lead, []).append(names[row.inbox_id])
    if not wanted:
        return
    for lead in frappe.get_all("CRM Lead", filters={"name": ["in", list(wanted)]}, fields=["name", FIELD]):
        merged = lead.get(FIELD) or ""
        for page in wanted[lead.name]:
            merged = merge_pages(merged, page)
        if merged != (lead.get(FIELD) or ""):
            frappe.db.set_value("CRM Lead", lead.name, FIELD, merged, update_modified=False)
    frappe.db.commit()


def ensure_list_column():
    """Show the page column in every saved Leads list view (the default one comes from CRMLead), once."""
    import json

    for name, columns in frappe.get_all("CRM View Settings", filters={"dt": "CRM Lead", "type": "list"},
                                        fields=["name", "columns"], as_list=True):
        try:
            current = json.loads(columns or "[]")
        except ValueError:
            continue
        if not current:
            continue  # no saved columns: the view uses the default list, which already has the page
        updated = add_column(current)
        if updated:
            frappe.db.set_value("CRM View Settings", name, "columns", json.dumps(updated))
    frappe.db.commit()
