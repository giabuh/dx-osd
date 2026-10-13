# Conversational AI Experience & Memory: Typing Indicator, Rich Media, Long-Term Memory, and Zero-Stall Resilience — Design Spec

Sub-project 1 of the DX-OSD OLP 2026 Tournament Upgrade (VFOSSA DX-OS HPDI Architecture).

## Purpose

Upgrade the DX-OSD conversational bot to a production-ready, tournament-grade experience for the Olympic Tin học Sinh viên (OLP) 2026 - Khối Phần mềm Nguồn mở (PMNM):
- **Typing Indicator (`typing_on`):** Simulate human typing so prospects see the active typing status on Facebook Messenger and Chatwoot inbox before receiving replies.
- **Rich Media Responses:** Provide visual course posters, syllabus overviews, and branch photos alongside pricing and course details.
- **Long-Term Contact Memory:** Recognize returning prospects (`is_returning = True`), greet them warmly by name, recall previous course/branch interest, and avoid re-asking already known information (phone, email, branch).
- **Zero-Stall Latency Control & Fallback:** Enforce a strict 2.5-second timeout on external AI/LLM calls with seamless fallback to verified CRM rule-based templates, guaranteeing sub-second response times without duplicate messages.

## What changes

1. **Typing Status Control (`mmm_custom.chatwoot_client.ChatwootClient`)**:
   - Add `toggle_typing(conversation_id, typing_status="on"|"off")` calling `POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_typing_status`.
   - Add `send_attachment(conversation_id, file_path_or_url, content)` or multipart attachment support in `send_message`.

2. **Typing Simulation & Attachment Dispatch (`mmm_custom.engine.effects`)**:
   - In `ChatwootEffects.send(conversation_id, reply)`:
     - Activate `toggle_typing(conversation_id, "on")` prior to emitting responses.
     - Calculate natural typing delay: `delay = min(2.5, max(1.5, len(reply_text) * 0.012))` seconds.
     - If `reply.attachments` contains image resources, dispatch the image card/attachment first or with the primary message.
     - `RecordingEffects` tracks typing toggles and attachments for unit tests.

3. **Rich Media Attachment Generation (`mmm_custom.engine.reply`)**:
   - When the bot presents a specific course (overview, fees, schedule, or quick-reply selection), check for an available course image (`CRM Product.image` or local image catalog under `public/images/courses/`).
   - Append `{"type": "image", "url": course_image_url, "title": course.name}` to `reply.attachments`.

4. **Long-Term Memory & Zero-Redundancy Dialogue (`mmm_custom.engine.repo` & `context`)**:
   - `repo.new_state` checks existing `CRM Lead` and prior `Bot Conversation` records for the contact.
   - If found, marks `state.is_returning = True` and loads:
     - `customer.name`: Customer's registered name / salutation.
     - `customer.previous_course`: Last inquired course from `CRM Lead.products` or `course_interest`.
     - `customer.previous_branch`: Preferred branch from `CRM Lead.territory`.
     - Prefills known slots (`phone`, `branch`) so the dialogue flow skips re-asking them.
   - Default greeting templates in `Lead Engine Settings` include returning customer variants recognizing past interactions.

5. **Zero-Stall AI Timeout & Guaranteed Idempotency (`mmm_custom.engine.jev` & `pipeline`)**:
   - Wrap LLM HTTP calls with a hard `timeout=2.5` seconds.
   - On timeout or HTTP 429 / network errors, catch immediately and return `JevResult("timeout_fallback")`.
   - Pipeline instantly falls back to keyword-based entity understanding and CRM catalog templates (< 5ms execution).
   - Once a turn completes for a `message_id`, `state.last_message_id` is updated and Redis lock is released; no delayed retry or duplicate message is ever sent.

## Out of scope

- AI video understanding and dynamic zoom (Sub-project 3).
- Platform-specific prompt skill registry and Admin Agent UI (Sub-project 4).
- Lead nurturing drip sequence and automated rebalancing (Sub-project 2).

## Verification

- **Unit tests** (`frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`):
  - Test typing toggle invocation on `ChatwootClient` and `RecordingEffects`.
  - Test natural typing delay calculation bounds (between 1.5s and 2.5s).
  - Test course image attachment generation when selecting/inquiring courses.
  - Test returning customer detection, memory prefill, and zero-redundancy slot handling.
  - Test AI 2.5s timeout handling and instant CRM fallback.
- **Regression suite**: Full test suite passes (`python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v`).
