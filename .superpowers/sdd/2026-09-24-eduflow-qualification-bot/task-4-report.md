# Task 4 Report: Agent Bot Setup Script + End-to-End Wiring + Documentation

## Status: DONE

## Commit
`f380cbb` — `feat(bot): add agent bot setup script and documentation` (amended)

## Files Changed
| File | Action |
|------|--------|
| `scripts/setup-agent-bot.py` | Created (158 lines) |
| `ROADMAP.md` | Modified — added bot milestone under Phase 0 deliverables |
| `AGENTS.md` | Modified — added bot test command under Commands |

## What was implemented

### 1. `scripts/setup-agent-bot.py`
- Automated one-time setup connecting Chatwoot and Frappe CRM:
  - Finds or creates the `EduFlow Qualification Bot` Agent Bot in Chatwoot with target URL `http://host.docker.internal:8000/api/method/mmm_custom.bot_api.agent_bot_webhook`.
  - Generates or retrieves a 32-byte hexadecimal webhook secret for HMAC-SHA256 signature validation.
  - Links the Agent Bot to the Facebook Messenger inbox (`inbox_id: 2`, `Channel::FacebookPage`) with `:active` status.
  - Generates or retrieves an API access token for the bot.
  - Configures Frappe CRM site config on `crm.localhost`:
    - `chatwoot_bot_webhook_secret`
    - `chatwoot_bot_api_token`
    - `chatwoot_bot_account_id`
    - `chatwoot_base_url`
  - Runs `mmm_custom.setup.setup` inside the Frappe bench to ensure custom fields (`branch`, `course_interest`, `chatwoot_contact_id`) and lead sources (`Messenger Bot`, `Messenger`, `Instagram`) exist.

### 2. Live Stack Verification
- Executed `python scripts/setup-agent-bot.py` successfully:
  - Chatwoot: Bot ID 1 ("EduFlow Qualification Bot") linked to Inbox 2 ("EduFlow Messenger").
  - Frappe CRM: Site config values saved to `crm.localhost`.
  - Bench: Custom fields and lead sources created/updated.
- Executed Frappe setup command directly:
  - `docker compose -f crm/docker/docker-compose.yml -f crm/docker/docker-compose.override.yml exec -T frappe bench --site crm.localhost execute mmm_custom.setup.setup` succeeded with code 0.

### 3. Documentation Updates
- `ROADMAP.md`: Added conversational bot qualification and round-robin agent assignment milestone under Phase 0 deliverables.
- `AGENTS.md`: Added Bot Engine Tests section to the Commands documentation.

## Test Results

```
> python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v

test_chatwoot_writeback_failure_handled_gracefully (test_api.TestChatwootSyncApi.test_chatwoot_writeback_failure_handled_gracefully) ... ok
test_create_new_lead_when_no_match (test_api.TestChatwootSyncApi.test_create_new_lead_when_no_match) ... ok
test_create_new_lead_with_course_interest (test_api.TestChatwootSyncApi.test_create_new_lead_with_course_interest) ... ok
test_detect_course_interest_various_keywords (test_api.TestChatwootSyncApi.test_detect_course_interest_various_keywords) ... ok
test_existing_crm_lead_id_in_crm (test_api.TestChatwootSyncApi.test_existing_crm_lead_id_in_crm) ... ok
test_existing_lead_updates_course_interest (test_api.TestChatwootSyncApi.test_existing_lead_updates_course_interest) ... ok
test_expired_timestamp_past_raises (test_api.TestChatwootSyncApi.test_expired_timestamp_past_raises) ... ok
test_future_timestamp_expired_raises (test_api.TestChatwootSyncApi.test_future_timestamp_expired_raises) ... ok
test_invalid_hmac_signature_raises (test_api.TestChatwootSyncApi.test_invalid_hmac_signature_raises) ... ok
test_invalid_json_body_returns_error (test_api.TestChatwootSyncApi.test_invalid_json_body_returns_error) ... ok
test_invalid_timestamp_string_raises (test_api.TestChatwootSyncApi.test_invalid_timestamp_string_raises) ... ok
test_matched_lead_by_email_or_phone (test_api.TestChatwootSyncApi.test_matched_lead_by_email_or_phone) ... ok
test_missing_timestamp_raises (test_api.TestChatwootSyncApi.test_missing_timestamp_raises) ... ok
test_non_conversation_created_event_ignored (test_api.TestChatwootSyncApi.test_non_conversation_created_event_ignored) ... ok
test_valid_hmac_signature_passes (test_api.TestChatwootSyncApi.test_valid_hmac_signature_passes) ... ok
test_valid_hmac_signature_without_sha256_prefix (test_api.TestChatwootSyncApi.test_valid_hmac_signature_without_sha256_prefix) ... ok
test_branch_selection_triggers_handoff (test_bot_api.TestBotApiWebhook.test_branch_selection_triggers_handoff) ... ok
test_completed_state_is_noop (test_bot_api.TestBotApiWebhook.test_completed_state_is_noop) ... ok
test_greeting_sends_course_quick_replies (test_bot_api.TestBotApiWebhook.test_greeting_sends_course_quick_replies) ... ok
test_invalid_hmac_rejected (test_bot_api.TestBotApiWebhook.test_invalid_hmac_rejected) ... ok
test_non_message_created_event_ignored (test_bot_api.TestBotApiWebhook.test_non_message_created_event_ignored) ... ok
test_outgoing_message_ignored (test_bot_api.TestBotApiWebhook.test_outgoing_message_ignored) ... ok
test_await_branch_invalid_input_resends_menu (test_bot_engine.TestBotEngineTransitions.test_await_branch_invalid_input_resends_menu) ... ok
test_await_branch_valid_selection_completes (test_bot_engine.TestBotEngineTransitions.test_await_branch_valid_selection_completes) ... ok
test_await_course_all_three_selected_auto_transitions (test_bot_engine.TestBotEngineTransitions.test_await_course_all_three_selected_auto_transitions) ... ok
test_await_course_done_token_transitions_to_branch (test_bot_engine.TestBotEngineTransitions.test_await_course_done_token_transitions_to_branch) ... ok
test_await_course_duplicate_selection_ignored (test_bot_engine.TestBotEngineTransitions.test_await_course_duplicate_selection_ignored) ... ok
test_await_course_invalid_input_resends_menu (test_bot_engine.TestBotEngineTransitions.test_await_course_invalid_input_resends_menu) ... ok
test_await_course_second_selection (test_bot_engine.TestBotEngineTransitions.test_await_course_second_selection) ... ok
test_await_course_valid_selection_adds_and_offers_more (test_bot_engine.TestBotEngineTransitions.test_await_course_valid_selection_adds_and_offers_more) ... ok
test_completed_state_returns_noop (test_bot_engine.TestBotEngineTransitions.test_completed_state_returns_noop) ... ok
test_greeting_any_message_sends_course_menu (test_bot_engine.TestBotEngineTransitions.test_greeting_any_message_sends_course_menu) ... ok
test_greeting_empty_state_treated_as_greeting (test_bot_engine.TestBotEngineTransitions.test_greeting_empty_state_treated_as_greeting) ... ok
test_fields_exist (test_bot_engine.TestTransitionResultDataclass.test_fields_exist) ... ok
test_assign_conversation (test_chatwoot_client.TestChatwootClient.test_assign_conversation) ... ok
test_auth_header_included (test_chatwoot_client.TestChatwootClient.test_auth_header_included) ... ok
test_list_agent_conversations (test_chatwoot_client.TestChatwootClient.test_list_agent_conversations) ... ok
test_list_agents (test_chatwoot_client.TestChatwootClient.test_list_agents) ... ok
test_send_message_plain_text (test_chatwoot_client.TestChatwootClient.test_send_message_plain_text) ... ok
test_send_quick_replies (test_chatwoot_client.TestChatwootClient.test_send_quick_replies) ... ok
test_toggle_status (test_chatwoot_client.TestChatwootClient.test_toggle_status) ... ok
test_update_contact (test_chatwoot_client.TestChatwootClient.test_update_contact) ... ok
test_build_search_filters (test_dedupe.TestDedupeLogic.test_build_search_filters) ... ok
test_build_search_filters_empty (test_dedupe.TestDedupeLogic.test_build_search_filters_empty) ... ok
test_find_matching_lead_found (test_dedupe.TestDedupeLogic.test_find_matching_lead_found) ... ok
test_find_matching_lead_no_filters (test_dedupe.TestDedupeLogic.test_find_matching_lead_no_filters) ... ok
test_find_matching_lead_not_found (test_dedupe.TestDedupeLogic.test_find_matching_lead_not_found) ... ok
test_find_matching_lead_without_frappe (test_dedupe.TestDedupeLogic.test_find_matching_lead_without_frappe) ... ok
test_normalize_phone_vn (test_dedupe.TestDedupeLogic.test_normalize_phone_vn) ... ok

----------------------------------------------------------------------
Ran 49 tests in 0.027s

OK
```

**49/49 tests pass.** Zero failures, zero errors.

## Review Fixes Applied

### Fix: Redacted Plain-Text Secret & Token Output in `scripts/setup-agent-bot.py`
- **Issue**: `print(output)` dumped raw Ruby runner output to stdout, leaking `BOT_SECRET` and `BOT_TOKEN` in plain text prior to the masked summary banner.
- **Resolution**: Filtered stdout parsing in `main()` to skip lines containing `BOT_SECRET` or `BOT_TOKEN`. All required output lines (`SUCCESS`, `BOT_ID`, `BOT_NAME`, `INBOX_NAME`, `OUTGOING_URL`) are displayed, while secrets and tokens are only displayed masked in the summary banner.
- **Verification**: Re-executed `python scripts/setup-agent-bot.py` verifying no plain-text secret output. Re-ran test suite (`49/49 passed`). Amended commit to `f380cbb`.
