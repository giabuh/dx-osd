### MMM Custom

Chatwoot ↔ Frappe CRM integration for DX-OSD: webhook sync with dedup, agent bot, data quality, custom fields, and optional AI agents.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app mmm_custom
```

### AI agents (optional)

The DX-OS **[I] Intelligence** layer: two agents on [TypeSafe Jev](https://docs.typesafe.ai), a hosted decision model that returns choices/scores with a confidence instead of generated text. An agent acts only when Jev's confidence is at least the threshold (default `0.7`); below it, nothing changes. Both are off until an API key is set — the rest of the app never depends on them.

| Agent | Runs | Does |
|---|---|---|
| `intelligence.analyze_conversation` | Background job for every incoming message (`message_created` on the Chatwoot webhook) | Sets `ai_intent` (`purchase`, `price_inquiry`, `support`, `complaint`, `spam`, `other`) and `ai_hotness` (`cold`, `warm`, `hot`) on the Lead; fills a missing phone/email that the customer typed in the chat (and, if another Lead has it, adds a "Possible duplicate" note and the `Nghi trùng` data-quality flag — never a merge); labels the conversation (`ai-<intent>`, `hot`); posts the best reply template as a private note (never for spam) |
| `followup.run_daily` | 08:00 site time (`scheduler_events`) | For open Leads with no change in 3 days, picks `call` / `message` / `review_close` / `wait` and creates a CRM Task for the Lead owner; skips Leads that already have an open Task; never changes the Lead |

Enable (site config; keep the key out of git):

```bash
bench --site crm.localhost set-config typesafe_api_key "<key from https://console.typesafe.ai/keys>"
bench --site crm.localhost set-config chatwoot_api_token "<Chatwoot access token>"   # already set if you ran scripts/configure-chatwoot.py
```

Optional keys: `typesafe_confidence_threshold` (0.7), `typesafe_model` (`jev-latest`), `ai_reply_templates` (JSON object of `key: text`, replaces the built-in Vietnamese templates), `ai_followup_stale_days` (3), `ai_followup_statuses` (`["New", "Contacted", "Nurture"]`), `ai_followup_max_leads` (20), `chatwoot_account_id` (1).

The Chatwoot webhook must subscribe to `message_created` (`scripts/configure-chatwoot.py` does). If the first message arrives before the conversation webhook has created the Lead, the job waits for it (4 s, 8 s, 16 s) before giving up, and it never calls Jev without a Lead. Jev is strongest in English; on 10 hand-labelled Vietnamese chats every wrong answer came back below 0.7 — check real chats before lowering the threshold.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/mmm_custom
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
