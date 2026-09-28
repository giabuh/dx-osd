"""Facebook pages: log in once, pick many pages, each becomes a Chatwoot inbox with the lead-engine bot.

Flow (spec 2026-09-28-multi-channel-connections):
1. `start` gives the Facebook login URL; Facebook sends the manager back to `callback` with a code.
2. `callback` trades the code for a long-lived user token and keeps it in the cache for a short while
   (`use_token` does the same with a token pasted by hand, for a site without a public HTTPS address).
3. `pages` lists the pages that token manages; `connect` sends each chosen page's token to Chatwoot
   (callbacks/connect_facebook_page, which subscribes the page's webhooks), stores the page and its
   Lead Ads forms in the CRM, and records a Channel Connection with the page's branch.
Page tokens obtained from a long-lived user token do not expire; `check_health` still checks them daily.

Needs `facebook_app_id` and `facebook_app_secret` in the site config (scripts/configure-chatwoot.py copies them
from .env). The Facebook app must list the callback URL under "Valid OAuth Redirect URIs".
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

try:
    import requests
except ImportError:
    requests = None

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from mmm_custom.desk import can_open_bot

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

GRAPH = "https://graph.facebook.com/v23.0"
DIALOG = "https://www.facebook.com/v23.0/dialog/oauth"
SCOPES = ("pages_show_list", "pages_messaging", "pages_manage_metadata", "pages_read_engagement",
          "leads_retrieval", "business_management")
CALLBACK_METHOD = "mmm_custom.channels.facebook.callback"
ADMIN_ROUTE = "/crm/admin/channels"
STATE_TTL = 600  # seconds between "Kết nối Facebook" and Facebook sending the manager back
TOKEN_TTL = 1800  # seconds the user token stays in the cache for picking pages
MESSAGING_TASKS = frozenset(("MANAGE", "MODERATE", "MESSAGING"))
REQUEST_TIMEOUT = 15
PROVIDER = "Facebook"


class GraphError(Exception):
    """Facebook answered with an error; the message is Facebook's own."""


# Pure helpers (tested offline).

def app_credentials(conf):
    """(app_id, app_secret) from the site config; ValueError says what is missing."""
    app_id = str(conf.get("facebook_app_id") or "").strip()
    secret = str(conf.get("facebook_app_secret") or "").strip()
    if not app_id or not secret:
        raise ValueError("Chưa cấu hình Facebook App: cần facebook_app_id và facebook_app_secret trong site config.")
    return app_id, secret


def callback_url(conf, site_url):
    """Where Facebook sends the manager back: `facebook_redirect_uri` when set (behind a proxy), else this site."""
    return (conf.get("facebook_redirect_uri") or f"{site_url.rstrip('/')}/api/method/{CALLBACK_METHOD}").strip()


def _sign(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def make_state(secret, user, now):
    """`<timestamp>.<hmac>` tying the login to this user, so a forged callback is refused."""
    ts = str(int(now))
    return f"{ts}.{_sign(secret, f'{user}.{ts}')}"


def state_ok(secret, state, user, now, ttl=STATE_TTL):
    ts, _, signature = str(state or "").partition(".")
    if not ts.isdigit() or not signature:
        return False
    if not 0 <= now - int(ts) <= ttl:
        return False
    return hmac.compare_digest(signature, _sign(secret, f"{user}.{ts}"))


def auth_url(app_id, redirect, state, scopes=SCOPES):
    return f"{DIALOG}?" + urlencode({"client_id": app_id, "redirect_uri": redirect, "state": state,
                                     "response_type": "code", "scope": ",".join(scopes)})


def graph_get(http, path, params):
    """GET a Graph API path (or a full paging URL); GraphError with Facebook's message on failure."""
    url = path if path.startswith("https://") else f"{GRAPH}/{path.lstrip('/')}"
    resp = http.get(url, params=params, timeout=REQUEST_TIMEOUT)
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if "error" in data or getattr(resp, "status_code", 200) >= 400:
        error = data.get("error") or {}
        raise GraphError(error.get("message") or f"HTTP {getattr(resp, 'status_code', '?')}")
    return data


def exchange_code(http, app_id, secret, redirect, code):
    return graph_get(http, "oauth/access_token", {"client_id": app_id, "client_secret": secret,
                                                   "redirect_uri": redirect, "code": code})["access_token"]


def long_lived_token(http, app_id, secret, token):
    """A 60-day user token; the page tokens it gives do not expire."""
    return graph_get(http, "oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": app_id,
                                                   "client_secret": secret, "fb_exchange_token": token})["access_token"]


def list_pages(http, user_token):
    """Every page the user manages (following Facebook's paging), with its page token."""
    pages, data = [], graph_get(http, "me/accounts", {"access_token": user_token, "limit": 100,
                                                      "fields": "id,name,category,access_token,tasks,picture{url}"})
    while True:
        pages.extend(data.get("data") or [])
        next_url = (data.get("paging") or {}).get("next")
        if not next_url:
            return pages
        data = graph_get(http, next_url, {})


def can_message(page):
    """Facebook only lets page roles with one of these tasks answer messages; no task list means unknown."""
    tasks = page.get("tasks")
    return tasks is None or bool(MESSAGING_TASKS.intersection(tasks))


def page_choices(pages, connections):
    """Pages from Facebook + existing connections (by page id) → rows for the picker. Never carries a token."""
    out = []
    for p in pages:
        conn = connections.get(str(p.get("id"))) or {}
        out.append({"id": str(p.get("id")), "name": p.get("name") or str(p.get("id")),
                    "category": p.get("category") or "",
                    "picture": ((p.get("picture") or {}).get("data") or {}).get("url") or "",
                    "can_message": can_message(p), "connected": conn.get("status") == "Connected",
                    "status": conn.get("status") or "", "branch": conn.get("branch") or ""})
    return out


def clean_selection(selection, available, branches):
    """[{id, branch}] from the browser → the same list; ValueError for a page the token does not manage
    or a branch that does not exist."""
    if isinstance(selection, str):
        selection = json.loads(selection or "[]")
    out, seen = [], set()
    for item in selection or []:
        page_id = str((item or {}).get("id") or "").strip()
        branch = str((item or {}).get("branch") or "").strip()
        if not page_id or page_id in seen:
            continue
        if page_id not in available:
            raise ValueError(f"Tài khoản Facebook này không quản lý page {page_id}.")
        if branch and branch not in branches:
            raise ValueError(f"Chi nhánh không tồn tại: {branch}")
        seen.add(page_id)
        out.append({"id": page_id, "branch": branch})
    if not out:
        raise ValueError("Chọn ít nhất một page.")
    return out


def health(debug, now):
    """debug_token data → (status, error, expires_at). expires_at 0 means the token never expires."""
    if not debug.get("is_valid"):
        return "Token expired", (debug.get("error") or {}).get("message") or "Token không còn hiệu lực.", None
    missing = sorted({"pages_messaging", "pages_manage_metadata"} - set(debug.get("scopes") or []))
    expires = int(debug.get("expires_at") or 0)
    if expires and expires < now:
        return "Token expired", "Token đã hết hạn.", expires
    if missing:
        return "Error", "Thiếu quyền: " + ", ".join(missing), expires or None
    return "Connected", "", expires or None


# Site glue.

def _require_access():
    if not can_open_bot():
        frappe.throw("Bạn không có quyền kết nối kênh.", frappe.PermissionError)


def _credentials():
    try:
        return app_credentials(frappe.conf)
    except ValueError as error:
        frappe.throw(str(error))


def _redirect():
    return callback_url(frappe.conf, frappe.utils.get_url())


def _cache_key(user=None):
    return f"mmm_custom:facebook_login:{user or frappe.session.user}"


def _remember_login(http, token):
    me = graph_get(http, "me", {"access_token": token, "fields": "id,name"})
    frappe.cache().set_value(_cache_key(), {"token": token, "account_id": me.get("id"), "account_name": me.get("name")},
                             expires_in_sec=TOKEN_TTL)
    return me


def _login():
    login = frappe.cache().get_value(_cache_key())
    if not login or not login.get("token"):
        frappe.throw("Phiên đăng nhập Facebook đã hết, bấm “Kết nối Facebook” lại.")
    return login


def _connections():
    rows = frappe.get_all("Channel Connection", filters={"provider": PROVIDER},
                          fields=["name", "external_id", "status", "branch", "chatwoot_inbox_id"])
    return {r.external_id: r for r in rows}


def _admin_route(**query):
    return ADMIN_ROUTE + ("?" + urlencode(query) if query else "")


def _redirect_to(location):
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = location


@whitelist()
def start():
    """The Facebook login URL; the browser goes there."""
    _require_access()
    app_id, secret = _credentials()
    return {"url": auth_url(app_id, _redirect(), make_state(secret, frappe.session.user, time.time()))}


@whitelist(methods=["GET"])
def callback(code=None, state=None, error=None, error_description=None, **_):
    """Facebook sends the manager back here; they land on the channels tab with the page picker open."""
    _require_access()
    if error or not code:
        return _redirect_to(_admin_route(facebook_error=error_description or error or "Không nhận được mã đăng nhập."))
    app_id, secret = _credentials()
    if not state_ok(secret, state, frappe.session.user, time.time()):
        return _redirect_to(_admin_route(facebook_error="Phiên đăng nhập không hợp lệ hoặc đã quá hạn, thử lại."))
    try:
        token = long_lived_token(requests, app_id, secret, exchange_code(requests, app_id, secret, _redirect(), code))
        _remember_login(requests, token)
    except GraphError as err:
        return _redirect_to(_admin_route(facebook_error=f"Facebook từ chối: {err}"))
    _redirect_to(_admin_route(facebook="pick"))


@whitelist(methods=["POST"])
def use_token(access_token=""):
    """A user token pasted by hand (Graph API Explorer), for sites Facebook cannot redirect to."""
    _require_access()
    token = (access_token or "").strip()
    if not token:
        frappe.throw("Dán access token của tài khoản Facebook quản lý các page.")
    try:
        conf_ok = frappe.conf.get("facebook_app_id") and frappe.conf.get("facebook_app_secret")
        if conf_ok:
            app_id, secret = _credentials()
            token = long_lived_token(requests, app_id, secret, token)
        _remember_login(requests, token)
    except GraphError as err:
        frappe.throw(f"Facebook từ chối: {err}")
    return pages()


@whitelist()
def pages():
    """Pages of the Facebook account that just logged in, marked when already connected."""
    _require_access()
    login = _login()
    try:
        found = list_pages(requests, login["token"])
    except GraphError as err:
        frappe.throw(f"Facebook từ chối: {err}")
    return {"account_name": login.get("account_name") or "", "pages": page_choices(found, _connections())}


def _store_crm_page(page, account_id):
    """The page (with its token) and its Lead Ads forms in the CRM's own lead_syncing doctypes.
    Returns the number of forms; 0 when Facebook refuses them (no leads_retrieval permission)."""
    from crm.lead_syncing.doctype.lead_sync_source.facebook import fetch_and_store_leadgen_forms_from_facebook

    values = {"page_name": page.get("name"), "category": page.get("category") or "",
              "access_token": page["access_token"], "account_id": account_id or ""}
    if frappe.db.exists("Facebook Page", page["id"]):
        frappe.db.set_value("Facebook Page", page["id"], values)
    else:
        frappe.get_doc({"doctype": "Facebook Page", "id": page["id"], **values}).insert(ignore_permissions=True)
    try:
        return len(fetch_and_store_leadgen_forms_from_facebook(page["id"], page["access_token"]))
    except Exception:
        frappe.log_error(title=f"Facebook Lead Ads forms of page {page['id']}")
        return 0


def _save_connection(page, branch, inbox_id, forms):
    name = frappe.db.get_value("Channel Connection", {"provider": PROVIDER, "external_id": page["id"]})
    doc = frappe.get_doc("Channel Connection", name) if name else frappe.new_doc("Channel Connection")
    doc.update({"provider": PROVIDER, "external_id": page["id"], "display_name": page.get("name"),
                "picture": ((page.get("picture") or {}).get("data") or {}).get("url") or "",
                "status": "Connected", "branch": branch or None, "chatwoot_inbox_id": inbox_id, "lead_forms": forms,
                "connected_by": frappe.session.user, "connected_at": frappe.utils.now_datetime(),
                "last_checked_at": frappe.utils.now_datetime(), "last_error": ""})
    if name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    return doc.name


@whitelist(methods=["POST"])
def connect(pages=None):
    """Connect the chosen pages: [{id, branch}]. Each page is done on its own; one failure does not stop the rest."""
    _require_access()
    from mmm_custom.staff_sync import admin_client, enqueue_sync

    login = _login()
    client = admin_client()
    if not client:
        frappe.throw("Chưa cấu hình Chatwoot (chatwoot_api_token): chạy scripts/configure-chatwoot.py.")
    try:
        found = {str(p["id"]): p for p in list_pages(requests, login["token"])}
    except GraphError as err:
        frappe.throw(f"Facebook từ chối: {err}")
    try:
        chosen = clean_selection(pages, found, set(frappe.get_all("CRM Territory", pluck="name")))
    except ValueError as error:
        frappe.throw(str(error))
    results = []
    for item in chosen:
        page = found[item["id"]]
        try:
            inbox = client.connect_facebook_page(page["id"], page["access_token"], login["token"], page.get("name"))
            forms = _store_crm_page(page, login.get("account_id"))
            _save_connection(page, item["branch"], inbox.get("id"), forms)
            frappe.db.commit()
            results.append({"id": page["id"], "name": page.get("name"), "ok": True, "inbox_id": inbox.get("id"),
                            "lead_forms": forms})
        except Exception as error:
            frappe.db.rollback()
            frappe.log_error(title=f"Connect Facebook page {page['id']}")
            results.append({"id": page["id"], "name": page.get("name"), "ok": False, "error": str(error)[:300]})
    enqueue_sync()  # the bot and the branch staff join the new inboxes
    return results


@whitelist(methods=["POST"])
def disconnect(name):
    """Stop receiving the page's messages. Its Chatwoot inbox and conversations stay; connecting it again resumes."""
    _require_access()
    from mmm_custom.staff_sync import admin_client

    doc = frappe.get_doc("Channel Connection", name)
    client = admin_client()
    if client:
        try:
            client.disconnect_facebook_page(doc.external_id)
        except Exception as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status != 404:  # a page Chatwoot never had is already disconnected
                frappe.throw(f"Chatwoot từ chối: {error}")
    doc.status = "Disconnected"
    doc.last_error = ""
    doc.save(ignore_permissions=True)
    return doc.status


def _local_time(timestamp):
    utc = datetime.fromtimestamp(timestamp, timezone.utc)
    return frappe.utils.convert_utc_to_system_timezone(utc).replace(tzinfo=None)


def check_health():
    """Daily: ask Facebook whether each connected page's token still works."""
    try:
        app_id, secret = app_credentials(frappe.conf)
    except ValueError:
        return 0
    rows = frappe.get_all("Channel Connection", filters={"provider": PROVIDER, "status": ["!=", "Disconnected"]},
                          fields=["name", "external_id"])
    for row in rows:
        token = frappe.db.get_value("Facebook Page", row.external_id, "access_token")
        try:
            if not token:
                raise GraphError("CRM không còn token của page này, kết nối lại.")
            debug = graph_get(requests, "debug_token", {"input_token": token,
                                                        "access_token": f"{app_id}|{secret}"}).get("data") or {}
            status, error, expires = health(debug, time.time())
        except GraphError as err:
            status, error, expires = "Error", str(err), None
        except Exception as err:  # network: keep the last known status
            frappe.db.set_value("Channel Connection", row.name, "last_error", str(err)[:300], update_modified=False)
            continue
        frappe.db.set_value("Channel Connection", row.name, {
            "status": status, "last_error": error, "last_checked_at": frappe.utils.now_datetime(),
            "token_expires_at": _local_time(expires) if expires else None,
        }, update_modified=False)
    frappe.db.commit()
    return len(rows)


@whitelist(methods=["POST"])
def check_now():
    _require_access()
    return check_health()
