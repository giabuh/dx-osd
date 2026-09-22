# Facebook Integration Platform — Spec

## Goal
Kết nối 3 hệ thống độc lập tại `/home/giabao/dev/MMM` (Chatwoot, Frappe CRM, n8n) thành một nền tảng chuyển đổi số cho doanh nghiệp SMB: nhận lead từ Facebook Lead Ads, nhận/trả lời tin nhắn Messenger/Instagram, hội tụ mọi lead/contact về một CRM duy nhất.

## Constraints
- KHÔNG gộp codebase. Không sửa code bên trong `chatwoot/` hoặc `crm/` (đây là clone của upstream `chatwoot/chatwoot` và `frappe/crm`, cần giữ khả năng `git pull` cập nhật).
- Tự host trên 1 VPS, dùng Docker Compose. Không cần multi-region/HA.
- Automation layer: **n8n** (đã chốt, không dùng Activepieces).
- Ngoài phạm vi: Airbyte, `messenger-platform-samples` (chỉ code mẫu tham khảo), Meta Business SDK độc lập.

## Service boundaries
| Hệ thống | Vai trò | Source of truth? |
|---|---|---|
| Frappe CRM (`crm/`) | Lead/Contact/Deal/pipeline | **Có** — duy nhất |
| Chatwoot (`chatwoot/`) | Inbox tương tác Messenger/Instagram | Không — chỉ bản sao nhẹ để chat |
| n8n | Glue: webhook → REST API, dedup, mapping | Không — stateless pipe |

## Flow A — Facebook Lead Ads (đã có sẵn, không cần build)
Facebook Lead Ads form → Frappe CRM tự poll qua `crm/lead_syncing/doctype/lead_sync_source/facebook.py` (Graph API `v23.0`, dedup theo `facebook_lead_id`). Chỉ cần cấu hình Facebook Page/App/Form trong CRM UI (Phase 0 + Phase 3 của plan).

## Flow B — Messenger/Instagram → CRM (cần build)
1. Khách nhắn tin → Chatwoot nhận qua channel Facebook/Instagram có sẵn (`app/models/channel/facebook_page.rb`, `app/services/instagram/*`).
2. Khi có event `conversation_created` (hoặc `contact_created`), Chatwoot bắn webhook, ký HMAC-SHA256 qua `app/models/concerns/webhook_secretable.rb` (header `X-Chatwoot-Signature` — verify bằng `signing_secret` cấu hình khi tạo Webhook trong Chatwoot UI).
3. n8n nhận webhook, verify signature.
4. Nếu contact Chatwoot đã có `custom_attributes.crm_lead_id` → chỉ gọi CRM REST API tạo Activity/Note vào Lead đó.
5. Nếu chưa có → tìm Lead trùng theo email/phone trong CRM (pattern giống `validate_duplicate_lead` trong `facebook.py`); nếu không trùng, tạo `CRM Lead` mới với `source="Messenger"` hoặc `"Instagram"`, field `chatwoot_contact_id` = Chatwoot contact id.
6. Ghi ngược `crm_lead_id` vào Chatwoot contact qua Chatwoot API (`PUT /api/v1/accounts/{account_id}/contacts/{id}`, field `custom_attributes`).

## Data model bổ sung
- **Chatwoot Contact.custom_attributes.crm_lead_id** — không cần schema change, `custom_attributes` là JSON field có sẵn.
- **CRM Lead.chatwoot_contact_id** — Custom Field mới (Data, unique), thêm qua app Frappe riêng `mmm_custom` (không sửa app `crm`).

## Deployment
Docker Compose trên 1 VPS, 3 project riêng (mỗi project giữ nguyên `docker-compose.yml`/`docker-compose.production.yaml` gốc của từng repo, chỉ thêm `docker-compose.override.yml` để bind port vào `127.0.0.1` và thêm volume cần thiết), cộng 1 project Caddy (`network_mode: host`) làm reverse proxy TLS cho 3 subdomain, trỏ vào `127.0.0.1:<port>` của từng service. Domain ví dụ dùng trong plan: `chat.example.com` (Chatwoot, port 3000), `crm.example.com` (Frappe CRM, port 8000), `n8n.example.com` (n8n, port 5678) — thay bằng domain thật khi triển khai.

## Rủi ro đã biết
- **Dedup 2 nguồn**: 1 khách vừa điền Lead Ads form vừa nhắn Messenger → xử lý ở bước 5 của Flow B bằng cách search email/phone trước khi tạo Lead mới.
- **Bảo mật webhook**: verify HMAC signature ở n8n; gọi Frappe REST API bằng API key/secret (không dùng session cookie).
- **Rate limit Meta Graph API**: `fetch_leads()` trong `facebook.py` có `# TODO: pagination` với `limit: 100000` — nợ kỹ thuật sẵn có từ upstream, chỉ cần biết trước, không cần sửa.
- **`crm/docker/docker-compose.yml` là dev/quickstart, không persist bench**: không có named volume cho `/home/frappe/frappe-bench` → mất state khi container bị xoá. Phase 2 phải thêm volume này trước khi làm bất cứ gì khác trên CRM.
