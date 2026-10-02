# Demo setup: seed the CRM and turn on Jev

For anyone who clones the repo and wants the same demo as ours: 13 Tin Học Sao Việt branches, 51 courses with
classes, 44 consultants, the bot's knowledge and level tests, and sample customers (52 Leads, 15 registrations,
notes, tasks, level-test attempts, Facebook posts with comments).

## 1. Start the stack

```bash
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000   # 200/302
```

First time on a machine: `scripts/quickstart.sh` builds and wires everything and loads the demo by default (`--no-demo` skips it); `TYPESAFE_API_KEY=<key> scripts/quickstart.sh` also sets the Jev key.

## 2. Seed the demo data

```bash
TYPESAFE_API_KEY=<your key> scripts/seed-demo.sh --reset
```

- `--reset` **deletes** every Lead, registration, note, task, bot conversation, Facebook post and all Chatwoot
  conversations/contacts first. Use it on a dev/demo machine only. Staff, catalog and bot setup are kept.
- Without `--reset` the command only adds or updates; running it again creates nothing new and moves the sample
  dates to today, so run it again on the morning of a demo.
- Sample customers are fictional (`@demo.saoviet.invalid` emails). Sample Facebook posts are never "Scheduled", so
  nothing is published to a real page.

Logins after the seed: `admin@eduflow.vn` / `admin123` (CRM and Chatwoot); every consultant signs in to both apps
with their email and `EduFlow@2026`.

## 3. Turn on Jev (required for the AI parts of the demo)

Jev is the TypeSafe model the bot uses to understand free-form messages. **Without a key the bot only answers from
its rules and keywords**: the Playground's **Use Jev**, Jev answers to customers, AI intent/hotness on Leads and the
AI follow-ups stay off, and `seed-demo.sh` prints `Jev is OFF` at the end.

1. Get a TypeSafe API key (ask the project owner; never commit it or paste it into an issue).
2. Pass it to the seed, which stores it in the site config and ticks *Lead Engine Settings › Jev answers real
   customers*:

   ```bash
   TYPESAFE_API_KEY=<your key> scripts/seed-demo.sh
   ```

   Or by hand:

   ```bash
   docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench --site crm.localhost set-config typesafe_api_key "<your key>"
   ```

   then in the CRM: */app/lead-engine-settings* › tick **Jev answers real customers** › Save.
3. Check it:
   - `docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench --site crm.localhost execute mmm_custom.engine.evaluate.run`
     runs the evaluation set and reports the gate (it calls Jev, so it uses tokens);
   - `/crm/admin/playground`: tick **Use Jev**, send "mình muốn học excel buổi tối ở bình thạnh" and the inspector
     shows Jev's questions, answers and tokens.

Optional site config: `typesafe_model` (default `jev-latest`), `typesafe_api_url`. Cost guards live in Lead Engine
Settings: *Jev calls per conversation per hour* (default 20) and *Daily input-token budget* (0 = unlimited).

To turn Jev off again: untick **Jev answers real customers** (the Playground can still force it per test), or
remove the key with `bench --site crm.localhost set-config typesafe_api_key ""`.
