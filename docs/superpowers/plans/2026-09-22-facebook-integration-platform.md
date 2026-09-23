# Facebook Integration Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nối 3 hệ thống độc lập (Chatwoot, Frappe CRM, n8n) tại `/home/giabao/dev/dx-osd` thành một nền tảng nhận lead Facebook Lead Ads + tin nhắn Messenger/Instagram, hội tụ về Frappe CRM.

**Architecture:** Frappe CRM là source of truth (đã tự poll Facebook Lead Ads sẵn). Chatwoot là inbox-only cho Messenger/Instagram. n8n là glue layer: nhận webhook ký HMAC từ Chatwoot, dedup theo email/phone, gọi REST API Frappe CRM để tạo/cập nhật Lead, ghi ngược `crm_lead_id` vào Chatwoot contact. Cả 3 hệ thống deploy bằng Docker Compose riêng biệt trên 1 VPS, Caddy làm reverse proxy TLS dùng `network_mode: host`.

**Tech Stack:** Docker Compose, Chatwoot (Rails, có sẵn), Frappe CRM (Python/bench, có sẵn), n8n (self-host), Node.js (`node:test` cho unit test logic dedup/mapping), Caddy (reverse proxy).

**Spec:** `docs/superpowers/specs/2026-09-22-facebook-integration-platform.md`

## Global Constraints
- ~~Không sửa code trong `chatwoot/` hoặc `crm/`~~ — **superseded** by `3a0e4ef`: both are now vendored source in this repo. Prefer extension points; edits inside them are allowed but must be recorded in `docs/vendored-upstreams.md`.
- Mọi web port của 3 stack chỉ bind vào `127.0.0.1` trên host — Caddy là điểm vào duy nhất từ Internet.
- Automation layer cố định là **n8n** — không cài Activepieces.
- Domain ví dụ trong plan: `chat.example.com`, `crm.example.com`, `n8n.example.com` — thay bằng domain thật của bạn ở Task 3 trước khi chạy Caddy thật (DNS A record phải trỏ đúng VPS trước khi Caddy tự xin Let's Encrypt).

---

## Execution Status (as of 2026-09-22)

Tracked here instead of only in the (gitignored) SDD ledger so this survives outside any one working tree. See `git log` for full detail on every commit named below.

| Task | Status |
|---|---|
| 0 — Facebook App | **Not started.** Manual, external to any dev environment — needs a human with Meta Business Manager access. |
| 1 — Init repo, clone vendored dirs | **Done.** |
| 2 — Deploy Chatwoot | **Done.** Runs, verified `200`/`302`. |
| 3 — Deploy Frappe CRM | **Done.** Fixed 2 real bugs in this task's own override YAML (missing `!override` on `ports:`; DNS retry window too short) — commit `33a40ef`. |
| 4 — Deploy n8n | **Done.** |
| 5 — Caddy reverse proxy | **Files only, not run.** Needs a real DNS domain pointed at a real VPS (Global Constraints) — this dev environment has neither. Fixed a Host-header bug for the CRM proxy block — commit `5f54914`. |
| 6 — CRM custom field `chatwoot_contact_id` | **Done.** Also wired into `after_install`/a migrate patch and seeded `Messenger`/`Instagram` `CRM Lead Source` records, both found missing by review — commit `c371a31`. |
| 7 — Frappe API key for n8n | **Done** (headlessly, not via UI). |
| 8 — dedupe.js unit tests | **Done.** Filter/first_name bugs found by review, fixed with new failing-then-passing tests — commit `fb34bb9`. |
| 9 — n8n workflow | **Done, and actually verified end-to-end** (not just built) — commits `aeed8bf`, `b78d4e3`, `38bade4`, `8292d22`, `01ab548`. The first pass had 6 real defects (signature format, payload shape, CRM schema, wrong doctype, dedup filter, PATCH-vs-PUT) — the first 5 found by a fresh-context review of the diff and confirmed against the vendored `chatwoot/`/`crm/` source; the 6th found by testing the exact Facebook-Lead-Ads-then-Messenger convergence scenario the project exists for. All fixed and re-verified against the real running stacks, including that convergence scenario (1 Lead, correctly matched and updated, not duplicated). |
| 10 — End-to-end test | **Step 1 done** (wrong signature correctly rejected). **Steps 2-5 blocked** — need a real Chatwoot→n8n webhook delivery, which needs Task 5 live. The equivalent logic was exercised directly instead (see Task 9's note) as the best available substitute in this environment. |
| 11 — Security checklist | **Done.** All 3 steps pass; no real secret anywhere in git history (checked past the plan's own grep, including a full-history high-entropy scan). |

---

## Phase 0: Meta App & Business Manager Setup

### Task 0: Tạo Facebook App và lấy quyền cần thiết

**Files:** Không có file code — task cấu hình thủ công trên Meta for Developers.

**Interfaces:**
- Produces: 1 Facebook App ID + App Secret, 1 Page Access Token dài hạn, quyền `pages_messaging`, `pages_show_list`, `pages_read_engagement`, `leads_retrieval` (và `instagram_basic`, `instagram_manage_messages` nếu dùng Instagram). Các giá trị này được Task 3 (Chatwoot) và Task 4 (CRM) tiêu thụ khi cấu hình channel/lead source.

- [ ] **Step 1: Tạo App**

Vào https://developers.facebook.com/apps → Create App → loại "Business" → gắn vào Business Manager của doanh nghiệp. Ghi lại **App ID** và **App Secret** (Settings → Basic).

- [ ] **Step 2: Kết nối Page và xin quyền**

Trong App → Add Product → "Facebook Login for Business" (để lấy Page Access Token) và "Webhooks". Xin các quyền: `pages_messaging`, `pages_show_list`, `pages_read_engagement`, `leads_retrieval`. Nếu dùng Instagram DM: thêm `instagram_basic`, `instagram_manage_messages`.

- [ ] **Step 3: Lấy Page Access Token dài hạn**

Dùng Graph API Explorer hoặc endpoint `oauth/access_token` để đổi short-lived token sang long-lived Page token (không hết hạn khi Page không đổi admin).

- [ ] **Step 4: Verify — gọi thử Graph API bằng token vừa lấy**

Run:
```bash
curl -s "https://graph.facebook.com/v23.0/me?fields=id,name&access_token=<PAGE_ACCESS_TOKEN>"
```
Expected: JSON trả về đúng `id` và `name` của Page (không phải lỗi `OAuthException`). Lưu token này vào password manager — Task 3 và Task 4 cần dùng lại.

- [ ] **Step 5: Ghi chú trạng thái App Review**

Nếu App và Page cùng một Business Manager sở hữu, `leads_retrieval` thường dùng được ở Standard Access không cần App Review. Nếu Graph API trả lỗi `permissions error` khi Task 4 thử fetch leads thật, quay lại đây nộp App Review trước khi tiếp tục Phase 3/4.

---

## Phase 1: Bootstrap integration repo

### Task 1: Init git repo, ignore vendored clones

> **Superseded (2026-09-22, `3a0e4ef`):** `chatwoot/`, `crm/`, `messenger-platform-samples/` are no longer ignored clones — they are vendored and tracked. Kept below as the original execution record.

**Files:**
- Create: `/home/giabao/dev/dx-osd/.gitignore`

**Interfaces:**
- Produces: git repo tại `/home/giabao/dev/dx-osd` chứa mọi file glue (`docker/`, `frappe-custom/`, `n8n/`, `docs/`), không track `chatwoot/`, `crm/`, `messenger-platform-samples/` (mỗi thư mục này đã là git repo riêng trỏ upstream — xác nhận qua `git -C chatwoot remote -v`).

- [ ] **Step 1: Viết .gitignore**

```
chatwoot/
crm/
messenger-platform-samples/
docker/**/.env
n8n/.n8n/
```

- [ ] **Step 2: Init repo và commit**

Run:
```bash
cd /home/giabao/dev/dx-osd
git init
git add .gitignore docs/superpowers/specs/2026-09-22-facebook-integration-platform.md docs/superpowers/plans/2026-09-22-facebook-integration-platform.md
git commit -m "chore: init integration repo with spec and plan"
```

- [ ] **Step 3: Verify**

Run: `git status --ignored --short`
Expected: `chatwoot/`, `crm/`, `messenger-platform-samples/` xuất hiện dưới mục `Ignored files`; `git log --oneline -1` trả về đúng 1 commit vừa tạo.

---

## Phase 2: Deploy 3 stack qua Docker Compose

### Task 2: Deploy Chatwoot (dùng compose có sẵn của repo)

**Files:**
- Create: `chatwoot/.env` (copy từ `chatwoot/.env.example`, không tạo file mới ngoài `chatwoot/`)
- Create: `docker/chatwoot/docker-compose.override.yaml` (fix 2 lỗi trong `chatwoot/docker-compose.production.yaml` phát hiện khi chạy thật — xem Step 3)

**Interfaces:**
- Consumes: không có
- Produces: Chatwoot rails container lắng nghe `127.0.0.1:3000` (đã có sẵn trong `chatwoot/docker-compose.production.yaml`) — Task 5 (Caddy) sẽ trỏ vào port này.

- [ ] **Step 1: Tạo .env từ template**

Run:
```bash
cd /home/giabao/dev/dx-osd/chatwoot
cp .env.example .env
```

- [ ] **Step 2: Điền secret bắt buộc**

Sửa `chatwoot/.env`:
```
SECRET_KEY_BASE=<output của: openssl rand -hex 64>
POSTGRES_PASSWORD=<output của: openssl rand -hex 24>
REDIS_PASSWORD=<output của: openssl rand -hex 24>
FRONTEND_URL=https://chat.example.com
RAILS_ENV=production
```

- [ ] **Step 3: Viết override cố định fix 2 lỗi phát hiện khi chạy thật**

`chatwoot/docker-compose.production.yaml` có 2 vấn đề không thể sửa trực tiếp (Global Constraint: không sửa code trong `chatwoot/`): (a) service `postgres` map cứng host port `127.0.0.1:5432:5432`, dễ đụng Postgres khác đã chạy sẵn trên host; (b) service `postgres` hard-code `POSTGRES_PASSWORD=` (rỗng) và không có `env_file`, nên giá trị đặt ở Step 2 không bao giờ tới được container `postgres` — nó crash-loop với lỗi "Database is uninitialized and superuser password is not specified". Viết `docker/chatwoot/docker-compose.override.yaml`:

```yaml
services:
  postgres:
    ports: !override
      - '127.0.0.1:15432:5432'
    environment: !override
      - POSTGRES_DB=chatwoot
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
```

(`!override` bắt buộc — merge mặc định của Compose NỐI THÊM vào list `ports`/`environment` thay vì thay thế, để lại mapping `5432` cũ gây xung đột port. `${POSTGRES_PASSWORD}` được Compose tự lấy từ `chatwoot/.env` vì đó là thư mục chứa file `-f` đầu tiên trong lệnh ở Step 4.)

- [ ] **Step 4: Chạy stack và chuẩn bị database**

Run:
```bash
cd /home/giabao/dev/dx-osd/chatwoot
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d postgres redis
sleep 5
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml run --rm rails bundle exec rails db:chatwoot_prepare
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d
```

- [ ] **Step 5: Verify**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000`
Expected: `200` (hoặc `302` redirect tới `/app/login` hoặc `/installation/onboarding` — cả 3 đều nghĩa là Rails đã lên). Nếu connection refused, chạy `docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml logs rails --tail 50` để xem lỗi thật, không đoán.

- [ ] **Step 6: Commit override file**

Run:
```bash
cd /home/giabao/dev/dx-osd
git add docker/chatwoot/docker-compose.override.yaml
git commit -m "fix(chatwoot): pin postgres host port and wire POSTGRES_PASSWORD via override"
```

### Task 3: Deploy Frappe CRM (fix persistence + dùng compose có sẵn)

**Files:**
- Create: `crm/docker/docker-compose.override.yml`

**Interfaces:**
- Consumes: không có
- Produces: Frappe container lắng nghe `127.0.0.1:8000`, site `crm.localhost`, admin password `admin` (từ `crm/docker/init.sh`) — Task 4 (custom field) và Task 5 (Caddy) dùng lại các giá trị này.

- [ ] **Step 1: Viết override — fix port binding, persist bench, fix DNS**

`crm/docker/init.sh` chỉ `bench init` một lần rồi bỏ qua nếu `apps/frappe` đã tồn tại, nhưng `crm/docker/docker-compose.yml` KHÔNG có volume cho `/home/frappe/frappe-bench` — nghĩa là mọi state (kể cả app custom sẽ thêm ở Phase 3) mất khi container bị xoá. Override này fix cả 2 vấn đề, cộng 2 lỗi khác phát hiện khi chạy thật (xem ledger `Task 3` cho bằng chứng đầy đủ):

- **Mount target phải là `/home/frappe` (cả home dir), không phải `/home/frappe/frappe-bench`**: mount 1 named volume thẳng vào `/home/frappe/frappe-bench` khiến Docker tự tạo sẵn thư mục đó làm mount point TRƯỚC KHI `init.sh` chạy dòng đầu tiên — với BẤT KỲ volume nào, kể cả rỗng. `bench init`'s check chỉ là `os.path.exists()` trần trụi (không phân biệt rỗng hay không), nên luôn báo "already exists" và no-op, làm mọi lệnh `bench` sau đó cascade lỗi. Mount cả `/home/frappe` thì Docker tự populate volume rỗng bằng nội dung sẵn có trong image (`.bench/`, `.local/`, ...) còn `frappe-bench/` (thứ mục thực sự không có sẵn trong image, chỉ được `bench init` tạo ra) vẫn đúng nghĩa "chưa tồn tại" ở lần chạy đầu.
- **Cần pin `dns: [8.8.8.8]` cho service `frappe`**: trên máy có Tailscale chạy, Docker daemon có thể gán nhầm `/etc/resolv.conf` của container mới tạo trỏ thẳng vào stub resolver của host (`127.0.0.53`, không dùng được từ network namespace của container) thay vì DNS nội bộ đúng của Docker — làm mọi lookup DNS ra ngoài (`bench get-app` cần GitHub, `uv venv` cần PyPI) fail với "Temporary failure in name resolution". `mariadb`/`redis` trong cùng file không bị (tự nhận đúng DNS nội bộ), chỉ `frappe` bị. (Đã thử pin `127.0.0.11` — DNS nội bộ của Docker — trước, nhưng giá trị đó tự forward-loop vào chính nó khi bị set tường minh qua `dns:`; `8.8.8.8` verify hoạt động đúng.)
- **Cần retry-wrapper chờ DNS sẵn sàng trước khi chạy `init.sh`**: kể cả với `dns: [8.8.8.8]` đúng, có hiện tượng chập chờn ở tầng Docker/host khiến DNS fail đúng trong vài giây đầu container mới start (0.3-10s, không tái hiện được khi test container riêng lẻ) — không sửa được bằng giá trị `dns:` tĩnh. Wrapper cho container tự đợi/thử lại tối đa 15s trước khi giao cho `init.sh` chạy thật, không đụng tới `init.sh` gốc (vẫn giữ nguyên qua `exec`).

```yaml
version: "3.7"
services:
  frappe:
    ports:
      - "127.0.0.1:8000:8000"
      - "127.0.0.1:9000:9000"
    dns:
      - 8.8.8.8
    command: >
      bash -c "for i in $(seq 1 15); do getent hosts pypi.org >/dev/null 2>&1 && break; echo 'Waiting for DNS...'; sleep 1; done; exec bash /workspace/init.sh"
    volumes:
      - .:/workspace
      - frappe-bench-data:/home/frappe

volumes:
  frappe-bench-data:
```

- [ ] **Step 2: Chạy stack**

Run:
```bash
cd /home/giabao/dev/dx-osd/crm/docker
docker compose up -d
```

(`docker compose` tự động nạp `docker-compose.yml` + `docker-compose.override.yml` cùng thư mục — không cần `-f` thứ hai.)

- [ ] **Step 3: Verify — chờ init.sh chạy xong rồi kiểm tra site**

Run:
```bash
timeout 300 bash -c 'until curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000 | grep -q 200; do sleep 5; done'
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000
```
Expected: `200`. Nếu timeout, chạy `docker compose logs frappe --tail 80` để xem `init.sh` dừng ở bước nào.

- [ ] **Step 4: Verify persistence thật sự hoạt động**

Run:
```bash
docker compose restart frappe
sleep 10
docker compose exec frappe test -d /home/frappe/frappe-bench/apps/crm && echo "PERSISTED"
```
Expected: in ra `PERSISTED` (không phải lỗi "no such file" — nếu lỗi nghĩa là volume chưa mount đúng, dừng lại sửa trước khi sang Task 4).

### Task 4: Deploy n8n

**Files:**
- Create: `docker/n8n/docker-compose.yml`
- Create: `docker/n8n/.env`

**Interfaces:**
- Consumes: không có
- Produces: n8n container lắng nghe `127.0.0.1:5678`, webhook base URL `https://n8n.example.com` — Phase 4 (workflow) và Task 5 (Caddy) dùng lại port + domain này.

- [ ] **Step 1: Viết docker-compose.yml**

```yaml
version: "3.7"
services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - n8n-postgres-data:/var/lib/postgresql/data

  n8n:
    image: n8nio/n8n:latest
    restart: always
    depends_on:
      - postgres
    ports:
      - "127.0.0.1:5678:5678"
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_DATABASE=n8n
      - DB_POSTGRESDB_USER=n8n
      - DB_POSTGRESDB_PASSWORD=${POSTGRES_PASSWORD}
      - N8N_HOST=n8n.example.com
      - N8N_PROTOCOL=https
      - N8N_PORT=5678
      - WEBHOOK_URL=https://n8n.example.com/
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
    volumes:
      - n8n-data:/home/node/.n8n

volumes:
  n8n-postgres-data:
  n8n-data:
```

- [ ] **Step 2: Tạo .env với secret**

Run:
```bash
cd /home/giabao/dev/dx-osd/docker/n8n
cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)
EOF
```

- [ ] **Step 3: Chạy stack**

Run: `docker compose up -d`

- [ ] **Step 4: Verify**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5678`
Expected: `200`.

- [ ] **Step 5: Commit**

Run:
```bash
cd /home/giabao/dev/dx-osd
git add docker/n8n/docker-compose.yml
git commit -m "feat(n8n): add n8n stack docker-compose config"
```
(`docker/n8n/.env` is gitignored via `docker/**/.env` from Task 1 — do not force-add it.)

### Task 5: Caddy reverse proxy (TLS cho cả 3 subdomain)

**Files:**
- Create: `docker/caddy/Caddyfile`
- Create: `docker/caddy/docker-compose.yml`

**Interfaces:**
- Consumes: port `127.0.0.1:3000` (Task 2), `127.0.0.1:8000` (Task 3), `127.0.0.1:5678` (Task 4)
- Produces: HTTPS endpoint công khai cho 3 domain — mọi task từ Phase 3 trở đi gọi API qua các domain này thay vì `127.0.0.1`.

- [ ] **Step 1: Viết Caddyfile**

```
chat.example.com {
    reverse_proxy 127.0.0.1:3000
}

crm.example.com {
    reverse_proxy 127.0.0.1:8000
}

n8n.example.com {
    reverse_proxy 127.0.0.1:5678
}
```

- [ ] **Step 2: Viết docker-compose.yml (network_mode: host để reach các port 127.0.0.1 của 3 stack khác)**

```yaml
version: "3.7"
services:
  caddy:
    image: caddy:2-alpine
    restart: always
    network_mode: host
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config

volumes:
  caddy-data:
  caddy-config:
```

- [ ] **Step 3: Trỏ DNS trước khi chạy**

Đảm bảo `chat.example.com`, `crm.example.com`, `n8n.example.com` (đổi thành domain thật) đã có A record trỏ về IP VPS — verify: `dig +short chat.example.com` phải trả về đúng IP VPS trước khi chạy Caddy, nếu không Let's Encrypt sẽ fail.

- [ ] **Step 4: Chạy và verify**

Run:
```bash
cd /home/giabao/dev/dx-osd/docker/caddy
docker compose up -d
sleep 15
curl -s -o /dev/null -w "%{http_code}\n" https://chat.example.com
curl -s -o /dev/null -w "%{http_code}\n" https://crm.example.com
curl -s -o /dev/null -w "%{http_code}\n" https://n8n.example.com
```
Expected: cả 3 lệnh trả `200`/`302` (không phải lỗi cert hoặc connection refused). Nếu cert lỗi, chạy `docker compose logs caddy --tail 50`.

---

## Phase 3: CRM custom field `chatwoot_contact_id`

### Task 6: Tạo Frappe app riêng chứa custom field (không sửa app `crm`)

**Files:**
- Create: `apps/mmm_custom/` bên trong container (sẽ copy ra host ở Step 3) → host path cuối cùng: `frappe-custom/mmm_custom/`
- Create: `frappe-custom/mmm_custom/mmm_custom/setup.py`

**Interfaces:**
- Produces: `CRM Lead.chatwoot_contact_id` (Data, unique) tồn tại trong Frappe CRM — Phase 4's n8n workflow set/query field này qua REST API `PUT/GET /api/resource/CRM Lead/{name}`.

- [ ] **Step 1: Tạo app trong container**

Run:
```bash
cd /home/giabao/dev/dx-osd/crm/docker
docker compose exec frappe bash -c "cd frappe-bench && bench new-app mmm_custom --title 'MMM Custom' --description 'Chatwoot-CRM integration custom fields' --publisher 'MMM' --email 'baoluu674@gmail.com' --license mit"
docker compose exec frappe bash -c "cd frappe-bench && bench --site crm.localhost install-app mmm_custom"
```
Nếu `bench new-app` từ chối flag nào đó (phiên bản bench khác), chạy lại không kèm flag — nó sẽ hỏi từng câu, trả lời tương ứng rồi tiếp tục.

- [ ] **Step 2: Copy app ra host để version control**

Run:
```bash
cd /home/giabao/dev/dx-osd/crm/docker
mkdir -p /home/giabao/dev/dx-osd/frappe-custom
docker compose cp frappe:/home/frappe/frappe-bench/apps/mmm_custom /home/giabao/dev/dx-osd/frappe-custom/mmm_custom
```

- [ ] **Step 3: Thêm bind mount để container đọc từ host từ giờ trở đi**

Sửa `crm/docker/docker-compose.override.yml` (đã tạo ở Task 3), thêm dòng volume mới vào service `frappe`:

```yaml
    volumes:
      - .:/workspace
      - frappe-bench-data:/home/frappe/frappe-bench
      - ../../frappe-custom/mmm_custom:/home/frappe/frappe-bench/apps/mmm_custom
```

Run:
```bash
cd /home/giabao/dev/dx-osd/crm/docker
docker compose up -d --force-recreate frappe
```

- [ ] **Step 4: Viết hàm tạo custom field**

Create `frappe-custom/mmm_custom/mmm_custom/setup.py`:

```python
import frappe


def create_custom_field():
	if frappe.db.exists("Custom Field", "CRM Lead-chatwoot_contact_id"):
		print("Custom field already exists, skipping")
		return

	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": "CRM Lead",
		"fieldname": "chatwoot_contact_id",
		"label": "Chatwoot Contact ID",
		"fieldtype": "Data",
		"unique": 1,
		"read_only": 0,
		"insert_after": "lead_name",
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print("Custom field created")
```

- [ ] **Step 5: Chạy hàm qua bench execute**

Run:
```bash
cd /home/giabao/dev/dx-osd/crm/docker
docker compose exec frappe bash -c "cd frappe-bench && bench --site crm.localhost execute mmm_custom.setup.create_custom_field"
```
Expected output: `Custom field created` (hoặc `Custom field already exists, skipping` nếu chạy lại lần 2 — idempotent).

- [ ] **Step 6: Verify field tồn tại qua REST API**

Run:
```bash
curl -s -u admin:admin "http://127.0.0.1:8000/api/resource/CRM Lead?fields=[\"name\",\"chatwoot_contact_id\"]&limit_page_length=1"
```
Expected: JSON response chứa key `chatwoot_contact_id` trong object trả về (không phải lỗi field không tồn tại).

- [ ] **Step 7: Commit vào git repo của mình**

Run:
```bash
cd /home/giabao/dev/dx-osd
git add frappe-custom/ crm/docker/docker-compose.override.yml
git commit -m "feat: add chatwoot_contact_id custom field to CRM Lead"
```

### Task 7: Tạo Frappe API key/secret cho n8n dùng

**Files:** Không có file code — thao tác qua CRM UI, lưu credential vào n8n ở Task 9.

- [ ] **Step 1: Tạo API key**

Vào `https://crm.example.com/app/user` → chọn user `Administrator` (hoặc tạo user riêng "n8n-integration" với role Sales Manager) → tab "API Access" → "Generate Keys". Lưu lại `api_key` và `api_secret`.

- [ ] **Step 2: Verify — gọi REST API bằng key vừa tạo**

Run:
```bash
curl -s -H "Authorization: token <api_key>:<api_secret>" "https://crm.example.com/api/resource/CRM Lead?limit_page_length=1"
```
Expected: JSON `{"data": [...]}, không phải `403`/`PermissionError`.

---

## Phase 4: n8n workflow — dedup logic + wiring

### Task 8: Viết và test logic dedup/mapping (TDD)

**Files:**
- Create: `n8n/logic/dedupe.js`
- Test: `n8n/logic/dedupe.test.js`

**Interfaces:**
- Produces: `normalizePhone(raw: string): string`, `buildLeadSearchFilters({email, phone}): object[]`, `buildNewLeadPayload({source, name, email, phone, chatwootContactId}): object` — Task 9's n8n Code node copy nguyên logic 3 hàm này vào node "Build Lead Payload".

- [ ] **Step 1: Viết failing test**

Create `n8n/logic/dedupe.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizePhone, buildLeadSearchFilters, buildNewLeadPayload } = require('./dedupe');

test('normalizePhone strips spaces, dashes, and adds +84 for local VN numbers', () => {
	assert.equal(normalizePhone('090 123 4567'), '+84901234567');
	assert.equal(normalizePhone('0901234567'), '+84901234567');
	assert.equal(normalizePhone('+84901234567'), '+84901234567');
});

test('buildLeadSearchFilters builds OR filter on email and mobile_no', () => {
	const filters = buildLeadSearchFilters({ email: 'a@b.com', phone: '0901234567' });
	assert.deepEqual(filters, [
		['CRM Lead', 'email', '=', 'a@b.com'],
		['CRM Lead', 'mobile_no', '=', '+84901234567'],
	]);
});

test('buildNewLeadPayload sets source and chatwoot_contact_id', () => {
	const payload = buildNewLeadPayload({
		source: 'Messenger',
		name: 'Nguyen Van A',
		email: 'a@b.com',
		phone: '0901234567',
		chatwootContactId: '42',
	});
	assert.equal(payload.source, 'Messenger');
	assert.equal(payload.lead_name, 'Nguyen Van A');
	assert.equal(payload.mobile_no, '+84901234567');
	assert.equal(payload.chatwoot_contact_id, '42');
});
```

- [ ] **Step 2: Chạy test, xác nhận fail vì chưa có implementation**

Run: `node --test n8n/logic/dedupe.test.js`
Expected: FAIL — `Cannot find module './dedupe'`.

- [ ] **Step 3: Viết implementation**

Create `n8n/logic/dedupe.js`:

```javascript
function normalizePhone(raw) {
	const digits = raw.replace(/[\s-]/g, '');
	if (digits.startsWith('+84')) return digits;
	if (digits.startsWith('0')) return '+84' + digits.slice(1);
	return digits;
}

function buildLeadSearchFilters({ email, phone }) {
	return [
		['CRM Lead', 'email', '=', email],
		['CRM Lead', 'mobile_no', '=', normalizePhone(phone)],
	];
}

function buildNewLeadPayload({ source, name, email, phone, chatwootContactId }) {
	return {
		source,
		lead_name: name,
		email,
		mobile_no: normalizePhone(phone),
		chatwoot_contact_id: chatwootContactId,
	};
}

module.exports = { normalizePhone, buildLeadSearchFilters, buildNewLeadPayload };
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `node --test n8n/logic/dedupe.test.js`
Expected: PASS — `# pass 3`, `# fail 0`.

- [ ] **Step 5: Commit**

Run:
```bash
cd /home/giabao/dev/dx-osd
git add n8n/logic/dedupe.js n8n/logic/dedupe.test.js
git commit -m "feat: add dedup/mapping logic for Chatwoot-CRM sync"
```

### Task 9: Build n8n workflow (Chatwoot webhook → CRM)

**Files:** Không có file code repo track được trực tiếp — build qua n8n UI tại `https://n8n.example.com`, rồi export JSON về `n8n/workflows/messenger-to-crm.export.json` ở Step cuối để version control.

**Interfaces:**
- Consumes: `normalizePhone`, `buildLeadSearchFilters`, `buildNewLeadPayload` (Task 8, copy nguyên văn vào Code node)
- Consumes: `api_key`/`api_secret` (Task 7), Chatwoot webhook signing secret (Step 1 dưới đây)

- [ ] **Step 1: Tạo Webhook trong Chatwoot, lấy signing secret**

Vào `https://chat.example.com` → Settings → Integrations → Webhooks → Add new webhook. URL: `https://n8n.example.com/webhook/chatwoot-sync`. Subscribe events: `conversation_created`, `contact_updated`. Lưu lại `signing_secret` hiển thị sau khi tạo (dùng ở Step 3).

- [ ] **Step 2: Tạo Credential trong n8n cho Frappe CRM**

Trong n8n UI → Credentials → New → "Header Auth". Name: `Frappe CRM API`. Header name: `Authorization`. Header value: `token <api_key>:<api_secret>` (từ Task 7).

- [ ] **Step 3: Tạo workflow, node 1 — Webhook trigger**

New Workflow → thêm node **Webhook**: HTTP Method `POST`, Path `chatwoot-sync`, Response Mode `Last Node`.

- [ ] **Step 4: Node 2 — Verify HMAC signature (Code node)**

Thêm node **Code** ngay sau Webhook, đặt tên "Verify Signature":

```javascript
const crypto = require('crypto');
const secret = 'SIGNING_SECRET_TU_STEP_1';
const rawBody = JSON.stringify($input.item.json.body ?? $input.item.json);
const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
const received = $input.item.json.headers['x-chatwoot-signature'];

if (expected !== received) {
	throw new Error('Invalid Chatwoot webhook signature');
}

return $input.item;
```

- [ ] **Step 5: Node 3 — Build lead payload (Code node, copy logic từ Task 8)**

Thêm node **Code**, đặt tên "Build Lead Payload", paste nguyên nội dung `n8n/logic/dedupe.js` (3 hàm) rồi thêm đoạn gọi:

```javascript
const contact = $input.item.json.body.conversation.meta.sender;
const conversationId = $input.item.json.body.conversation.id;
const email = contact.email || '';
const phone = contact.phone_number || '';
const payload = buildNewLeadPayload({
	source: $input.item.json.body.conversation.channel.includes('Instagram') ? 'Instagram' : 'Messenger',
	name: contact.name,
	email,
	phone,
	chatwootContactId: String(contact.id),
});
const searchFilters = buildLeadSearchFilters({ email, phone });

return { json: { contact, payload, searchFilters, conversationId } };
```

Node này produce 4 field dùng lại ở các step sau: `contact` (Step 6, 8, 9), `payload` (Step 8), `searchFilters` (Step 7), `conversationId` (Step 9).

- [ ] **Step 6: Node 4 — IF contact đã có crm_lead_id**

Thêm node **IF**: điều kiện `{{$json.contact.custom_attributes.crm_lead_id}}` **is not empty**.
- Nhánh **true** → nối tới Node 7 (Log Activity).
- Nhánh **false** → nối tới Node 5 (Search Existing Lead).

- [ ] **Step 7: Node 5 — Search existing lead (HTTP Request)**

Thêm node **HTTP Request**: Method `GET`, URL `https://crm.example.com/api/resource/CRM Lead`, Query Params: `filters` = `{{JSON.stringify($json.searchFilters)}}` (field `searchFilters` đã có sẵn từ output của Node 3 ở Step 5), Credential: `Frappe CRM API`.

- [ ] **Step 8: Node 6 — IF lead đã tồn tại → Create hoặc Update**

Thêm node **IF**: `{{$json.data.length}}` **is greater than 0**.
- Nhánh **true** (đã có Lead trùng email/phone) → **HTTP Request** `PATCH` tới `https://crm.example.com/api/resource/CRM Lead/{{$json.data[0].name}}`, body `{"chatwoot_contact_id": "{{$('Build Lead Payload').item.json.contact.id}}"}`.
- Nhánh **false** → **HTTP Request** `POST` tới `https://crm.example.com/api/resource/CRM Lead`, body = `{{$('Build Lead Payload').item.json.payload}}`.

Cả 2 nhánh dùng Credential `Frappe CRM API`, nối tiếp sang Node 8 (Write back to Chatwoot).

- [ ] **Step 9: Node 7 — Log Activity (nhánh contact đã map sẵn)**

**HTTP Request** `POST` tới `https://crm.example.com/api/resource/CRM Notes`, body `{"lead": "{{$json.contact.custom_attributes.crm_lead_id}}", "note": "New message from Chatwoot conversation #{{$json.conversationId}}"}`. Credential: `Frappe CRM API`.

- [ ] **Step 10: Node 8 — Write crm_lead_id back to Chatwoot contact**

**HTTP Request**: Method `PUT`, URL `https://chat.example.com/api/v1/accounts/1/contacts/{{$('Build Lead Payload').item.json.contact.id}}`, Header `api_access_token` (tạo Profile Settings → Access Token trong Chatwoot, lưu làm Credential riêng "Chatwoot API"), body `{"custom_attributes": {"crm_lead_id": "{{$json.data.name}}"}}`.

- [ ] **Step 11: Activate workflow**

Bấm "Active" toggle góc trên phải workflow.

- [ ] **Step 12: Export workflow ra file để version control**

Trong n8n UI → workflow menu (···) → Download. Lưu file vào:

Run:
```bash
mkdir -p /home/giabao/dev/dx-osd/n8n/workflows
# di chuyển file vừa tải từ trình duyệt/VPS vào đây
mv ~/Downloads/*.json /home/giabao/dev/dx-osd/n8n/workflows/messenger-to-crm.export.json
```

- [ ] **Step 13: Commit**

Run:
```bash
cd /home/giabao/dev/dx-osd
git add n8n/workflows/messenger-to-crm.export.json
git commit -m "feat: add n8n workflow export for Chatwoot-CRM sync"
```

---

## Phase 5: End-to-end test + webhook security review

### Task 10: Test toàn luồng bằng webhook giả lập

**Files:** Không có file mới — test bằng curl trực tiếp vào n8n webhook.

- [ ] **Step 1: Giả lập webhook Chatwoot thật (KHÔNG kèm signature đúng — phải bị từ chối)**

Run:
```bash
curl -s -X POST https://n8n.example.com/webhook/chatwoot-sync \
  -H "Content-Type: application/json" \
  -H "X-Chatwoot-Signature: sai_signature" \
  -d '{"conversation":{"id":999,"channel":"Channel::FacebookPage","meta":{"sender":{"id":123,"name":"Test User","email":"test@example.com","phone_number":"0901234567","custom_attributes":{}}}}}'
```
Expected: n8n workflow execution log (n8n UI → Executions) hiển thị lỗi `Invalid Chatwoot webhook signature` — nghĩa là bước verify HMAC ở Task 9 Step 4 hoạt động đúng, không phải giả định.

- [ ] **Step 2: Tạo conversation thật trong Chatwoot để lấy signature hợp lệ**

Trong Chatwoot UI (`https://chat.example.com`), tạo 1 conversation test qua kênh test (hoặc gửi tin nhắn thật qua Page Messenger đã kết nối ở Phase 0). Xác nhận n8n Executions nhận được event với signature hợp lệ (không có lỗi `Invalid Chatwoot webhook signature`).

- [ ] **Step 3: Verify Lead được tạo trong CRM**

Run:
```bash
curl -s -u admin:admin "https://crm.example.com/api/resource/CRM Lead?filters=[[\"source\",\"=\",\"Messenger\"]]&fields=[\"name\",\"lead_name\",\"chatwoot_contact_id\"]"
```
Expected: JSON chứa 1 Lead mới với `chatwoot_contact_id` khớp với contact id trong Chatwoot.

- [ ] **Step 4: Verify crm_lead_id được ghi ngược vào Chatwoot**

Run:
```bash
curl -s -H "api_access_token: <CHATWOOT_ACCESS_TOKEN>" \
  "https://chat.example.com/api/v1/accounts/1/contacts/<CONTACT_ID>" | grep -o '"crm_lead_id":"[^"]*"'
```
Expected: in ra `"crm_lead_id":"<TÊN LEAD VỪA TẠO Ở STEP 3>"`.

- [ ] **Step 5: Test dedup — gửi tin nhắn thứ 2 từ cùng khách, xác nhận KHÔNG tạo Lead thứ 2**

Lặp lại Step 2 với cùng khách hàng (cùng email/phone). Chạy lại lệnh ở Step 3.
Expected: vẫn chỉ có **1** Lead (không phải 2) — nghĩa là nhánh IF ở Task 9 Step 6 (contact đã có `crm_lead_id`) đã chặn đúng, chỉ tạo Activity thay vì Lead mới.

### Task 11: Security review checklist

**Files:** Không có file mới — checklist verify bằng lệnh thật.

- [ ] **Step 1: Xác nhận không có port nào expose ra ngoài 127.0.0.1 ngoại trừ Caddy**

Run: `sudo ss -tlnp | grep -E ':3000|:8000|:5678'`
Expected: cả 3 dòng đều hiển thị `127.0.0.1:<port>`, không có `0.0.0.0:<port>`.

- [ ] **Step 2: Xác nhận webhook secret không nằm trong git history**

Run: `git log -p -- n8n/ docker/ frappe-custom/ | grep -iE "signing_secret|api_secret|access_token" `
Expected: không có kết quả nào (secrets chỉ tồn tại trong n8n Credentials store và Chatwoot DB, không commit vào repo).

- [ ] **Step 3: Xác nhận .env files bị gitignore đúng**

Run: `git check-ignore -v docker/n8n/.env chatwoot/.env`
Expected: cả 2 file đều match rule trong `.gitignore` (từ Task 1).

---

## Self-review notes
- Spec coverage: Phase 0 = Meta App (spec §Flow A prereq), Phase 1 = repo bootstrap, Phase 2 = 3 stack deploy (spec §Deployment), Phase 3 = custom field (spec §Data model), Phase 4 = dedup logic + workflow (spec §Flow B, §Rủi ro dedup), Phase 5 = end-to-end + security (spec §Rủi ro bảo mật webhook). `facebook.py` pagination TODO và `crm/docker` ephemeral-state risk đều đã có task xử lý hoặc note rõ (Task 3 Step 1 fix ephemeral state; pagination TODO chỉ note trong spec, không cần fix theo quyết định của user).
- Không có task nào cho Airbyte/messenger-platform-samples/Meta Business SDK độc lập — đúng như "Ngoài phạm vi" trong spec.
