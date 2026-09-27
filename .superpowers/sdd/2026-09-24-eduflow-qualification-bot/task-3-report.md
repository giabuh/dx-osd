# Task 3 Report: Bot Webhook Endpoint + CRM Integration

## Status: DONE

## Commit
`7445cac` — `feat(bot): add webhook endpoint with CRM lead integration and agent assignment`

## Files Changed
| File | Action |
|------|--------|
| `frappe-custom/mmm_custom/mmm_custom/bot_api.py` | Created (275 lines) |
| `frappe-custom/mmm_custom/mmm_custom/setup.py` | Modified — added `branch` custom field + `Messenger Bot` lead source |
| `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py` | Created (6 tests) |

## What was implemented

### `bot_api.py` — Frappe whitelist webhook endpoint
- **`agent_bot_webhook()`** — `@frappe.whitelist(allow_guest=True)` endpoint at `mmm_custom.bot_api.agent_bot_webhook`
  - HMAC-SHA256 signature validation with 300s anti-replay window (`_verify_hmac`)
  - Filters: only processes `message_created` events with `message_type=0` (incoming from customer)
  - Reads `bot_state` and `bot_courses` from Chatwoot contact `custom_attributes`
  - Calls `bot_engine.transition()` to compute next state
  - Sends Quick Reply or plain text responses via `ChatwootClient`
  - Updates contact `custom_attributes` with new state
  - On `completed` state transition: creates/updates CRM Lead, assigns human agent, toggles conversation to `open`
- **`_find_best_agent()`** — branch-filtered round-robin agent selection by fewest open conversations
- **`_create_or_update_lead()`** — dedup-aware CRM Lead creation: checks `crm_lead_id` in custom attrs → `find_matching_lead()` → new insert; writes `crm_lead_id` back to Chatwoot

### `setup.py` modifications
- Added `branch` Select custom field on CRM Lead (options: CS1 Bình Thạnh, CS2 Quận 1, CS3 Thủ Đức), inserted after `course_interest`
- Added `"Messenger Bot"` to `create_lead_sources()` tuple

## Test command + output

```
> python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v

test_chatwoot_writeback_failure_handled_gracefully (test_api) ... ok
test_create_new_lead_when_no_match (test_api) ... ok
test_create_new_lead_with_course_interest (test_api) ... ok
test_detect_course_interest_various_keywords (test_api) ... ok
test_existing_crm_lead_id_in_crm (test_api) ... ok
test_existing_lead_updates_course_interest (test_api) ... ok
test_expired_timestamp_past_raises (test_api) ... ok
test_future_timestamp_expired_raises (test_api) ... ok
test_invalid_hmac_signature_raises (test_api) ... ok
test_invalid_json_body_returns_error (test_api) ... ok
test_invalid_timestamp_string_raises (test_api) ... ok
test_matched_lead_by_email_or_phone (test_api) ... ok
test_missing_timestamp_raises (test_api) ... ok
test_non_conversation_created_event_ignored (test_api) ... ok
test_valid_hmac_signature_passes (test_api) ... ok
test_valid_hmac_signature_without_sha256_prefix (test_api) ... ok
test_branch_selection_triggers_handoff (test_bot_api) ... ok
test_completed_state_is_noop (test_bot_api) ... ok
test_greeting_sends_course_quick_replies (test_bot_api) ... ok
test_invalid_hmac_rejected (test_bot_api) ... ok
test_non_message_created_event_ignored (test_bot_api) ... ok
test_outgoing_message_ignored (test_bot_api) ... ok
test_await_branch_invalid_input_resends_menu (test_bot_engine) ... ok
test_await_branch_valid_selection_completes (test_bot_engine) ... ok
test_await_course_all_three_selected_auto_transitions (test_bot_engine) ... ok
test_await_course_done_token_transitions_to_branch (test_bot_engine) ... ok
test_await_course_duplicate_selection_ignored (test_bot_engine) ... ok
test_await_course_invalid_input_resends_menu (test_bot_engine) ... ok
test_await_course_second_selection (test_bot_engine) ... ok
test_await_course_valid_selection_adds_and_offers_more (test_bot_engine) ... ok
test_completed_state_returns_noop (test_bot_engine) ... ok
test_greeting_any_message_sends_course_menu (test_bot_engine) ... ok
test_greeting_empty_state_treated_as_greeting (test_bot_engine) ... ok
test_fields_exist (test_bot_engine) ... ok
test_assign_conversation (test_chatwoot_client) ... ok
test_auth_header_included (test_chatwoot_client) ... ok
test_list_agent_conversations (test_chatwoot_client) ... ok
test_list_agents (test_chatwoot_client) ... ok
test_send_message_plain_text (test_chatwoot_client) ... ok
test_send_quick_replies (test_chatwoot_client) ... ok
test_toggle_status (test_chatwoot_client) ... ok
test_update_contact (test_chatwoot_client) ... ok
test_build_search_filters (test_dedupe) ... ok
test_build_search_filters_empty (test_dedupe) ... ok
test_find_matching_lead_found (test_dedupe) ... ok
test_find_matching_lead_no_filters (test_dedupe) ... ok
test_find_matching_lead_not_found (test_dedupe) ... ok
test_find_matching_lead_without_frappe (test_dedupe) ... ok
test_normalize_phone_vn (test_dedupe) ... ok
----------------------------------------------------------------------
Ran 49 tests in 0.030s
OK
```

**49/49 tests pass.** Zero failures, zero errors.
