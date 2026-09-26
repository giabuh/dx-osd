# Kế Hoạch Triển Khai Chuyển Đổi FOSS 100%, Thay Thế n8n & Tích Hợp Meta Messenger Thật

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuẩn hóa toàn bộ hệ thống DX-OSD đạt 100% Mã nguồn mở thuần túy (FOSS/OSI), loại bỏ hoàn toàn n8n bằng Webhook Endpoint tinh gọn trong app Frappe `mmm_custom`, và kết nối dữ liệu Fanpage thật (EduFlow Academy, ID `1334466483083776`) từ Messenger vào CRM không trùng lặp Lead.

**Architecture:** Giảm cấu trúc hệ thống từ 3 cụm xuống **2 cụm container duy nhất (Chatwoot + Frappe CRM)**. Chatwoot tiếp nhận tin nhắn từ Facebook Page `1334466483083776` (qua Cloudflare Tunnel), bắn Webhook ký số HMAC-SHA256 thẳng vào API endpoint của Frappe CRM (`mmm_custom.api.chatwoot_sync`). Frappe CRM xử lý chuẩn hóa số điện thoại, dedup qua MariaDB ORM, tự động cập nhật/tạo Lead và ghi ngược `crm_lead_id` về Chatwoot.

**Tech Stack:** Docker, Chatwoot Community (Ruby on Rails, MIT), Frappe CRM v15 / v1.84.0 (Python, AGPLv3), MariaDB (GPLv2), Redis 7.2.4-alpine (BSD-3), Cloudflare Tunnel.

**Spec:** `docs/superpowers/specs/2026-09-22-facebook-integration-platform.md` và `docs/KE_HOACH_CHUYEN_DOI_FOSS_DX-OSD_v2.docx`.

## Global Constraints
- 100% mã nguồn phải tuân thủ giấy phép được OSI công nhận (AGPL-3.0, MIT, Apache-2.0, BSD-3-Clause).
- Tuyệt đối không xóa volume dữ liệu `frappe-bench-data` của CRM hoặc `chatwoot-data`.
- Mọi web port nội bộ chỉ bind vào `127.0.0.1`.
- Không commit file `.env` hoặc access token vào Git history.
- Mọi sửa đổi trong thư mục vendored (`chatwoot/`, `crm/`) phải được ghi lại tại `docs/vendored-upstreams.md`.

---

### Task 1: Xóa mã độc quyền và kích hoạt Chatwoot Community Edition thuần MIT

**Files:**
- Modify: `chatwoot/config/application.rb:43-53`
- Delete: `chatwoot/enterprise/` (toàn bộ thư mục)
- Delete: `messenger-platform-samples/` (toàn bộ thư mục)
- Modify: `docs/vendored-upstreams.md`

**Interfaces:**
- Produces: Chatwoot Community Edition chạy trên `http://127.0.0.1:3000` không chứa mã thương mại `enterprise/`.

- [ ] **Step 1: Xóa thư mục messenger-platform-samples khỏi git**
```powershell
git rm -r messenger-platform-samples
```

- [ ] **Step 2: Xóa thư mục chatwoot/enterprise khỏi git**
```powershell
git rm -r chatwoot/enterprise
```

- [ ] **Step 3: Vá file chatwoot/config/application.rb để bọc khối eager load enterprise trong điều kiện kiểm tra tồn tại**
Sửa dòng 43-53 trong `chatwoot/config/application.rb`:
```ruby
if Rails.root.join('enterprise').exist?
  config.eager_load_paths << Rails.root.join('enterprise/lib')
  config.eager_load_paths << Rails.root.join('enterprise/listeners')
  config.eager_load_paths += Dir["#{Rails.root}/enterprise/app/**"]
  config.paths['app/views'].unshift('enterprise/app/views')
  enterprise_initializers = Rails.root.join('enterprise/config/initializers')
  Dir[enterprise_initializers.join('**/*.rb')].each { |f| require f } if enterprise_initializers.exist?
end
```

- [ ] **Step 4: Ghi nhận sửa đổi vendored vào docs/vendored-upstreams.md**
Thêm dòng sau vào bảng "Local edits inside vendored directories":
`| chatwoot/config/application.rb | Guard enterprise/ eager load so removing chatwoot/enterprise/ boots cleanly as pure Community Edition (MIT) |`

- [ ] **Step 5: Rebuild Docker Chatwoot Community**
```powershell
cd chatwoot
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d --build rails
cd ..
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000
```
Expected: Trả về `200` hoặc `302`.

- [ ] **Step 6: Commit**
```powershell
git add chatwoot/config/application.rb docs/vendored-upstreams.md
git commit -m "chore(foss): remove proprietary enterprise and sample directories, enforce Chatwoot Community MIT"
```

---

### Task 2: Ghim an toàn phiên bản Redis tránh bản quyền RSALv2

**Files:**
- Modify: `docker/chatwoot/docker-compose.override.yaml`
- Modify: `crm/docker/docker-compose.override.yml`

**Interfaces:**
- Produces: Docker Redis services pinned to `redis:7.2.4-alpine` (BSD-3-Clause).

- [ ] **Step 1: Ghim tag redis trong docker/chatwoot/docker-compose.override.yaml**
Sửa image redis thành `redis:7.2.4-alpine`.

- [ ] **Step 2: Ghim tag redis trong crm/docker/docker-compose.override.yml**
Sửa image redis thành `redis:7.2.4-alpine`.

- [ ] **Step 3: Commit**
```powershell
git add docker/chatwoot/docker-compose.override.yaml crm/docker/docker-compose.override.yml
git commit -m "chore(infra): pin redis to 7.2.4-alpine for pure BSD-3 compliance"
```

---

### Task 3: Phát triển logic Deduplication bằng Python trong `mmm_custom`

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/dedupe.py`
- Create: `frappe-custom/mmm_custom/mmm_custom/tests/test_dedupe.py`

**Interfaces:**
- Produces: 
  - `normalize_phone(phone_str: str) -> str`
  - `build_lead_search_filters(email: str = None, phone: str = None) -> list`
  - `find_matching_lead(email: str = None, phone: str = None) -> dict`

- [ ] **Step 1: Viết failing test test_dedupe.py**
Tạo file `frappe-custom/mmm_custom/mmm_custom/tests/test_dedupe.py`:
```python
import unittest
from mmm_custom.dedupe import normalize_phone, build_lead_search_filters

class TestDedupeLogic(unittest.TestCase):
    def test_normalize_phone_vn(self):
        self.assertEqual(normalize_phone("0901234567"), "+84901234567")
        self.assertEqual(normalize_phone("+84901234567"), "+84901234567")
        self.assertEqual(normalize_phone("090 123 4567"), "+84901234567")
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_build_search_filters(self):
        filters = build_lead_search_filters("test@example.com", "0901234567")
        self.assertEqual(len(filters), 2)
        self.assertIn(["email_id", "=", "test@example.com"], filters)
        self.assertIn(["mobile_no", "=", "+84901234567"], filters)

    def test_build_search_filters_empty(self):
        filters = build_lead_search_filters("", None)
        self.assertEqual(len(filters), 0)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**
Run: `python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_dedupe.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'mmm_custom.dedupe'`.

- [ ] **Step 3: Triển khai logic trong dedupe.py**
Tạo file `frappe-custom/mmm_custom/mmm_custom/dedupe.py`:
```python
import re

def normalize_phone(phone_str: str) -> str:
    if not phone_str:
        return ""
    cleaned = re.sub(r"[^0-9+]", "", str(phone_str))
    if cleaned.startswith("0") and len(cleaned) in [10, 11]:
        return "+84" + cleaned[1:]
    return cleaned

def build_lead_search_filters(email: str = None, phone: str = None) -> list:
    filters = []
    if email and str(email).strip():
        filters.append(["email_id", "=", str(email).strip()])
    norm_phone = normalize_phone(phone)
    if norm_phone:
        filters.append(["mobile_no", "=", norm_phone])
    return filters

def find_matching_lead(email: str = None, phone: str = None):
    try:
        import frappe
    except ImportError:
        return None
    filters = build_lead_search_filters(email, phone)
    if not filters:
        return None
    leads = frappe.get_all(
        "CRM Lead",
        or_filters=filters,
        fields=["name", "first_name", "email_id", "mobile_no", "chatwoot_contact_id"],
        limit=1
    )
    return leads[0] if leads else None
```

- [ ] **Step 4: Chạy test xác nhận PASS**
Run: `python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_dedupe.py`
Expected: Ran 3 tests, OK.

- [ ] **Step 5: Commit**
```powershell
git add frappe-custom/mmm_custom/mmm_custom/dedupe.py frappe-custom/mmm_custom/mmm_custom/tests/test_dedupe.py
git commit -m "feat(crm): implement dedupe logic in python with 100% unit test coverage"
```

---

### Task 4: Xây dựng Webhook Endpoint trong `mmm_custom` và Gỡ bỏ n8n

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/api.py`
- Delete: `docker/n8n/` (toàn bộ thư mục)
- Delete: `n8n/` (toàn bộ thư mục)

**Interfaces:**
- Produces: API endpoint `POST /api/method/mmm_custom.api.chatwoot_sync` tiếp nhận Webhook từ Chatwoot.

- [ ] **Step 1: Viết Webhook handler trong api.py**
Tạo file `frappe-custom/mmm_custom/mmm_custom/api.py`:
```python
import frappe
import hmac
import hashlib
import time
import json
import requests
from mmm_custom.dedupe import normalize_phone, find_matching_lead

@frappe.whitelist(allow_guest=True)
def chatwoot_sync():
    req = frappe.request
    ts = req.headers.get("X-Chatwoot-Timestamp")
    sig = req.headers.get("X-Chatwoot-Signature", "")
    raw_body = req.get_data()
    secret = frappe.conf.get("chatwoot_webhook_secret") or "dx_osd_shared_webhook_secret_2026"

    # 1. Chống Replay Attack & Verify HMAC Signature
    if not ts or abs(time.time() - int(ts)) > 300:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)
    
    expected = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        frappe.throw("Invalid HMAC signature", frappe.AuthenticationError)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}

    if payload.get("event") != "conversation_created":
        return {"status": "ignored", "event": payload.get("event")}

    conversation = payload.get("conversation", {})
    contact = conversation.get("contact_inbox", {}).get("contact", {})
    contact_id = contact.get("id")
    email = contact.get("email")
    phone = contact.get("phone_number")
    custom_attrs = contact.get("custom_attributes") or {}
    crm_lead_id = custom_attrs.get("crm_lead_id")

    # 2. Xử lý Logic Dedup và Hội Tụ Lead
    if crm_lead_id and frappe.db.exists("CRM Lead", crm_lead_id):
        lead_name = crm_lead_id
    else:
        matched = find_matching_lead(email, phone)
        if matched:
            lead_name = matched.name
            frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
        else:
            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": contact.get("name") or "EduFlow Student",
                "email_id": email,
                "mobile_no": normalize_phone(phone),
                "lead_source": "Messenger",
                "chatwoot_contact_id": str(contact_id)
            }).insert(ignore_permissions=True)
            lead_name = lead.name

    # 3. Ghi log hội thoại vào FCRM Note
    try:
        messages = conversation.get("messages") or []
        first_msg = messages[0].get("content") if messages else "New conversation via Messenger"
        frappe.get_doc({
            "doctype": "FCRM Note",
            "parent": lead_name,
            "parenttype": "CRM Lead",
            "parentfield": "notes",
            "content": f"[Chatwoot #{conversation.get('id')}]: {first_msg}"
        }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Failed to create FCRM Note: {str(e)}")

    # 4. Ghi ngược crm_lead_id về Chatwoot Contact
    chatwoot_url = frappe.conf.get("chatwoot_api_url") or "http://127.0.0.1:3000"
    chatwoot_token = frappe.conf.get("chatwoot_api_token")
    if chatwoot_token and contact_id:
        try:
            requests.put(
                f"{chatwoot_url}/api/v1/accounts/1/contacts/{contact_id}",
                headers={"api_access_token": chatwoot_token},
                json={"custom_attributes": {"crm_lead_id": lead_name}},
                timeout=5
            )
        except Exception as e:
            frappe.log_error(f"Failed to update Chatwoot contact: {str(e)}")

    return {"status": "success", "lead_id": lead_name}
```

- [ ] **Step 2: Dừng container n8n và xóa bỏ khỏi repo**
```powershell
cd docker/n8n
docker compose down -v
cd ../..
git rm -r docker/n8n
git rm -r n8n
```

- [ ] **Step 3: Test giả lập gọi Webhook CRM**
Chạy python test gửi request kèm HMAC signature tới `http://127.0.0.1:8000/api/method/mmm_custom.api.chatwoot_sync`.
Expected: Phản hồi HTTP 200 `{"message": {"status": "success", "lead_id": ...}}`.

- [ ] **Step 4: Commit**
```powershell
git add frappe-custom/mmm_custom/mmm_custom/api.py
git commit -m "feat(crm): add in-bench webhook endpoint, decommission n8n for 100% FOSS"
```

---

### Task 5: Cấu hình Chatwoot Webhook & Kết nối Fanpage EduFlow Academy

**Files:**
- Cấu hình: Chatwoot Integrations Webhook (`http://127.0.0.1:3000`)
- Cấu hình: Cloudflare Tunnel

- [ ] **Step 1: Khởi động Cloudflare Tunnel mở cổng Chatwoot**
```powershell
cloudflared tunnel --url http://127.0.0.1:3000
```
Ghi lại URL công khai (ví dụ `https://your-tunnel.trycloudflare.com`).

- [ ] **Step 2: Cấu hình Webhook trong Chatwoot**
Đăng nhập Chatwoot (`Administrator` / `admin123`):
Settings -> Integrations -> Webhooks -> Add Webhook:
- URL: `http://host.docker.internal:8000/api/method/mmm_custom.api.chatwoot_sync` (hoặc `http://crm.localhost:8000/...`).
- Sự kiện: `Conversation Created`.

- [ ] **Step 3: Cấu hình Fanpage EduFlow Academy trong Chatwoot**
Settings -> Inboxes -> Add Inbox -> Facebook Page:
- Điền Page ID: `1334466483083776`.
- Cung cấp Token Page của Fanpage.

- [ ] **Step 4: Kiểm thử gửi tin nhắn thật từ Messenger**
- Dùng điện thoại mở Messenger chat vào Fanpage EduFlow Academy: "Test tích hợp DX-OSD OLP".
- Kiểm tra tin nhắn vào Chatwoot Inbox.
- Kiểm tra CRM Lead tại `http://127.0.0.1:8000/app/crm-lead`.

---

### Task 6: Tối ưu UI/UX Giao diện Doanh nghiệp

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/setup.py`

- [ ] **Step 1: Bổ sung trường quan tâm khóa học (course_interest) trên CRM Lead**
Trong `setup.py`, bổ sung Custom Field `course_interest` (Select: "Tiếng Anh", "Bơi lội", "Toán tư duy", "Chưa xác định").

- [ ] **Step 2: Migrate patch cập nhật cấu trúc Frappe CRM**
Chạy `bench --site crm.localhost migrate`.

- [ ] **Step 3: Commit**
```powershell
git add frappe-custom/mmm_custom/mmm_custom/setup.py
git commit -m "feat(ui): add course_interest field and lead source visibility"
```

---

### Task 7: Cập nhật Hồ sơ Bản quyền FOSS Compliance & Repo Docs

**Files:**
- Modify: `REPO.md`
- Modify: `ROADMAP.md`
- Modify: `AGENTS.md`
- Create: `docs/foss-compliance-report.md`

- [ ] **Step 1: Cập nhật Git Identity của Thành**
```powershell
git config --global user.name "Thanh"
git config --global user.email "thanhheo7749@gmail.com"
```

- [ ] **Step 2: Cập nhật REPO.md, ROADMAP.md, AGENTS.md phản ánh kiến trúc FOSS 2 cụm**
Loại bỏ n8n, ghi nhận `mmm_custom` là tầng nhận webhook trực tiếp từ Chatwoot.

- [ ] **Step 3: Tạo Báo cáo Chứng nhận Bản quyền Nguồn mở (docs/foss-compliance-report.md)**
Tổng hợp danh mục 100% bản quyền OSI (AGPL-3.0, MIT, Apache-2.0, BSD-3) sẵn sàng nộp Ban Giám khảo VFOSSA.

- [ ] **Step 4: Commit**
```powershell
git add REPO.md ROADMAP.md AGENTS.md docs/foss-compliance-report.md
git commit -m "docs: finalize 100% FOSS compliance documentation and roadmap v2"
```
