# Proactive Level Test — Design Spec

Decision D-106 (`2026-09-26-edu-lead-engine/decisions.md`). Builds on the level quiz of D-104.

## Purpose

The level quiz only ran when a customer typed "test excel". The owner wants it to hold customers and turn
them into qualified leads:

- Jev chats first, learns what the customer wants, then **offers** a short test for that course when their
  level is unknown.
- The result places the customer in a basic or advanced class.
- A reward (free trial class + voucher) earns the phone number.
- The wording is gentle, cheerful and polite, like a staff member ("Dạ … ạ", "em" / "anh/chị").

Confirmed choices: all four extensions (adaptive quizzes for several course groups; result, reward and
phone; quiz editor and funnel in the admin; reminder for half-way tests and hints for consultants); **show
the result first, then ask the phone**; the reward is **both** a trial class and a voucher.

## Conversation

1. "học excel ở dĩ an bao nhiêu tiền" → the fee, then the next question as today.
2. Next turn, the course is known, the level is not, the quiz was never offered: instead of an optional
   question (or the phone question) the bot says
   "Dạ để em tư vấn đúng lớp hơn, anh/chị làm thử bài test Excel nhỏ 5 câu, chừng 1 phút thôi nhé ạ 😊 Làm
   xong em tặng anh/chị một buổi học thử miễn phí và mã ưu đãi ạ." with **[Làm bài test] [Để sau]**.
   Required questions (branch) are still asked first; handoff and confirmations win.
3. Questions run easy → hard; after a right answer "Dạ chính xác rồi ạ 👏", after a wrong one "câu vừa rồi
   hơi khó, không sao đâu ạ". Two basic questions wrong end the test early.
4. Result: "Dạ anh/chị làm đúng 4/5 câu, giỏi quá ạ 🎉 … em gợi ý khóa Excel nâng cao & Dashboard …", the
   next trial classes of that course as buttons, then the phone question.
5. With the phone: the syllabus of the recommended course and, when a promotion applies, a voucher code
   (`SV-EXCEL-7K3Q`). The usual handoff follows (course + phone = qualified).
6. "Để sau" → "Dạ không sao ạ, khi nào tiện anh/chị cứ nhắn em làm bài test nhé ạ." and the chat goes on;
   the quiz is never offered again in that conversation.
7. A customer who stops half-way gets one reminder 2–20 hours after their last message, with the buttons of
   the question they stopped at.

## Design

### Quiz configuration (`engine/quiz.py`)

`Bot Skill.action_config` of a `level_quiz` skill, compatible with D-104:

```json
{"slot": "quiz_progress", "subject": "Excel", "mode": "test",
 "courses": ["VP-EXCEL", "VP-EXCEL-NC"], "groups": ["Tin học văn phòng"],
 "max_questions": 5, "stop_after_wrong": 2,
 "questions": [{"q": "…", "options": ["…"], "answer": 0, "level": "basic", "topic": "VLOOKUP", "goals": ["office"]}],
 "bands": [{"max": 2, "level": "beginner", "course": "VP-EXCEL"}]}
```

- Still stateless: `quiz_progress` holds the answers so far. The question order is deterministic (filtered
  by the customer's `goal` unless that leaves too few, then sorted basic → intermediate → advanced), so the
  answers alone give the next question, an early stop and the score.
- `mode: survey` (parents of young learners): `points` per option instead of one answer.
- `result` → score, total, level, course, missed topics, stopped early. `quiz_for(skills, course, group)`
  picks the quiz for a course (its own list first, then its group). `validate` checks a configuration.
- Demo: Excel (8 questions, 5 asked), Word, PowerPoint, Photoshop, programming, and a kids survey.

### Offer (`engine/offers.py`, `decide.py`, `reply.py`)

- `quiz_offer`: active conversation, no consultant reply, not the first turn, no placement yet, a quiz for
  the course or group, not in `state.offers`, not already being answered; when the level is already filled
  only if Jev's `level_unsure` ≥ 0.6. The `level_unsure` noul is asked only while an offer is possible.
- `decide` sets `Decision.offer` in place of an optional or phone question; reason "Mời làm bài test Excel
  (chưa rõ trình độ)". `reply.compose` renders `quiz_offer_template` with the two buttons; "Để sau" is the
  button action `offer_decline` → `Decision.declined` → `quiz_decline_template`.
- `Bot Conversation.quiz_offers` (JSON): quiz → offered | declined | started | reminded | done | rewarded.

### Result and reward (`pipeline.py`, `voucher.py`)

- `apply_quiz_results` also fills `quiz_detail` (missed topics), sets `Decision.quiz_done` and asks the phone
  with `quiz_phone_template`. `write_lead` raises `ai_hotness` to at least warm.
- `issue_reward`: a finished quiz and a known phone → syllabus of the recommended course; the best active
  promotion for it gives a voucher `<voucher_prefix>-<SUBJECT>-<4 chars>` (hash of the conversation id,
  so a replayed turn gives the same code) written to the on-demand slot `voucher_code`. Sent once
  (`rewarded`). No promotion → the syllabus only.
- The level quiz's result also carries the recommended course's trial classes as buttons (`trial_offer`).
- New Lead fields `quiz_detail` (Small Text) and `voucher_code` (Data), in the Lead side panel; the handoff
  summary shows "📝 Bài test Excel: 4/5 · Biết cơ bản · cần củng cố: Pivot Table · mã ưu đãi …".

### Attempts, reminder, admin

- DocType `Quiz Attempt` (one per conversation and quiz): status, score, total, level, missed, phone_after,
  voucher_code, offered/started/finished/reminded times, is_sandbox. Written by the pipeline from the change
  in `quiz_offers` (`offers.attempt_changes`); playground rows are marked `is_sandbox` and left out of the
  funnel, scenario runs and replays write nothing.
- `quiz_reminders.run` (cron `*/15`): started, not reminded, not sandbox; the conversation is active, no
  consultant reply, quiet for `quiz_remind_after_hours` (default 2) up to 20 hours. Sends
  `quiz_reminder_template` with the current question's buttons, puts them in `pending`, marks `reminded`.
- `/crm/admin/quizzes` (`quiz_admin.py`, `AdminQuizzes.vue`, `QuizDialog.vue`): funnel cards and charts
  (offered, took it, finished, phone, enrolled, back after a reminder) per 7/30/90/365 days, and the quiz
  editor: subject, mode, questions per test, early stop, groups/courses that trigger the offer, questions
  (options, right answer or points, level, topic, goals), score bands (level + course) and the three bot
  messages. Saving runs `quiz.validate` and `tone.problems`.

### Tone (`engine/tone.py`)

Every customer-facing template (Lead Engine Settings `*_template` except the consultant summary, skill
templates, slot questions) starts with "Dạ" or addresses the customer through `brand.you`, contains "ạ",
never writes "mình", "bạn", "tôi" or "cậu" (use `brand.me` / `brand.you`), and has at most one emoji.
`tests/test_tone.py` checks the demo data; the quiz editor checks what a manager types.

## Understanding replies (D-107)

Found in the owner's live test with Jev: a 9-digit phone was dropped and the hotline answered instead, a parent's
first question fired three skills, typed trial dates and side questions broke the flow, "ok" to the offer was not
understood. Changes:

- `engine/reply_match.py`: a typed message is matched to the buttons the bot just sent (folded title, "a / câu 2",
  "ok / thôi" for the offer, date/weekday/shift for trial classes); Jev's `reply_to_bot` choice covers the rest.
- A quiz waiting for an answer comes back after a side question (at most twice), without praise; an answer that is
  no button asks to pick one. "ok" to a slot question re-asks it; neither counts as not understood.
- One focus per reply: one course list, a quiz asked alongside other skills is offered after them, one button set.
- Names (`person_name`), a phone with a digit missing (`phone_check_template`), the customer's own number never
  answered with the hotline, the customer called by name, and the result names the syllabus line covering a
  missed topic.

## Testing

- Unit: adaptive order, goal filter, early stop, survey, missed topics, `quiz_for`, `validate`; offer
  conditions, decide/compose, "Để sau", tracking; reward and voucher; attempt rows; reminder window and
  job; editor normalisation, problems and funnel; tone of every template.
- Acceptance scenario S19: fee question → offer → test → result → phone → syllabus.
- `yarn build`, eslint; mocked-browser screenshots of the Bài test tab and editor.
- Live (after migrate and the demo loader): the Playground replays the conversation above, with and
  without Jev.
