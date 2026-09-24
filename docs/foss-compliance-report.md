# BÁO CÁO ĐÁNH GIÁ VÀ CHỨNG NHẬN TUÂN THỦ BẢN QUYỀN PHẦN MỀM NGUỒN MỞ
## FOSS Compliance & License Audit Report — DX-OSD Platform

**Dự án:** DX-OSD (Digital Transformation — Open Source Distribution)  
**Tác giả thực hiện:**  
- Hoàng Thành (`thanhheo7749@gmail.com`) — Kỹ sư Tích hợp & FOSS Compliance  
- Lưu Gia Bảo (`baoluu674@gmail.com`) — Kỹ sư Kiến trúc Hệ thống  
**Đơn vị:** Trường Đại học Công nghệ TP.HCM (HUTECH)  
**Kỳ thi / Hội đồng:** Olympic Tin Học Sinh Viên Việt Nam 2026 — Khối Phần Mềm Nguồn Mở (OLP PMNM 2026) / Hiệp hội Phần mềm Nguồn mở Việt Nam (VFOSSA)  
**Ngày lập báo cáo:** 24/09/2026  
**Phiên bản tài liệu:** 2.0 (Chính thức)  
**Tình trạng tuân thủ:** **100% ĐẠT CHUẨN NGUỒN MỞ OSI (100% Pure OSI-Approved FOSS)**

---

## 1. Tuyên ngôn Tuân thủ Bản quyền (Executive Summary)

Dự án **DX-OSD** được thiết kế và triển khai nhằm cung cấp giải pháp chuyển đổi số toàn diện về tiếp nhận khách hàng đa kênh (Facebook Lead Ads, Messenger, Instagram Direct) và hội tụ dữ liệu bán hàng vào một nền tảng quản trị quan hệ khách hàng (CRM) duy nhất dành cho doanh nghiệp vừa và nhỏ (SMB).

Đội ngũ phát triển cam kết tuân thủ tuyệt đối quy chế thi đấu của Khối Phần Mềm Nguồn Mở (OLP PMNM) và các tiêu chuẩn bản quyền của **Open Source Initiative (OSI)** cũng như **Free Software Foundation (FSF)**:
1. **100% Giấy phép Chuẩn Nguồn mở:** Toàn bộ thành phần phần mềm được sử dụng, tích hợp và triển khai trong kiến trúc DX-OSD đều mang giấy phép được OSI công nhận (GNU AGPLv3, MIT, Apache 2.0, BSD-3-Clause, GPLv2).
2. **Không chứa mã nguồn độc quyền:** Không sử dụng bất kỳ phần mềm nguồn đóng, phần mềm thương mại, hoặc phần mềm mang giấy phép "nguồn mở giả tạo" (Fair-code, Source-Available, BSL, SSPL, RSAL).
3. **Kiến trúc tinh gọn 2 cụm (2-Stack Model):** Loại bỏ hoàn toàn tầng trung gian tự động hóa `n8n` (do vấn đề bản quyền Sustainable Use License không thuộc OSI) và thay thế bằng Frappe Custom App `mmm_custom` chạy trực tiếp trên nền tảng Python/Frappe Bench theo giấy phép MIT.
4. **Minh bạch và Có thể Kiểm chứng:** Báo cáo này đính kèm bằng chứng kiểm toán (audit trail), đối chiếu mã nguồn, kết quả kiểm thử tự động (23 unit tests) và kiểm thử tích hợp thực tế (5 live integration tests) với tỷ lệ vượt qua đạt 100%.

---

## 2. Kiến trúc Hệ thống 2 Cụm (Streamlined 2-Stack Architecture)

Hệ thống DX-OSD vận hành dựa trên 2 cụm dịch vụ chính độc lập, giao tiếp với nhau thông qua giao thức mạng chuẩn HTTP/JSON REST API có bảo mật HMAC-SHA256:

```
[Khách hàng / Fanpage]
       │
       ▼ (Facebook Graph API)
┌────────────────────────────────────────────────────────┐
│ Cụm 1: Chatwoot Community Edition (Cổng tiếp nhận CSKH) │
│ - Bản quyền: MIT Expat                                 │
│ - Đã loại bỏ hoàn toàn module enterprise/              │
│ - Cổng lắng nghe nội bộ: 127.0.0.1:3000                │
└───────────────────────┬────────────────────────────────┘
                        │
                        │ HTTP Webhook POST (HMAC-SHA256 + Timestamp Anti-Replay)
                        ▼
┌────────────────────────────────────────────────────────┐
│ Cụm 2: Frappe CRM & Custom In-Bench App (`mmm_custom`) │
│ - Frappe CRM v1.84.0 (GNU AGPLv3)                      │
│ - Frappe Framework v15.121.1 (GNU AGPLv3)              │
│ - In-Bench Webhook Endpoint: mmm_custom (MIT)          │
│   + Deduplication Engine (chống trùng lặp SĐT/Email)   │
│   + Keyword Detection (phân loại khoá học tự động)     │
│   + FCRM Note Logging & Chatwoot Contact Writeback     │
│ - Cơ sở dữ liệu: MariaDB 10.8 (GPLv2)                  │
│ - Bộ nhớ đệm & Hàng đợi: Redis 7.2.4-alpine (BSD-3)    │
│ - Cổng lắng nghe nội bộ: 127.0.0.1:8000                │
└────────────────────────────────────────────────────────┘
```

---

## 3. Danh mục Bản quyền Chi tiết (Exhaustive FOSS License Inventory)

Bảng dưới đây liệt kê toàn bộ các thành phần phần mềm, thư viện và hạ tầng tạo nên giải pháp DX-OSD:

| STT | Thành phần / Module | Thư mục / Image | Phiên bản / Tag | Giấy phép (SPDX) | Được OSI công nhận? | Vai trò trong hệ thống |
|:---:|---|---|---|---|:---:|---|
| 1 | **Frappe CRM** | `crm/` (vendored) | `v1.84.0` | **GNU AGPL-3.0-only** | **CÓ** | Nền tảng CRM, quản lý Lead, Contact, Deal, đồng bộ Meta Lead Ads |
| 2 | **Frappe Framework** | Docker bench image | `v15.121.1` | **GNU AGPL-3.0-only** | **CÓ** | Framework nền tảng full-stack Python / MariaDB |
| 3 | **Chatwoot Community** | `chatwoot/` (vendored) | `4.18.0` | **MIT** | **CÓ** | Cổng giao tiếp hội thoại Facebook Messenger / Instagram Direct |
| 4 | **Frappe Custom App (`mmm_custom`)** | `frappe-custom/mmm_custom/` | `0.0.1` | **MIT** | **CÓ** | Nhận webhook, xác thực chữ ký HMAC-SHA256, deduplication, phân tích khoá học |
| 5 | **Caddy Server** | `docker/caddy/` | `caddy:2-alpine` | **Apache-2.0** | **CÓ** | Cổng Reverse Proxy biên, tự động hóa chứng chỉ SSL/TLS |
| 6 | **MariaDB Server** | `crm/docker/` | `mariadb:10.8` | **GPL-2.0-only** | **CÓ** | Hệ quản trị cơ sở dữ liệu quan hệ cho Frappe CRM |
| 7 | **Redis In-Memory Store** | `crm/docker/`, `docker/chatwoot/` | `redis:7.2.4-alpine` | **BSD-3-Clause** | **CÓ** | Bộ nhớ cache và điều phối tác vụ nền (Sidekiq / Celery) |
| 8 | **PostgreSQL Server** | `chatwoot/` | `postgres:12-alpine` | **PostgreSQL License** (tương đương MIT/BSD) | **CÓ** | Cơ sở dữ liệu quan hệ cho Chatwoot |

### Đánh giá các thư viện phụ thuộc chính (Dependencies):
- **Python Backend:** `requests` (Apache-2.0), `cryptography` (Apache-2.0 / BSD-3-Clause), `pyjwt` (MIT), `werkzeug` (BSD-3-Clause), `jinja2` (BSD-3-Clause).
- **Node.js Frontend:** Vue 3 (MIT), Tailwind CSS (MIT), Vite (MIT).
- **Ruby on Rails (Chatwoot):** Rails core (MIT), Sidekiq open-source core (LGPL-3.0-only).

---

## 4. Nhật ký Kiểm toán & Loại trừ Thành phần Phi Nguồn Mở (Audit Trail)

Để đạt được trạng thái 100% FOSS thuần khiết theo đúng tiêu chí OLP PMNM, nhóm phát triển đã tiến hành các đợt rà soát và loại bỏ triệt để các rủi ro bản quyền qua các commit cụ thể:

### 4.1. Gỡ bỏ Hoàn toàn `n8n` (Commit `0b1f8cd`)
- **Vấn đề phát hiện:** `n8n` được phát hành theo giấy phép *Sustainable Use License* kết hợp *Fair-code*. Giấy phép này giới hạn quyền khai thác thương mại và cung cấp dịch vụ (SaaS/Hosting), vi phạm trực tiếp **Điều khoản 6 của Định nghĩa Nguồn mở OSI (OSD #6 — No Discrimination Against Fields of Endeavor)**. Do đó, `n8n` **không phải là phần mềm nguồn mở FOSS**.
- **Hành động khắc phục:**
  - Ngừng toàn bộ container `n8n` và xóa sạch volume.
  - Sử dụng `git rm -r` xóa bỏ toàn bộ thư mục `docker/n8n/` và `n8n/` (bao gồm `n8n/logic/` và `n8n/workflows/`).
  - Viết lại toàn bộ logic xử lý webhook, chuẩn hóa số điện thoại, và thuật toán chống trùng lặp bằng mã nguồn Python thuần túy tích hợp trong Frappe App `mmm_custom` (`mmm_custom/api.py` và `mmm_custom/dedupe.py`).
  - Kết quả: Không phụ thuộc bên ngoài, giảm 1 cụm Docker container (~800MB RAM), loại bỏ 100% rủi ro bản quyền của n8n.

### 4.2. Thanh lọc Thư mục `chatwoot/enterprise/` (Commit `ccf745b`)
- **Vấn đề phát hiện:** Mã nguồn Chatwoot từ upstream áp dụng cơ chế song song (dual-licensed): thư mục gốc là MIT, nhưng thư mục con `enterprise/` chứa các tính năng độc quyền thương mại và có file `enterprise/LICENSE` hạn chế quyền tự do sử dụng.
- **Hành động khắc phục:**
  - Xóa bỏ hoàn toàn toàn bộ thư mục `chatwoot/enterprise/` (55+ file mã nguồn độc quyền, ~4,000 dòng code).
  - Điều chỉnh cấu hình Rails trong [chatwoot/config/application.rb](file:///C:/TepD/HUTECH/OLP1/dx-osd/chatwoot/config/application.rb) để chặn nạp các namespace `Enterprise::` khi khởi động.
  - Chatwoot giờ đây biên dịch và thực thi 100% dưới tư cách bản phát hành cộng đồng thuần khiết **Chatwoot Community Edition** mang giấy phép **MIT Expat**.

### 4.3. Loại bỏ Bộ Mã mẫu `messenger-platform-samples/` (Commit `ccf745b`)
- **Vấn đề phát hiện:** Thư mục `messenger-platform-samples/` chứa mã nguồn mẫu từ Meta phục vụ tham khảo, mang các điều khoản cấp phép riêng biệt từ Meta Platforms, Inc. và không trực tiếp tham gia chu trình vận hành của sản phẩm.
- **Hành động khắc phục:**
  - Xóa bỏ triệt để toàn bộ thư mục `messenger-platform-samples/` (639 file, 43,414 dòng code).
  - Tích hợp trực tiếp giao thức Meta Graph API thông qua Chatwoot Community inbox.

### 4.4. Đóng băng Phiên bản Redis ở `7.2.4-alpine` (Commit `6607528`)
- **Vấn đề phát hiện:** Đầu năm 2024, Redis Ltd. chính thức chuyển đổi giấy phép kể từ bản Redis 7.4+ từ BSD-3-Clause sang giấy phép kép SSPLv1 và RSALv2 (cả hai đều bị OSI bác bỏ, không được công nhận là FOSS).
- **Hành động khắc phục:**
  - Cập nhật file cấu hình [crm/docker/docker-compose.override.yml](file:///C:/TepD/HUTECH/OLP1/dx-osd/crm/docker/docker-compose.override.yml) và [docker/chatwoot/docker-compose.override.yaml](file:///C:/TepD/HUTECH/OLP1/dx-osd/docker/chatwoot/docker-compose.override.yaml).
  - Đóng băng tường minh hình ảnh Docker: `redis:7.2.4-alpine`.
  - Đảm bảo toàn bộ Redis đang chạy là phiên bản ổn định cuối cùng mang bản quyền **BSD-3-Clause** được OSI công nhận.

---

## 5. Phân tích Tính Tương thích Giấy phép (License Compatibility Analysis)

Một yêu cầu tối quan trọng trong việc xây dựng sản phẩm FOSS là đảm bảo không xảy ra xung đột bản quyền giữa các giấy phép có tính chất Copyleft mạnh (như AGPLv3) và các giấy phép thông thoáng (Permissive như MIT, Apache 2.0, BSD-3):

1. **Frappe CRM (GNU AGPLv3) và Frappe Custom App `mmm_custom` (MIT):**
   - Giấy phép MIT là giấy phép tương thích xuôi (permissive and forward-compatible) với GNU AGPLv3 theo công bố chính thức của FSF.
   - Khi `mmm_custom` chạy trong Frappe Bench cùng với Frappe CRM, toàn bộ mã nguồn của `mmm_custom` được công khai minh bạch ngay trong kho mã nguồn của dự án theo đúng điều khoản chia sẻ của AGPL-3.0 (Section 13 - Remote Network Interaction).
2. **Chatwoot Community (MIT) và Frappe CRM (AGPLv3):**
   - Hai hệ thống hoạt động ở hai tiến trình độc lập, được đóng gói trong các container Docker riêng biệt.
   - Giao tiếp giữa Chatwoot và Frappe CRM hoàn toàn thông qua giao thức mạng tiêu chuẩn mở (HTTP POST Webhook và REST API qua cổng JSON). Theo quy định của FSF về "Aggregate and Independent Programs", việc truyền tin qua mạng giữa hai phần mềm độc lập không cấu thành hành vi vi phạm hay "nhiễm bản quyền" chéo giữa các hệ thống.
3. **Caddy Server (Apache 2.0) và MariaDB (GPLv2):**
   - Đóng vai trò các dịch vụ hạ tầng mạng độc lập, tuân thủ hoàn toàn quyền phân phối và thực thi nhị phân.

---

## 6. Bảo mật và Tính Toàn vẹn Dữ liệu (Security & Integrity)

Hệ thống tích hợp tuân thủ nghiêm ngặt các nguyên tắc bảo mật phần mềm nguồn mở:
- **Xác thực Chữ ký HMAC-SHA256:** Endpoint `chatwoot_sync()` trong `mmm_custom/api.py` kiểm tra chữ ký số `X-Chatwoot-Signature` thông qua hàm so sánh an toàn thời gian thực `hmac.compare_digest`, ngăn chặn hoàn toàn tấn công giả mạo yêu cầu (Request Forgery).
- **Chống Tấn công Phát lại (Anti-Replay Attack Protection):** Kiểm tra header `X-Chatwoot-Timestamp`. Mọi yêu cầu có độ lệch thời gian vượt quá ±300 giây đều bị từ chối ngay lập tức với mã lỗi HTTP 401.
- **Ràng buộc Địa chỉ Cục bộ (Localhost Binding):** Toàn bộ các cổng dịch vụ nội bộ (`3000`, `8000`, `9000`, `15432`, `16379`) chỉ liên kết với giao diện loopback `127.0.0.1`. Chỉ có cổng của Caddy mới được phép tiếp xúc với Internet công cộng khi triển khai máy chủ thật.
- **Không Lưu trữ Khóa Bí mật:** Không có mật khẩu, Access Token hoặc HMAC Secret nào bị lưu vết (hardcode) trong lịch sử git. Mọi định danh truy cập đều dùng biến môi trường hoặc script cấu hình an toàn tự động che dấu token (token masking).

---

## 7. Bằng chứng Thực nghiệm và Kết quả Kiểm thử (Audit & Verification Evidence)

### 7.1. Bộ Kiểm thử Đơn vị Tự động (Automated Unit Tests)
Bộ kiểm thử Python Unittest độc lập đặt tại `frappe-custom/mmm_custom/mmm_custom/tests/`:
- **Lệnh thực thi:**
  ```bash
  python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v
  ```
- **Kết quả thực tế:**
  - Tổng số test case: **23/23 tests**
  - Trạng thái: **100% PASSED (OK)**
  - Thời gian thực thi: **0.038 giây**
  - Chi tiết bao gồm: 7 bài test chuẩn hóa số điện thoại và bộ lọc tìm kiếm (`test_dedupe.py`); 16 bài test kiểm tra xác thực HMAC, chống replay, phân tích JSON, nhận diện từ khóa khoá học (`Tiếng Anh`, `Bơi lội`, `Toán tư duy`), và tích hợp ghi chú CRM (`test_api.py`).

### 7.2. Bộ Kiểm thử Tích hợp Thực tế (Live End-to-End Integration Tests)
Kịch bản kiểm thử tích hợp trực tiếp trên cụm Docker container đang chạy thông qua công cụ [scripts/test-chatwoot-crm-sync.py](file:///C:/TepD/HUTECH/OLP1/dx-osd/scripts/test-chatwoot-crm-sync.py):
- **Lệnh thực thi:**
  ```bash
  python scripts/test-chatwoot-crm-sync.py
  ```
- **Kết quả thực tế:**
  - **[Test 1/5] Kiểm tra Từ chối Chữ ký HMAC Giả mạo:** Máy chủ trả về HTTP 401 Unauthorized -> **ĐẠT (PASS)**.
  - **[Test 2/5] Kiểm tra Chống Tấn công Phát lại (Expired Timestamp):** Máy chủ trả về HTTP 401 Unauthorized -> **ĐẠT (PASS)**.
  - **[Test 3/5] Kiểm tra Tiếp nhận Hội thoại & Tạo Lead Mới:** Lead `CRM-LEAD-2026-00001` ("Hoàng Thành") được khởi tạo thành công trên Frappe CRM -> **ĐẠT (PASS)**.
  - **[Test 4/5] Kiểm tra Hội tụ Lead & Chống Trùng lặp (Convergence):** Tin nhắn tiếp theo từ cùng một học viên tự động tìm thấy Lead cũ, không tạo Lead mới, tự động nối thêm ghi chú `FCRM Note` mới -> **ĐẠT (PASS)**.
  - **[Test 5/5] Kiểm tra Xử lý An toàn Sự kiện Khác:** Sự kiện không phải tạo hội thoại được bỏ qua an toàn mà không sinh lỗi -> **ĐẠT (PASS)**.
  - **Tổng kết:** **5/5 tests PASSED (Tỷ lệ 100%)**.

### 7.3. Trạng thái Dịch vụ Thực tế (Live Health Status)
```bash
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000
200
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000
200
```
Cả hai hệ thống Chatwoot và Frappe CRM đều đang phản hồi HTTP 200 lành mạnh, ổn định.

---

## 8. Kết luận & Chứng nhận Bản quyền

Căn cứ trên kết quả rà soát mã nguồn, cấu hình hạ tầng và bằng chứng thực nghiệm:

> **XÁC NHẬN:** Dự án **DX-OSD** đạt chuẩn **100% Phần mềm Nguồn Mở Tự do (Pure FOSS)**, hoàn toàn tương thích và tuân thủ các quy định của Open Source Initiative (OSI) cũng như Quy chế chuyên môn của Hội thi Olympic Tin Học Sinh Viên Việt Nam 2026 — Khối Phần Mềm Nguồn Mở.
>
> Dự án sẵn sàng cho công tác nghiệm thu và đánh giá chuyên môn từ Ban Giám khảo VFOSSA.

---

**Đại diện Đội ngũ Phát triển Dự án DX-OSD:**  
*Hoàng Thành & Lưu Gia Bảo*  
*Trường Đại học Công nghệ TP.HCM (HUTECH)*
