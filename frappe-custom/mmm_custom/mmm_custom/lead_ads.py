"""Facebook Lead Ads for the /admin page. Sync logic stays in crm/lead_syncing (Lead Sync Source,
Facebook Page, Facebook Lead Form, Failed Lead Sync Log); this module only lets managers configure it."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

import json

from mmm_custom.desk import can_open_bot

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

FREQUENCIES = ("Every 5 Minutes", "Every 10 Minutes", "Every 15 Minutes", "Hourly", "Daily", "Monthly")
DEFAULT_FREQUENCY = "Hourly"
SOURCE_FIELDS = ("access_token", "facebook_page", "facebook_lead_form", "background_sync_frequency", "enabled")
DATA_TYPES = frozenset(("Data", "Small Text", "Text", "Long Text", "Select", "Link", "Int", "Float", "Currency",
                        "Date", "Datetime", "Phone", "Autocomplete"))
FIRST_FIELDS = (("first_name", "First Name"), ("email", "Email"), ("mobile_no", "Mobile No"))
SYNC_SET_FIELDS = frozenset(("source", "facebook_lead_id", "facebook_form_id", "naming_series"))  # set by the sync


def _require_access():
    if not can_open_bot():
        frappe.throw("Bạn không có quyền cấu hình Facebook Lead Ads.", frappe.PermissionError)


def _get(field, key, default=None):
    return field.get(key, default) if isinstance(field, dict) else getattr(field, key, default)


def lead_field_choices(meta_fields):
    """CRM Lead fields a form question can map to: [{value, label}], name/email/phone first."""
    labels = {_get(f, "fieldname"): _get(f, "label") for f in meta_fields}
    choices = [{"value": name, "label": labels.get(name) or label} for name, label in FIRST_FIELDS]
    seen = {name for name, _ in FIRST_FIELDS}
    for f in meta_fields:
        name = _get(f, "fieldname")
        if (name in seen or name in SYNC_SET_FIELDS or _get(f, "fieldtype") not in DATA_TYPES
                or _get(f, "hidden") or _get(f, "read_only")):
            continue
        seen.add(name)
        choices.append({"value": name, "label": _get(f, "label") or name})
    return choices


def clean_source_values(values, is_new):
    """Form values → Lead Sync Source fields. Only whitelisted fields; ValueError names what is wrong."""
    values = values or {}
    out = {k: values[k] for k in SOURCE_FIELDS if k in values}
    token = str(out.pop("access_token", "") or "").strip()
    if token:
        out["access_token"] = token
    elif is_new:
        raise ValueError("Cần nhập access token của Facebook.")
    for key, label in (("facebook_page", "Page"), ("facebook_lead_form", "Form")):
        if key in out or is_new:
            out[key] = str(out.get(key) or "").strip()
            if not out[key]:
                raise ValueError(f"Chọn {label}.")
    frequency = out.get("background_sync_frequency") or (DEFAULT_FREQUENCY if is_new else None)
    if frequency is not None:
        if frequency not in FREQUENCIES:
            raise ValueError(f"Tần suất không hợp lệ: {frequency}")
        out["background_sync_frequency"] = frequency
    if "enabled" in out or is_new:
        out["enabled"] = 1 if str(out.get("enabled", 1)).lower() not in ("0", "false", "") else 0
    return out


def clean_mapping(mapping, allowed):
    """{question_key: crm_field or ""} → the same dict; a CRM field outside `allowed` is refused."""
    if isinstance(mapping, str):
        mapping = json.loads(mapping or "{}")
    out = {}
    for key, field in (mapping or {}).items():
        field = str(field or "").strip()
        if field and field not in allowed:
            raise ValueError(f"Trường CRM không hợp lệ: {field}")
        out[str(key)] = field
    return out


def page_choices(pages):
    """Facebook /me/accounts pages (with tokens) → [{id, name, forms: [{id, name}]}] for the browser."""
    return [{"id": p.get("id"), "name": p.get("name") or p.get("page_name") or p.get("id"),
             "forms": [{"id": f.get("id"), "name": f.get("name") or f.get("form_name") or f.get("id")}
                       for f in p.get("forms") or []]} for p in pages or []]


def short_error(traceback):
    """The last meaningful traceback line, short enough for a table cell."""
    lines = [line.strip() for line in str(traceback or "").splitlines() if line.strip()]
    return (lines[-1] if lines else "")[:200]


def _throw_value_error(fn, *args):
    try:
        return fn(*args)
    except ValueError as error:
        frappe.throw(str(error))


@whitelist()
def list_sources():
    _require_access()
    pages = dict(frappe.get_all("Facebook Page", fields=["name", "page_name"], as_list=True))
    forms = dict(frappe.get_all("Facebook Lead Form", fields=["name", "form_name"], as_list=True))
    failed = dict(frappe.get_all("Failed Lead Sync Log", filters={"type": "Failure"},
                                 fields=["source", "count(name) as count"], group_by="source", as_list=True))
    rows = frappe.get_all("Lead Sync Source", fields=["name", "type", "facebook_page", "facebook_lead_form", "enabled",
                                                      "background_sync_frequency", "last_synced_at"],
                          order_by="creation desc")
    for row in rows:
        row["page_name"] = pages.get(row.facebook_page) or row.facebook_page or ""
        row["form_name"] = forms.get(row.facebook_lead_form) or row.facebook_lead_form or ""
        row["failures"] = failed.get(row.name, 0)
    return {"sources": rows, "frequencies": list(FREQUENCIES)}


@whitelist()
def pages():
    """Pages and forms already stored by an earlier connect, for editing a source without its token."""
    _require_access()
    stored = frappe.get_all("Facebook Page", fields=["name as id", "page_name as name"])
    for page in stored:
        page["forms"] = frappe.get_all("Facebook Lead Form", filters={"page": page["id"]},
                                       fields=["name as id", "form_name as name"])
    return stored


@whitelist()
def connect(access_token=""):
    _require_access()
    from crm.lead_syncing.doctype.lead_sync_source.facebook import fetch_and_store_pages_from_facebook

    try:
        return page_choices(fetch_and_store_pages_from_facebook((access_token or "").strip()))
    except frappe.ValidationError:
        raise
    except Exception as error:  # Graph API HTTP errors carry Facebook's own message
        frappe.throw(f"Facebook từ chối: {error}")


@whitelist()
def save_source(values=None):
    _require_access()
    if isinstance(values, str):
        values = json.loads(values or "{}")
    values = values or {}
    name = str(values.get("name") or "").strip()  # the source being edited; empty for a new one
    fields = _throw_value_error(clean_source_values, values, not name)
    if not name:
        doc = frappe.get_doc({"doctype": "Lead Sync Source", "type": "Facebook", **fields})
        doc.name = str(values.get("title") or "").strip() or frappe.db.get_value(
            "Facebook Lead Form", fields["facebook_lead_form"], "form_name") or fields["facebook_lead_form"]
        doc.set("__newname", doc.name)  # autoname: prompt
        doc.insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("Lead Sync Source", name)
        doc.update(fields)
        doc.save(ignore_permissions=True)
    return doc.name


@whitelist()
def set_enabled(name, enabled=1):
    _require_access()
    doc = frappe.get_doc("Lead Sync Source", name)
    doc.enabled = 1 if str(enabled).lower() not in ("0", "false", "") else 0
    doc.save(ignore_permissions=True)
    return doc.enabled


def _lead_fields():
    return lead_field_choices(frappe.get_meta("CRM Lead").fields)


@whitelist()
def form_mapping(form):
    _require_access()
    doc = frappe.get_doc("Facebook Lead Form", form)
    return {"form": doc.name, "form_name": doc.form_name, "fields": _lead_fields(),
            "questions": [{"key": q.key, "label": q.label, "type": q.type, "mapped_to_crm_field": q.mapped_to_crm_field}
                          for q in doc.questions]}


@whitelist()
def save_mapping(form, mapping=None):
    _require_access()
    cleaned = _throw_value_error(clean_mapping, mapping, {c["value"] for c in _lead_fields()})
    doc = frappe.get_doc("Facebook Lead Form", form)
    for question in doc.questions:
        if question.key in cleaned:
            question.mapped_to_crm_field = cleaned[question.key]
    doc.save(ignore_permissions=True)
    return len(cleaned)


@whitelist()
def sync_now(name):
    _require_access()
    frappe.get_doc("Lead Sync Source", name).sync_leads()  # queued outside developer mode
    return True


@whitelist()
def failures(limit=50):
    _require_access()
    rows = frappe.get_all("Failed Lead Sync Log", filters={"type": "Failure"},
                          fields=["name", "source", "creation", "traceback"], order_by="creation desc",
                          limit=min(int(limit or 50), 200))
    return [{"name": r.name, "source": r.source, "creation": r.creation, "error": short_error(r.traceback)}
            for r in rows]


@whitelist()
def retry(name):
    _require_access()
    lead = frappe.get_doc("Failed Lead Sync Log", name).retry_sync()
    return getattr(lead, "name", lead)
