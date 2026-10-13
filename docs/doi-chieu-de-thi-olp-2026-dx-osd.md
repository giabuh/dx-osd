# Đối chiếu đề thi OLP 2026 (khối Phần mềm Nguồn mở) với kiến trúc DX-OSD

> Soạn ngày 11/10/2026. Dự án DX-OSD / EduFlow — tách riêng khỏi đề tài NCKH.
> Tài liệu này chỉ đối chiếu theo hai nguồn: (1) văn bản **đề thi chính thức** trên VFOSSA, đọc trực tiếp ngày 11/10/2026 — “Đề thi Phần mềm nguồn mở – OLP 2026: Xây dựng Hệ điều hành Chuyển đổi số bằng Công nghệ Lõi nguồn mở (DX-OS Open-Core)”, https://vfossa.vn/tin-tuc/de-thi-phan-mem-nguon-mo-olp-2026-798.html ; (2) **báo cáo 29 repo đã lọc OSI** đã giao ngày 10/10/2026, kèm phiếu kiểm chứng giấy phép trực tiếp ngày 10/10/2026.
> Lưu ý thời điểm: thể lệ từng ghi đề thi công bố tháng 11/2026, nhưng văn bản đề thi **đã truy cập và đọc được trực tiếp ngày 11/10/2026** — lấy trạng thái thực tế này làm chuẩn.

## Cách đọc trạng thái

| Trạng thái | Nghĩa |
|---|---|
| Khớp theo thiết kế | Kiến trúc DX-OSD đã chọn thành phần tương ứng trong báo cáo 29 repo. **Không** đồng nghĩa đã triển khai xong hay đã chạy được — bằng chứng triển khai phải đến từ kho mã nguồn thật của đội |
| Khớp một phần | Có thành phần đáp ứng một phần yêu cầu; còn thiếu năng lực mà đề thi nêu |
| Khoảng trống | Chưa có thành phần nào trong kiến trúc/danh mục đáp ứng |
| Chưa chốt quyết định | Bị chặn bởi một trong ba quyết định thiết kế còn mở — ghi rõ ở đúng dòng bị ảnh hưởng |
| Chưa kiểm chứng | Giấy phép/mức đáp ứng mới ở mức nguồn thứ cấp hoặc suy luận, phải kiểm chứng lại trên repo gốc trước khi khẳng định trước Ban Giám khảo |

Nguyên tắc xuyên suốt: không khẳng định một yêu cầu “đã đáp ứng” khi bằng chứng chưa tới mức đó.

---

## 1. Bảng gap — Tầng 1: nền tảng lõi headless (bắt buộc)

Đề thi (mục 3) yêu cầu nền tảng lõi Open-Core ở Tầng 1 vận hành **hoàn toàn không giao diện (headless)**, chỉ cung cấp dịch vụ dạng PaaS cho ứng dụng tầng trên, và bắt buộc có 4 dịch vụ: Định danh bảo mật (Identity/SSO), Cổng API (API Gateway), Quản trị dữ liệu cấu trúc/phi cấu trúc, Động cơ luồng công việc (Workflow). Đề thi nêu Supabase / Strapi / Directus làm ví dụ tham chiếu cho nguyên lý headless này.

| # | Yêu cầu của đề thi | Phần DX-OSD tương ứng | Repo liên quan (trong danh mục 29) | Trạng thái | Khoảng trống còn lại |
|---|---|---|---|---|---|
| 1.0 | Toàn bộ lõi Tầng 1: headless, không UI, chỉ cung cấp dịch vụ cho tầng trên | Frappe Framework làm lõi dịch vụ (DocType, REST API, hàng đợi, phân quyền); giao diện người dùng đặt ở ứng dụng Tầng 2 (Vue 3) | `frappe/frappe` — MIT [kiểm chứng trực tiếp 10/10] | Khớp theo thiết kế, có lưu ý | Frappe vốn kèm giao diện quản trị (Desk). Khi trình bày phải phân định rạch ròi: phần *lõi* dự thi là dịch vụ/API của Frappe, phần UI thuộc Tầng 2 — nếu để Ban Giám khảo hiểu Desk là giao diện của lõi, lập luận headless sẽ yếu |
| 1.1 | Định danh bảo mật — Identity/SSO (mô tả tầng lõi ở mục 2 còn gồm MFA, quản lý khóa/bí mật, PKI) | Định danh và phân quyền theo vai tích hợp sẵn trong Frappe Framework; đăng nhập qua nhà cung cấp ngoài bằng OAuth/OIDC ở mức ứng dụng | `frappe/frappe` — MIT [trực tiếp] | Khớp một phần | Chưa có IdP/SSO chuyên trách (ví dụ Keycloak được đề thi nêu ở lớp tham chiếu 2) trong danh mục 29 repo — danh mục hiện **không có** repo IdP riêng. MFA, quản lý bí mật, PKI theo mô tả đầy đủ của mục 2 chưa có thành phần tương ứng. Cần quyết định bổ sung IdP ngoài danh mục (kiểm chứng giấy phép riêng) hay giới hạn phạm vi ở mức Frappe cung cấp và trình bày trung thực phần thiếu |
| 1.2 | Cổng API — API Gateway (mục 2: kiểm soát biên mạng, mô hình zero-trust, đa thuê ước/cách ly dữ liệu, che giấu PII) | Frappe tự sinh REST API từ DocType, phân quyền tới cấp dòng; đa chi nhánh ánh xạ qua Company/site trong cùng lõi | `frappe/frappe` — MIT [trực tiếp] | Khớp một phần | Chưa có API Gateway độc lập trong danh mục 29 repo: chưa có lớp chặn biên riêng cho rate-limit, định tuyến, zero-trust như mô tả mục 2 (đề thi nêu Apache APISIX ở lớp tham chiếu 2 — **ngoài** danh mục 29, chưa kiểm chứng trong báo cáo). Cơ chế che giấu PII chưa có thành phần tương ứng. Nếu bổ sung gateway ngoài danh mục phải kiểm chứng giấy phép trước khi đưa vào kiến trúc |
| 1.3 | Quản trị dữ liệu **cấu trúc** và giao dịch (mục 2: OLTP bảo đảm toàn vẹn; tự sinh API từ CSDL kèm phân quyền cấp dòng; quản lý phiên bản/lịch sử biến động dữ liệu) | Frappe DocType trên MariaDB là nguồn sự thật giao dịch; versioning tài liệu và nhật ký hoạt động có sẵn trong lõi Frappe; ERPNext + Frappe Education giữ dữ liệu nghiệp vụ giáo dục | `frappe/frappe` — MIT [trực tiếp]; `frappe/erpnext` — GPL-3.0 [trực tiếp]; `frappe/education` — GPL-3.0 [**kiểm chứng trực tiếp trên license.txt gốc** 10/10] | Khớp theo thiết kế | Đây là dịch vụ lõi mạnh nhất của DX-OSD so với đề. Điểm phải giữ khi tích hợp: tệp license.txt của Frappe Education chỉ có một dòng khai báo, không kèm toàn văn GPL — giữ nguyên tệp và bảo đảm header giấy phép cho từng tệp mã tự viết (lỗi trừ 5 điểm/lỗi ở nhóm cấp phép PoF). **Quyết định mở #1 (giấy phép sản phẩm) ảnh hưởng trực tiếp dòng này** — xem mục 3 |
| 1.4 | Quản trị dữ liệu **phi cấu trúc** và hồ sơ (mục 2: lưu trữ đối tượng; quản lý hồ sơ/văn bản phục vụ phê duyệt; đánh chỉ mục toàn văn; trộn dữ liệu tự động sinh biểu mẫu/báo cáo) | Quản lý tệp đính kèm trong Frappe phục vụ hồ sơ nghiệp vụ của EduFlow; sự kiện phả hệ dữ liệu theo chuẩn OpenLineage lưu trong Frappe | `frappe/frappe` — MIT [trực tiếp]; `OpenLineage/OpenLineage` — Apache-2.0 [mức thứ cấp trong báo cáo, chưa mở LICENSE trực tiếp] | Khớp một phần | Chưa có kho lưu trữ đối tượng chuyên trách (đề thi nêu MinIO ở lớp tham chiếu 5 — ngoài danh mục 29, giấy phép chưa kiểm chứng trong báo cáo này) và chưa có động cơ đánh chỉ mục toàn văn chuyên trách trong danh mục. Trộn dữ liệu sinh biểu mẫu/báo cáo động mới ở mức tính năng của Frappe/ERPNext, chưa có bằng chứng kiểm chứng riêng |
| 1.5 | Động cơ luồng công việc — Workflow (mục 2: quản lý trạng thái luồng phê duyệt BPMN; thực thi kịch bản tự động hóa ngầm; API nạp dữ liệu theo lô) | Frappe Workflow + Scheduler lo phê duyệt và tác vụ nền ở lõi; lớp workflow kéo-thả bên ngoài **chưa chốt** | `frappe/frappe` — MIT [trực tiếp] (Workflow/Scheduler tích hợp); các ứng viên thay thế: `activepieces/activepieces` — lõi MIT nhưng thư mục `ee/` theo giấy phép thương mại [kiểm chứng trực tiếp tài liệu giấy phép trong repo 10/10]; `node-red/node-red` — Apache-2.0 [mức thứ cấp] | **Chưa chốt quyết định** | **Quyết định mở #2 (thay n8n) chặn trực tiếp dòng này.** n8n phải loại: giấy phép Sustainable Use License (fair-code), không được OSI công nhận — dù đề thi nêu n8n làm ví dụ ở lớp tham chiếu 4, việc dùng n8n vẫn xung đột cổng giấy phép OSI của thể lệ (dự án không đạt yêu cầu nguồn mở thì không được chấm xếp hạng) và nhóm cấp phép PoF. Nếu chưa chốt, phần “kịch bản tự động hóa ngầm” ngoài Frappe Workflow chưa có chủ sở hữu kỹ thuật; hỗ trợ BPMN chuẩn cũng chưa có thành phần tương ứng trong danh mục |

### Yêu cầu xuyên suốt Tầng 1 — giấy phép phát hành (cổng xếp hạng)

| Yêu cầu | Phần DX-OSD tương ứng | Repo liên quan | Trạng thái | Khoảng trống |
|---|---|---|---|---|
| Thể lệ: dự án phải phát hành theo giấy phép **OSI-approved**, mã nguồn truy cập tự do — chỉ dự án đáp ứng mới được chấm xếp hạng; nhóm PoF “cấp phép” trị giá 10 điểm, trừ 5 điểm cho mỗi lỗi (không ghi giấy phép từng tệp, giấy phép không tương thích, thiếu thông báo, thiếu toàn văn) | DX-OSD đặt chuẩn nội bộ 100% thành phần OSI-approved; đã có quy trình đề xuất: bảng SBOM + quét bằng công cụ rà soát giấy phép trước khi nộp | `aboutcode-org/scancode-toolkit` — Apache-2.0 [thứ cấp]; `oss-review-toolkit/ort` — Apache-2.0 [thứ cấp]; `fossology/fossology` — GPL-2.0-only [thứ cấp] | **Chưa chốt quyết định** | **Quyết định mở #1 (giấy phép sản phẩm) chặn toàn bộ Tầng 1**, không chỉ một dịch vụ: lõi Frappe là MIT, dữ liệu giáo dục GPL-3.0, nhưng Frappe CRM/Helpdesk/LMS là AGPL-3.0 [kiểm chứng trực tiếp 10/10]. Chừng nào chưa chốt “AGPL-3.0 toàn bộ” hay “GPL-3.0 + tách CRM thành dịch vụ giao tiếp qua API”, chừng đó chưa thể: ghi header giấy phép thống nhất cho từng tệp mã tự viết, viết thông báo giấy phép của sản phẩm, hay chạy vòng quét tuân thủ cuối cùng. Tác động nếu để sát hạn: nhóm PoF cấp phép là nơi trừ điểm theo từng lỗi, và đây cũng là cổng được-không-được xếp hạng |

---

## 2. Bảng gap — Tầng 2: ít nhất một ứng dụng minh họa thuộc không gian H–P–D–I

Đề thi (mục 3) yêu cầu **ít nhất một** ứng dụng minh họa có giao diện nằm trong không gian H–P–D–I ở Tầng 2. DX-OSD lấy EduFlow (chuỗi trung tâm giáo dục đa chi nhánh) làm ứng dụng minh họa; theo thiết kế, các module của EduFlow chạm cả bốn không gian — bảng dưới đây đối chiếu từng không gian, nhưng **mức yêu cầu tối thiểu của đề chỉ là một**, và trạng thái vẫn là theo thiết kế cho tới khi có bằng chứng từ kho mã nguồn thật.

| Không gian | Yêu cầu của đề thi (mục 2, tóm lược) | Ứng dụng DX-OSD / EduFlow tương ứng | Repo liên quan (trong danh mục 29) | Trạng thái | Khoảng trống còn lại |
|---|---|---|---|---|---|
| **H** — Con người số | Cổng giao tiếp điện tử tập trung; lưu trữ đám mây cá nhân; bảng hiệu suất Kanban & lịch; bách khoa tri thức; ứng dụng di động hiện trường | Cổng học viên/phụ huynh và nhân viên chi nhánh trên Vue 3; kênh giao tiếp đa kênh qua Chatwoot bản Community; quản trị nhân sự cơ bản trong ERPNext | `chatwoot/chatwoot` — **chỉ phần ngoài `enterprise/` là MIT** [trực tiếp]; `frappe/erpnext` — GPL-3.0 [trực tiếp] | Khớp theo thiết kế | Cờ đỏ đã kiểm chứng: thư mục `enterprise/` của Chatwoot (Captain AI, SLA, SSO/SAML, audit logs, custom roles) theo giấy phép thương mại — không được tính vào sản phẩm nguồn mở, không dùng fork “mở khóa”. Kanban/lịch, bách khoa tri thức và ứng dụng di động chưa có module riêng trong thiết kế hiện tại — nếu nhận là làm được cả 5 hạng mục của không gian H sẽ vượt bằng chứng; chỉ nên khẳng định phần cổng giao tiếp và kênh đa kênh |
| **P** — Quy trình số | Thanh toán điện tử và đối soát; hóa đơn điện tử; văn phòng điện tử (e-Office); quản trị nhân sự & KPI; quản lý dự án; công cụ thiết kế biểu mẫu/quy trình BPMN trực quan | Quy trình tuyển sinh – phê duyệt – thu học phí của EduFlow trên Frappe Workflow; kế toán/thu phí trong ERPNext; app tùy biến mmm_custom của đội | `frappe/erpnext` — GPL-3.0 [trực tiếp]; `frappe/frappe` — MIT [trực tiếp] | Khớp một phần | Thanh toán điện tử/đối soát ngân hàng và phát hành hóa đơn điện tử (theo chuẩn Việt Nam) chưa có thành phần nào trong danh mục 29 repo — đây là khoảng trống thật, không lấp bằng khẳng định chung chung. Thiết kế quy trình BPMN trực quan phụ thuộc quyết định mở #2 ở dòng 1.5 |
| **D** — Dữ liệu số | Kho dữ liệu ấm: phân tích/điều hành thời gian thực, lakehouse, trung tâm điều hành/BI, dịch vụ dữ liệu, **quản trị phả hệ dữ liệu**; kho lạnh: lưu trữ lịch sử bất biến, đối soát sổ cái | Báo cáo vận hành đa chi nhánh từ nguồn sự thật Frappe; phả hệ dữ liệu là điểm nhấn sẵn có của DX-OSD: sự kiện theo chuẩn OpenLineage + vết kiểm toán/versioning của Frappe; mục tiêu giảm can thiệp thủ công 80% → dưới 20% đo trên dữ liệu vận hành này | `OpenLineage/OpenLineage` — Apache-2.0 [thứ cấp, chưa mở LICENSE trực tiếp]; `MarquezProject/marquez` — Apache-2.0 [thứ cấp]; `frappe/frappe` — MIT [trực tiếp] | Khớp một phần | Chưa có thành phần BI/dashboard chuyên trách trong danh mục (đề thi nêu Metabase ở lớp tham chiếu 6 — ngoài danh mục, chưa kiểm chứng); lakehouse và kho lạnh bất biến chưa có trong thiết kế. Phần phả hệ dữ liệu là phần khớp nhất của không gian D nhưng mức giấy phép của OpenLineage/Marquez còn ở mức thứ cấp — phải mở LICENSE trên repo gốc trước khi đưa vào hồ sơ |
| **I** — Trí tuệ số | Tìm kiếm toàn văn và tìm kiếm ngữ nghĩa véc-tơ; cổng quản trị/giám sát tác tử AI; OCR; trợ lý ảo trên tri thức nội bộ (RAG) | Lớp Agentic AI của DX-OSD: tác tử tư vấn tuyển sinh/chăm sóc học viên gọi API Chatwoot CE và ghi vết vào phả hệ dữ liệu; rào chắn kiểm tra đầu ra trước khi gửi | `langchain-ai/langgraph` — MIT [**kiểm chứng trực tiếp**]; `crewAIInc/crewAI` — MIT [**kiểm chứng trực tiếp trên LICENSE gốc** 10/10]; `NVIDIA/NeMo-Guardrails` — Apache-2.0 [thứ cấp]; `guardrails-ai/guardrails` — Apache-2.0 [thứ cấp] | **Chưa chốt quyết định** | **Quyết định mở #3 (framework tác tử) chặn dòng này**: LangGraph hay CrewAI — về giấy phép cả hai đều đã rõ là MIT, nên quyết định thuần túy là kỹ thuật (kiểm soát luồng/human-in-the-loop so với tốc độ dựng demo đa tác tử). Chưa chốt thì chưa khóa được kiến trúc tác tử, checkpoint và cách ghi vết. Ngoài ra: tìm kiếm ngữ nghĩa véc-tơ, OCR và RAG trên tri thức nội bộ chưa có thành phần tương ứng đã chốt trong danh mục; giấy phép **trọng số của từng mô hình LLM** phải liệt kê và kiểm tra riêng — giấy phép của framework không suy ra giấy phép của mô hình |

### Bốn nguyên lý thiết kế (đề thi mục 4) — đối chiếu nhanh

| Nguyên lý | Đối chiếu DX-OSD | Trạng thái |
|---|---|---|
| (i) Phân tách chức năng theo vòng đời/tốc độ dữ liệu (giao dịch thời gian thực tách khỏi lưu trữ lịch sử phân tích) | Frappe/MariaDB giữ giao dịch; phần đẩy dữ liệu lịch sử xuống kho phân tích chưa có thành phần chốt (xem khoảng trống không gian D) | Khớp một phần |
| (ii) Hội tụ dữ liệu hành chính (IT) và dữ liệu vận hành (OT), bản sao số thời gian thực | Bài toán trung tâm giáo dục gần như không có dữ liệu cảm biến/OT — nguyên lý này ít đất diễn trong EduFlow; nên trình bày đúng mức là nguyên lý tham chiếu, không ép ánh xạ | Ít áp dụng — ghi rõ khi thuyết trình |
| (iii) Quản trị dữ liệu thế hệ mới: tự động hóa dòng chảy, kiểm soát phả hệ/nguồn gốc/chất lượng trên báo cáo tổng hợp | Đây là nguyên lý DX-OSD khớp mạnh nhất: phả hệ dữ liệu + rào chắn toàn vẹn dữ liệu (“rác đầu vào – rác đầu ra”) là trọng tâm sẵn có của dự án | Khớp theo thiết kế |
| (iv) Zero-Trust gắn với GitOps, kiểm dịch tại biên mạng, hạ tầng tự động bằng mã | Đóng gói Docker/Docker Compose có trong thiết kế; GitOps và kiểm dịch tệp tại biên chưa có thành phần nào trong danh mục 29 repo | Khoảng trống |

---

## 3. Ba quyết định còn mở — vị trí và tác động (không chốt thay)

Kiểm tra lại ngày 11/10/2026: cả ba quyết định **vẫn đang mở**, chưa có quyết định nào được ghi nhận. Mỗi quyết định nằm ở đúng dòng yêu cầu lõi mà nó chặn:

| # | Quyết định | Nằm ở dòng | Tác động nếu chưa chốt |
|---|---|---|---|
| 1 | Giấy phép sản phẩm: **AGPL-3.0 cho toàn bộ** (nếu kết hợp trực tiếp Frappe CRM/LMS/Helpdesk) **hay GPL-3.0 + tách CRM** thành dịch vụ giao tiếp qua API | Dòng xuyên suốt Tầng 1 — giấy phép phát hành; liên quan trực tiếp dòng 1.3 (dữ liệu cấu trúc GPL-3.0) và ứng dụng H (CRM thuộc AGPL-3.0) | Không thể hoàn thiện header giấy phép từng tệp, thông báo giấy phép, SBOM và vòng quét tuân thủ cuối — đúng nhóm PoF 10 điểm và cổng xếp hạng của thể lệ |
| 2 | Thay n8n: **Activepieces** (lõi MIT, phải loại hai thư mục `ee/`) **hay Node-RED** (Apache-2.0) **hay chỉ Frappe Workflow + Scheduler** | Dòng 1.5 — Workflow (Tầng 1); lan sang không gian P (thiết kế quy trình trực quan) | Phần tự động hóa ngầm ngoài Frappe chưa có chủ sở hữu kỹ thuật; n8n đã bị loại vì giấy phép không đạt OSI — không có đường quay lại phương án này |
| 3 | Framework tác tử chính: **LangGraph** (MIT, kiểm soát luồng + human-in-the-loop) **hay CrewAI** (MIT, dựng đa tác tử nhanh) | Không gian **I** (Tầng 2) — cổng quản trị/giám sát tác tử | Chưa khóa được kiến trúc tác tử, cơ chế checkpoint/phê duyệt ngoại lệ và cách ghi vết phả hệ cho hành động của tác tử. Cả hai đều MIT đã kiểm chứng trực tiếp, nên đây là quyết định kỹ thuật thuần túy |

---

## 4. Checklist nộp bài — hạn chót 17:00 Chủ Nhật, ngày 06/12/2026

Quy cách gửi bài lấy từ mục 5 của đề thi chính thức (đọc trực tiếp 11/10/2026); các mục chuẩn bị kho nguồn lấy từ 6 nhóm PoF của thể lệ (50/100 điểm, chấm trừ điểm trên kho nguồn trước chung kết).

### 4.1. Gửi bài (bắt buộc, theo đề thi)

- [ ] Gửi email tới **cả hai** địa chỉ: **olpvietnam@vaip.vn** và **thuky@vfossa.vn**
- [ ] Trước hạn chót: **17:00 Chủ Nhật, ngày 06/12/2026**
- [ ] Tiêu đề thư đúng mẫu: `BÀI THI PMNM 2026 - [Tên Đội] - [Tên Trường]`
- [ ] Nội dung thư gồm: danh sách tối đa 3 thành viên (họ tên, năm sinh, ngành đào tạo); người hướng dẫn (họ tên, Khoa/Viện/Trường); **đường dẫn kho mã nguồn** chứa đầy đủ kết quả dự thi; xác nhận đã đăng ký dự thi đúng quy định thông qua trường; cam kết bản quyền sản phẩm tuân thủ quy tắc phần mềm tự do nguồn mở
- [ ] Đội đã hoàn tất đăng ký dự thi qua trường theo danh sách BTC tiếp nhận (theo lịch thể lệ: tháng 11/2026)

### 4.2. Kho mã nguồn — sẵn sàng cho chấm PoF (07–09/12/2026)

- [ ] Kho công khai trên Internet, có giao diện xem mã qua web và được dùng thật trong suốt quá trình làm bài (nhóm PoF kho nguồn: 5 điểm)
- [ ] Giấy phép sản phẩm đã chốt (quyết định #1) kèm **toàn văn giấy phép** ở gốc kho; header giấy phép/SPDX trong từng tệp mã tự viết; tệp thông báo giấy phép bên thứ ba đầy đủ (nhóm PoF cấp phép: 10 điểm)
- [ ] Ít nhất **một bản phát hành (release) có đánh phiên bản**, tạo **trước** thời điểm nộp bài, đóng gói bằng định dạng mở (nhóm PoF release: 5 điểm)
- [ ] Hướng dẫn cài đặt/dịch từ mã nguồn chạy được — ưu tiên Docker Compose một lệnh; chương trình chạy được ngoài thư mục mã nguồn (nhóm PoF build from source: 10 điểm)
- [ ] Làm rõ thư viện/gói đính kèm, không sửa mã của gói phụ thuộc, tận dụng thư viện sẵn có của hệ thống (nhóm PoF bundling: 10 điểm)
- [ ] README (kiến trúc, cài đặt, demo), CHANGELOG theo phiên bản, và bug tracker được bật, dùng thật (nhóm PoF tài liệu & giao tiếp: 10 điểm)
- [ ] Đã chạy quét tuân thủ giấy phép trên toàn bộ cây mã nguồn và lưu báo cáo + bảng SBOM vào kho làm chứng cứ; mọi thành phần không đạt OSI (điểm tên: thư mục `enterprise/` của Chatwoot, hai thư mục `ee/` của Activepieces nếu dùng, n8n) đã bị loại khỏi sản phẩm nộp

### 4.3. Chung kết (10/12/2026) — chuẩn bị sẵn cùng lúc nộp bài

- [ ] Hệ thống chạy thử nghiệm để trình diễn; đề thi khuyến khích demo vận hành trên môi trường Internet
- [ ] Bài trình bày **15 phút** đủ 4 nội dung theo đề thi: giải pháp thiết kế và lựa chọn công nghệ; tính năng nền tảng và bài toán ứng dụng minh họa; kết quả sản phẩm và trình diễn demo; định hướng phát triển tiếp theo
- [ ] Trao giải: 11/12/2026 (theo thể lệ)

### 4.4. Đề xuất nội bộ của đội (không phải yêu cầu của BTC)

- [ ] Khóa kiến trúc và tạo release ứng viên **trước** hạn nộp vài ngày, để vòng quét giấy phép và kiểm tra build từ nguồn còn thời gian sửa — hạn 06/12 rơi đúng cuối tuần, không nên để lần build sạch đầu tiên vào ngày nộp
- [ ] Chốt ba quyết định ở mục 3 **trước** khi khóa kiến trúc: quyết định #1 chặn khâu giấy phép của kho nguồn, #2 chặn dịch vụ Workflow, #3 chặn không gian I

---

## 5. Phần chưa kiểm chứng — không dùng làm căn cứ khẳng định

1. Giấy phép ở mức **thứ cấp** (chưa mở LICENSE trực tiếp trên repo gốc) của: OpenLineage, Marquez, ScanCode Toolkit, OSS Review Toolkit, FOSSology, Node-RED, NeMo Guardrails, Guardrails AI, Frappe Docker. Phiếu kiểm chứng 10/10/2026 mới nâng lên mức trực tiếp cho: Frappe Framework/ERPNext/CRM/Helpdesk/LMS, Frappe Education, CrewAI, LangGraph và ranh giới `ee/` của Activepieces.
2. Các công nghệ đề thi nêu trong **bảng tham chiếu 7 lớp** (Keycloak, Apache APISIX, MinIO, Metabase, HashiCorp Vault…) nằm **ngoài** danh mục 29 repo của báo cáo — giấy phép và mức phù hợp của chúng chưa được kiểm chứng trong bộ tài liệu này; một số công nghệ tham chiếu có mô hình giấy phép cần soi kỹ trước khi dùng (ví dụ n8n đã bị loại vì lý do này).
3. Trạng thái “khớp theo thiết kế” trong tài liệu này phản ánh kiến trúc đã chọn trong báo cáo 29 repo và hồ sơ dự án — **không** phải kết quả kiểm chứng mã nguồn DX-OSD thực tế. Mức đáp ứng cuối cùng do kho mã nguồn, bản phát hành và buổi demo quyết định.
4. Giấy phép trọng số của từng mô hình LLM sẽ dùng trong demo chưa được liệt kê/kiểm chứng — phải bổ sung vào SBOM trước khi nộp.
