# Glossary

| Term | Vietnamese | Meaning in this spec |
|---|---|---|
| Lead | Khách tiềm năng | A CRM Lead record; one per real person (dedup) |
| Deal | Cơ hội / Ghi danh | CRM Deal created when a lead enrols (C7.1) |
| Area | Khu vực | Group node in CRM Territory (TP.HCM, Bình Dương, Đồng Nai, Vũng Tàu) |
| Branch | Chi nhánh / Cơ sở | Leaf node in CRM Territory; stored on Lead as `territory` |
| Course group | Nhóm khóa | e.g. Tin học văn phòng, Kế toán; consultants specialise by group |
| Course | Khóa học | A CRM Product with education custom fields; `standard_rate` = listed fee |
| Course schedule | Lịch khai giảng | One course × branch × start date × shift |
| Consultant | Tư vấn viên | CRM `Consultant` DocType linked to a CRM User and a Chatwoot agent |
| Team lead | Trưởng nhóm | Consultant level that receives hot leads (rule D) |
| Central team | Tổng đài / bộ phận trung tâm | Last-resort routing target |
| Slot | Ô thông tin | A fact the bot needs: area, branch, course group, course, phone |
| Slot filling | Điền ô | Ask only for slots still missing; Jev may fill several from one message |
| Bot Skill | Kỹ năng của bot | Something the bot can do when a customer asks (answer fees, list schedules, recommend courses, send certificate-lookup link…): Jev description + parameters (slots) + action type + templates (D-035) |
| Answer template | Mẫu câu trả lời | Jinja text filled with CRM data; the only source of bot wording |
| Confidence bands | Vùng tin cậy | Act / confirm / fall back, with per-decision thresholds in `Lead Engine Settings` (D-030); `intelligence.py` keeps its single 0.7 gate |
| Handoff | Chuyển người | Bot sets conversation `open` and assigns a consultant with a summary note |
| Hotness | Độ nóng | cold / warm / hot, from Jev `score` |
| Intent | Ý định | purchase, price_inquiry, support, complaint, spam, other (Jev `choice`) |
| Bot Conversation | Phiên hội thoại bot | Per-conversation state: filled slots, pending question/options, status (D-024) |
| Playground | Sân thử | CRM page to simulate a message and see every step of the engine (D-038) |
| Learning signal | Tín hiệu học | A rejected confirmation, a consultant correction or an unmatched term, kept as future evaluation data / alias proposal (D-043) |
| AI Decision Log | Nhật ký quyết định AI | One record per automated decision: input, Jev answers + confidence, action, reason |
| Dashboard App | Khung bên cạnh chat | Chatwoot feature that embeds a URL beside each conversation |
| Jev / System One | — | TypeSafe decision model; question types `choice`, `score`, `noul`; no text generation |
| H-P-D-I | — | DX-OS layers: Human, Process, Data, Intelligence (see `README.md` at repo root) |
