# Comment funnel: from a post comment to a Lead that knows its post — Design Spec

Decision D-122 (`2026-09-26-edu-lead-engine/decisions.md`). Organic posts only (no paid ads).

## Purpose

The pieces existed but were not joined:

- `scripts/comment-reply.py` answers every comment the same way (public reply + private reply), with offers
  hard-coded in its prompts (30 % in one, 35 % in another), its state in `.replied_*.json` files, and it runs
  outside the bench.
- `Facebook Post.sync_comments` classifies comments with its own keyword list, only for display.
- `Facebook Post.leads_count` counts FCRM Notes whose text contains the post id — nothing writes such a note,
  so a post never shows the Leads it brought.
- The level test (D-106) only starts when a customer types its keyword in Messenger.

## What changes

1. **One classifier** (`mmm_custom/comment_funnel.classify`): `quiz` (a level-test keyword of the post's
   course, or "test" / "kiểm tra trình độ"), `price`, `interest`, `praise`, `other`. `Facebook Post.sync_comments`
   uses it for its `sentiment` column.
2. **Action per intent** (`plan`): quiz / price / interest → public reply + private reply; praise → public
   thanks only; other (spam, tags, emoji) → nothing. A private reply is only sent while Facebook allows it
   (comment younger than 7 days, one per comment).
3. **Messages from CRM data, in the house tone (D-106)**: templates in Lead Engine Settings defaults
   (`comment_public_template`, `comment_thanks_template`, `comment_private_template`), rendered with the
   post's course (name, fee), the best active `Course Promotion` for it (title, fee after it) and the
   course's level-test keyword. No AI and no hard-coded offer. The private reply asks the customer to answer
   in Messenger; from that answer on, Chatwoot and the bot (Jev) lead the chat as for any Messenger customer.
4. **In-bench job** `comment_funnel.run` every 5 minutes, off unless site config `comment_funnel_enabled` is
   set. Each handled comment is a `Facebook Comment Reply` row (unique `comment_id`): inserting the row claims
   the comment, so two runs never answer twice. The row keeps the intent, both replies, the status and the
   customer's page-scoped id (`psid`, returned by the private-reply call).
5. **Attribution**: Chatwoot's Facebook contact inbox `source_id` is that same psid. On `conversation_created`
   and on each incoming `message_created`, `api.chatwoot_sync` calls `comment_funnel.attribute`: a reply row
   with that psid and no Lead yet gets the Lead, and the Lead gets `facebook_post` (new read-only Link field)
   and `source_campaign` = "Bình luận: <post title>" when empty (first touch, D-100).
6. **Post results**: `sync_analytics` counts `leads_count` from Leads whose `facebook_post` is the post and a
   new `registrations_count` from those Converted (D-116); the marketing overview sums both.

`scripts/comment-reply.py` is unchanged. Enabling the in-bench job and running the script's comment mode
together would answer comments twice: run the script with `--messenger-only` or not at all.

## Out of scope

Paid ads, Conversions API, A/B tests, changing the weekly planner from these numbers.

## Verification

- Unit tests (`tests/test_comment_funnel.py`): classifier, plan, rendered texts pass `tone.problems`,
  comment handling with fake senders (claim, skip, private window, psid kept), attribution helpers.
- Bench: `bench --site crm.localhost migrate`; `comment_funnel.run(dry_run=True)` against the live page
  lists what it would answer without sending anything.
