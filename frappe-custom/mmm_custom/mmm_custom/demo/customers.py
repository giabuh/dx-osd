"""Sample customers for the demo CRM (spec 2026-10-01-demo-seed-design.md): 52 Leads, 15 registrations, notes, tasks,
level-test attempts and Facebook posts with comments, from `saoviet/customers.json`.

Run: bench --site crm.localhost execute mmm_custom.demo.customers.seed      (idempotent)
     bench --site crm.localhost execute mmm_custom.demo.customers.reset     (DESTRUCTIVE, dev/demo only)

Dates in the data are day offsets from the run day. Registrations go through the real hooks (`mmm_custom.enrolment`,
`mmm_custom.lifecycle`): a Lead is never written as Converted, the registration moves it. The pure helpers at the top
need no Frappe and are unit-tested offline.
"""

import json
import zlib
from datetime import date, datetime, time, timedelta
from pathlib import Path

try:
	import frappe
except ImportError:  # offline tests
	frappe = None

DATA_DIR = Path(__file__).resolve().parent / "saoviet"
EMAIL_DOMAIN = "@demo.saoviet.invalid"
CONVERSATION_PREFIX = "demo-"
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
LEAD_STATUSES = ("New", "Qualified", "Contacted", "Trial Booked", "Nurture", "Converted", "Unqualified", "Junk")
DEAL_FINALS = ("awaiting", "pending", "deposit", "won", "lost")
POST_STATUSES = ("Posted", "Pending Approval", "Draft")  # never Scheduled: the publisher would post it for real
SENTIMENTS = ("Quan tâm khóa học", "Hỏi học phí / lịch", "Tích cực", "Spam / Khác")
DEPOSIT_SHARE = 0.3


# ---------------------------------------------------------------- pure helpers

def load_data(root=DATA_DIR):
	return json.loads((Path(root) / "customers.json").read_text(encoding="utf-8"))


def day_from(today, offset):
	"""The date `offset` days from `today` (negative = past)."""
	return today + timedelta(days=offset)


def stamp(today, days_ago, key, early=False):
	"""A stable time on the day `days_ago` days before `today`: the clock part comes from `key`, so a re-run on the
	same day gives the same value and a later day moves it with the calendar."""
	seed = zlib.crc32(str(key).encode())
	hour = 7 + seed % 3 if (early or days_ago <= 0) else 8 + seed % 13
	return datetime.combine(today - timedelta(days=days_ago), time(hour, (seed // 13) % 60))


def pick_class(schedules, today):
	"""The first open class that has not started yet (else the latest one) from rows {name, start_date, status}."""
	def start(row):
		value = row["start_date"]
		return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])

	rows = sorted((r for r in schedules if r.get("status", "Open") == "Open"), key=start)
	upcoming = [r for r in rows if start(r) >= today]
	chosen = upcoming[0] if upcoming else (rows[-1] if rows else None)
	return chosen["name"] if chosen else ""


def branch_consultants(consultants, branch):
	"""Emails of the consultants of one branch, in file order."""
	return [c["email"] for c in consultants if c.get("branch") == branch]


def deposit_for(final_fee):
	"""The deposit a sample registration paid: about 30% of the fee, rounded to 10.000đ."""
	return round(float(final_fee or 0) * DEPOSIT_SHARE / 10000) * 10000


def day_of_week(day):
	return WEEKDAYS[day.weekday()]


def conversation_id(email):
	return CONVERSATION_PREFIX + email.split("@")[0]


def catalog_of(dataset):
	"""What the customer data is checked against: {branches: {name: tier}, courses: {code: offer}, consultants:
	{email: branch}, quizzes: {skill_key}, sources, lost_reasons}. `dataset` is `loader.load_dataset()`."""
	return {
		"branches": {b["territory_name"]: b["tier"] for a in dataset["areas"]["areas"] for b in a["branches"]},
		"courses": {c["product_code"]: c["offer"] for c in dataset["courses"]},
		"consultants": {p["email"]: p["branch"] for p in dataset["consultants"]},
		"quizzes": {s["skill_key"] for s in dataset["bot_skills"] if s["action_type"] == "level_quiz"},
	}


def validate_data(data, catalog):
	"""Problems of the customer data against the catalog: a list of readable strings, empty when it is sound."""
	errors = []
	leads = data["leads"]
	emails = [l["email"] for l in leads]
	phones = [l["mobile_no"] for l in leads]
	if len(set(emails)) != len(emails):
		errors.append("duplicate Lead emails")
	if len(set(phones)) != len(phones):
		errors.append("duplicate Lead phones")
	by_email = {l["email"]: l for l in leads}
	for l in leads:
		who = l["email"]
		if not who.endswith(EMAIL_DOMAIN):
			errors.append(f"{who}: email must end with {EMAIL_DOMAIN}")
		tier = catalog["branches"].get(l["branch"])
		if tier is None:
			errors.append(f"{who}: unknown branch {l['branch']}")
		if catalog["consultants"].get(l["lead_owner"]) != l["branch"]:
			errors.append(f"{who}: owner {l['lead_owner']} is not a consultant of {l['branch']}")
		if l["status"] not in LEAD_STATUSES:
			errors.append(f"{who}: unknown status {l['status']}")
		if not l["courses"]:
			errors.append(f"{who}: no course")
		for code in l["courses"]:
			offer = catalog["courses"].get(code)
			if offer is None:
				errors.append(f"{who}: unknown course {code}")
			elif offer == "full" and tier != "full":
				errors.append(f"{who}: {code} is not offered at {l['branch']}")
		if l["status"] in ("Unqualified", "Junk") and not l.get("lost_reason"):
			errors.append(f"{who}: lost status without a reason")
	deal_leads = [d["lead"] for d in data["deals"]]
	if len(set(deal_leads)) != len(deal_leads):
		errors.append("more than one registration for a Lead")
	for d in data["deals"]:
		if d["lead"] not in by_email:
			errors.append(f"registration of unknown Lead {d['lead']}")
		if d["final"] not in DEAL_FINALS:
			errors.append(f"{d['lead']}: unknown registration status {d['final']}")
		elif d["final"] in ("pending", "deposit", "won") and by_email.get(d["lead"], {}).get("status") != "Converted":
			errors.append(f"{d['lead']}: a confirmed registration needs a Converted Lead")
	for ref, rows in (("note", data["notes"]), ("task", data["tasks"]), ("quiz attempt", data["quiz_attempts"])):
		for r in rows:
			if r.get("lead") not in by_email:
				errors.append(f"{ref} of unknown Lead {r.get('lead')}")
	for r in data["tasks"]:
		if r.get("assigned_to") and r["assigned_to"] not in catalog["consultants"]:
			errors.append(f"task {r['title']}: unknown assignee {r['assigned_to']}")
	for r in data["quiz_attempts"]:
		if r["quiz"] not in catalog["quizzes"]:
			errors.append(f"quiz attempt: unknown quiz {r['quiz']}")
	titles = {p["title"] for p in data["posts"]}
	for p in data["posts"]:
		if p["status"] not in POST_STATUSES:
			errors.append(f"post {p['title']}: status {p['status']} is not allowed in the sample")
		if p["course"] not in catalog["courses"]:
			errors.append(f"post {p['title']}: unknown course {p['course']}")
		if p["status"] == "Posted" and not str(p.get("fb_post_id", "")).startswith("demo-"):
			errors.append(f"post {p['title']}: fb_post_id must start with demo-")
	for c in data["comments"]:
		if c["post"] not in titles:
			errors.append(f"comment {c['comment_id']}: unknown post")
		if c["sentiment"] not in SENTIMENTS:
			errors.append(f"comment {c['comment_id']}: unknown sentiment")
	comment_ids = {c["comment_id"] for c in data["comments"]}
	for r in data["comment_replies"]:
		if r["comment_id"] not in comment_ids:
			errors.append(f"reply to unknown comment {r['comment_id']}")
		if r.get("lead") and r["lead"] not in by_email:
			errors.append(f"reply linked to unknown Lead {r['lead']}")
	return errors


def normalise(value):
	"""A comparable form of a stored or wanted value (dates as text, numbers as floats)."""
	if isinstance(value, datetime):
		return value.strftime("%Y-%m-%d %H:%M:%S")
	if isinstance(value, date):
		return value.isoformat()
	if isinstance(value, bool):
		return int(value)
	if isinstance(value, (int, float)):
		return float(value)
	if value in (None, ""):
		return ""
	try:
		return float(value)  # an Int stored as "3" is the same as 3
	except (TypeError, ValueError):
		return str(value)


def differs(current, wanted):
	"""Has the stored value to be written? Child rows compare only the fields the data sets."""
	if isinstance(wanted, list):
		current = current or []
		return len(current) != len(wanted) or any(
			normalise(row.get(k)) != normalise(v) for row, want in zip(current, wanted) for k, v in want.items())
	return normalise(current) != normalise(wanted)


# ---------------------------------------------------------------- Frappe side

class Counts(dict):
	"""{doctype: {"created": n, "updated": n}}; a row created in this run is never also counted as updated."""

	fresh = None

	def add(self, doctype, created=0, updated=0, name=None):
		self.fresh = self.fresh if self.fresh is not None else set()
		if created and name:
			self.fresh.add((doctype, name))
		if updated and (doctype, name) in self.fresh:
			return
		row = self.setdefault(doctype, {"created": 0, "updated": 0})
		row["created"] += int(created)
		row["updated"] += int(updated)


def _put(counts, doctype, filters, values, create_extra=None):
	"""Insert (filters + values + create_extra) when no row matches `filters`, else save the values that differ.
	Returns the name."""
	name = frappe.db.get_value(doctype, filters)
	if not name:
		name = frappe.get_doc({"doctype": doctype, **filters, **values, **(create_extra or {})}).insert(
			ignore_permissions=True).name
		counts.add(doctype, created=1, name=name)
		return name
	current = frappe.get_doc(doctype, name).as_dict()
	changed = {k: v for k, v in values.items() if differs(current.get(k), v)}
	if changed:
		doc = frappe.get_doc(doctype, name)
		doc.update(changed)
		doc.save(ignore_permissions=True)
		counts.add(doctype, updated=1, name=name)
	return name


def _restamp(counts, doctype, name, creation, modified=None, owner=None):
	"""Move creation/modified (and owner) to the sample's dates; counted as an update only when they changed."""
	values = {"creation": creation, "modified": modified or creation}
	if owner:
		values["owner"] = owner
	row = frappe.db.get_value(doctype, name, list(values), as_dict=True)
	if any(differs(row.get(k), v) for k, v in values.items()):
		frappe.db.set_value(doctype, name, values, update_modified=False)
		counts.add(doctype, updated=1, name=name)


def seed():
	"""Create or refresh the sample customers; returns {doctype: {"created": n, "updated": n}}."""
	from mmm_custom.demo import loader
	from mmm_custom import seed_demo

	data = load_data()
	dataset = loader.load_dataset()
	errors = validate_data(data, catalog_of(dataset))
	if errors:
		frappe.throw("Sample customer data is inconsistent:<br>" + "<br>".join(errors[:20]))

	today = frappe.utils.getdate()
	counts = Counts()
	courses = {c["product_code"]: c for c in dataset["courses"]}
	lead_name = {}

	# --- Leads: created in their pre-registration status; registrations move the Converted ones below
	deal_specs = {d["lead"]: d for d in data["deals"]}
	for l in data["leads"]:
		products = [{"product_code": c, "product_name": courses[c]["product_name"], "qty": 1,
		             "rate": courses[c]["standard_rate"], "amount": courses[c]["standard_rate"],
		             "net_amount": courses[c]["standard_rate"]} for c in l["courses"]]
		values = {
			"first_name": l["first_name"], "last_name": l["last_name"], "mobile_no": l["mobile_no"],
			"territory": l["branch"], "lead_owner": l["lead_owner"], "source": l["source"],
			"ai_hotness": l["ai_hotness"], "ai_intent": l["ai_intent"], "preferred_shift": l["preferred_shift"],
			"course_interest": ", ".join(courses[c]["product_name"] for c in l["courses"])[:140], "products": products}
		for key in ("learner_type", "learner_name", "learner_age", "learning_goal", "current_level"):
			if key in l:
				values[key] = l[key]
		if "trial_in_days" in l:
			values["trial_date"] = day_from(today, l["trial_in_days"])
		if l.get("lost_reason"):
			values["lost_reason"] = l["lost_reason"]
		first_status = l.get("initial_status") or l["status"]
		name = _put(counts, "CRM Lead", {"email": l["email"]}, values, create_extra={"status": first_status})
		lead_name[l["email"]] = name
		created_at = stamp(today, l["days_ago"], l["email"])
		_restamp(counts, "CRM Lead", name, created_at, stamp(today, l["days_ago"] // 2, l["email"]))

	# --- Registrations through the real hooks
	for d in data["deals"]:
		_registration(counts, d, next(x for x in data["leads"] if x["email"] == d["lead"]),
		              lead_name[d["lead"]], today)

	# --- Notes
	for n in data["notes"]:
		lead = lead_name[n["lead"]]
		owner = next(x["lead_owner"] for x in data["leads"] if x["email"] == n["lead"])
		name = _put(counts, "FCRM Note",
		            {"reference_doctype": "CRM Lead", "reference_docname": lead, "title": n["title"]},
		            {"content": n["content"]})
		_restamp(counts, "FCRM Note", name, stamp(today, n["days_ago"], n["lead"] + n["title"]), owner=owner)

	# --- Tasks: the six in seed_demo.TASKS plus the follow-ups of the sample
	extra = [{**t, "reference_doctype": "CRM Lead"} for t in data["tasks"]]
	result = seed_demo.seed_tasks(extra=extra)
	counts.add("CRM Task", created=result["count"], updated=len(result["moved"]))

	# --- Level-test attempts
	_quiz_attempts(counts, data, lead_name, today, dataset)

	# --- Facebook posts, comments and replies
	_posts(counts, data, lead_name, today)

	# --- Registrations, notes and quiz results saved the Leads again: put their dates back
	for l in data["leads"]:
		_restamp(counts, "CRM Lead", lead_name[l["email"]], stamp(today, l["days_ago"], l["email"]),
		         stamp(today, l["days_ago"] // 2, l["email"]))

	frappe.db.commit()
	return dict(counts)


def _registration(counts, spec, lead, name, today):
	from mmm_custom.lifecycle import AWAITING_CONFIRMATION, DEPOSIT_PAID, LOST, PENDING_PAYMENT, WON

	final = spec["final"]
	existing = frappe.db.get_value("CRM Deal", {"lead": name})
	created_at = stamp(today, max(lead["days_ago"] - 1, 0), lead["email"] + "deal")
	if existing:  # re-run: only the dates follow the new day
		deposit_day = day_from(today, -spec["deposit_days_ago"]) if "deposit_days_ago" in spec else None
		if deposit_day and differs(frappe.db.get_value("CRM Deal", existing, "deposit_date"), deposit_day):
			frappe.db.set_value("CRM Deal", existing, "deposit_date", deposit_day, update_modified=False)
			counts.add("CRM Deal", updated=1, name=existing)
		_restamp(counts, "CRM Deal", existing, created_at)
		return existing
	course = lead["courses"][0]
	schedules = frappe.get_all("Course Schedule", filters={"course": course, "branch": lead["branch"], "status": "Open"},
	                           fields=["name", "start_date", "status"])
	lead_doc = frappe.get_doc("CRM Lead", name)
	lead_doc.flags.ignore_permissions = True
	contact = lead_doc.create_contact("", False)  # links by phone / email, or creates the student's contact
	deal = lead_doc.create_deal(contact, lead_doc.create_organization(), {
		"status": AWAITING_CONFIRMATION, "enrol_course": course, "course_schedule": pick_class(schedules, today) or None,
		"territory": lead["branch"], "deal_owner": lead["lead_owner"]})
	counts.add("CRM Deal", created=1, name=deal)

	def move(**values):
		doc = frappe.get_doc("CRM Deal", deal)
		doc.update(values)
		doc.save(ignore_permissions=True)  # enrolment.on_update moves the Lead
		return doc

	if final == "lost":
		move(status=LOST, lost_reason=spec["lost_reason"], closed_date=today)
	elif final != "awaiting":
		fee = move(status=PENDING_PAYMENT).final_fee
		if final in ("deposit", "won"):
			day = day_from(today, -spec["deposit_days_ago"])
			if final == "deposit":
				move(status=DEPOSIT_PAID, deposit_amount=deposit_for(fee), deposit_date=day)
			else:
				move(status=WON, deposit_amount=deposit_for(fee), deposit_date=day, paid_amount=fee, closed_date=day)
	_restamp(counts, "CRM Deal", deal, created_at)
	return deal


def _quiz_attempts(counts, data, lead_name, today, dataset):
	from mmm_custom.engine import voucher

	prefix = dataset["settings"].get("voucher_prefix") or "SV"
	subjects = {s["skill_key"]: s["action_config"]["subject"] for s in dataset["bot_skills"]
	            if s["action_type"] == "level_quiz"}
	for q in data["quiz_attempts"]:
		lead = lead_name[q["lead"]]
		cid = conversation_id(q["lead"])
		conv = _put(counts, "Bot Conversation", {"conversation_id": cid},
		            {"lead": lead, "status": "closed", "is_sandbox": 0, "turns": 6 if q["status"] == "done" else 2})
		offered = stamp(today, q["days_ago"], q["lead"] + q["quiz"])
		values = {"conversation": conv, "status": q["status"], "is_sandbox": 0, "offered_at": offered}
		if q["status"] in ("started", "done"):
			values["started_at"] = offered + timedelta(minutes=3)
			values["reminded_at"] = offered + timedelta(hours=2)  # no reminder goes out for a sample
		if q["status"] == "done":
			values.update(score=q["score"], total=q["total"], level=q["level"], missed=q["missed"],
			              phone_after=1 if q.get("phone_after") else 0, finished_at=offered + timedelta(minutes=10))
			code = voucher.code(prefix, subjects[q["quiz"]], q["lead"]) if q.get("phone_after") else ""
			values["voucher_code"] = code
			lead_values = {"placement_result": f"{subjects[q['quiz']]}: {q['score']}/{q['total']} ({q['level']})",
			               "voucher_code": code}
			doc = frappe.get_doc("CRM Lead", lead)
			changed = {k: v for k, v in lead_values.items() if differs(doc.get(k), v)}
			if changed:
				doc.update(changed)
				doc.save(ignore_permissions=True)
				counts.add("CRM Lead", updated=1, name=doc.name)
		_put(counts, "Quiz Attempt", {"lead": lead, "quiz": q["quiz"]}, values)


def _posts(counts, data, lead_name, today):
	comments = {}
	for c in data["comments"]:
		comments.setdefault(c["post"], []).append(c)
	post_name = {}
	for p in data["posts"]:
		when = stamp(today, -p["day_offset"], p["title"])
		when = when.replace(hour=p["hour"], minute=0)
		values = {"course": p["course"], "status": p["status"], "day_of_week": day_of_week(when),
		          "scheduled_time": when, "batch_id": p["batch_id"], "content": p["content"],
		          "likes_count": p["likes"], "comments_count": p["comments"], "shares_count": p["shares"],
		          "reach_count": p["reach"], "leads_count": p["leads"], "registrations_count": p["registrations"]}
		if p["status"] == "Posted":
			values.update(posted_at=when, fb_post_id=p["fb_post_id"], fb_post_url="", last_analytics_sync=when)
			values["comments"] = [{"comment_id": c["comment_id"], "from_name": c["from_name"],
			                       "comment_time": when + timedelta(hours=c["hours_after"]), "sentiment": c["sentiment"],
			                       "comment_message": c["message"]} for c in comments.get(p["title"], [])]
		post_name[p["title"]] = _put(counts, "Facebook Post", {"title": p["title"]}, values)
	by_comment = {c["comment_id"]: c for c in data["comments"]}
	posted_when = {p["title"]: stamp(today, -p["day_offset"], p["title"]).replace(hour=p["hour"], minute=0)
	               for p in data["posts"]}
	for r in data["comment_replies"]:
		c = by_comment[r["comment_id"]]
		values = {"facebook_post": post_name[c["post"]], "from_name": c["from_name"], "intent": r["intent"],
		          "status": r["status"], "comment_message": c["message"], "public_reply": r["public_reply"],
		          "private_reply": r["private_reply"],
		          "comment_time": posted_when[c["post"]] + timedelta(hours=c["hours_after"]),
		          "lead": lead_name.get(r.get("lead")) or None}
		_put(counts, "Facebook Comment Reply", {"comment_id": r["comment_id"]}, values)
		if r.get("lead"):
			lead = lead_name[r["lead"]]
			if differs(frappe.db.get_value("CRM Lead", lead, "facebook_post"), post_name[c["post"]]):
				frappe.db.set_value("CRM Lead", lead, "facebook_post", post_name[c["post"]], update_modified=False)
				counts.add("CRM Lead", updated=1, name=lead)


# Everything below the line is deleted by reset(); what stays: users, consultants, the catalog, promotions, bot
# slots/skills/settings, staff replies, course FAQs, channel connections and the site config.
RESET_PLAIN = ("CRM Notification", "CRM Call Log", "CRM Task", "FCRM Note", "Bot Conversation", "Quiz Attempt",
               "AI Decision Log", "Bot Learning Signal", "Facebook Comment Reply")
RESET_WITH_CHILDREN = ("CRM Lead", "CRM Deal", "Facebook Post")
RECORD_TYPES = ("CRM Lead", "CRM Deal", "CRM Task")


def _count_delete(counts, doctype, filters=None):
	counts[doctype] = frappe.db.count(doctype, filters or {})
	frappe.db.delete(doctype, filters or {})


def reset():
	"""Delete all customer and test data of the CRM. Dev/demo only; there is no undo."""
	counts = {}
	_count_delete(counts, "ToDo", {"reference_type": ["in", RECORD_TYPES]})
	_count_delete(counts, "Comment", {"reference_doctype": ["in", RECORD_TYPES]})
	_count_delete(counts, "Version", {"ref_doctype": ["in", RECORD_TYPES]})
	_count_delete(counts, "Communication", {"reference_doctype": ["in", RECORD_TYPES]})
	for doctype in RESET_PLAIN:
		_count_delete(counts, doctype)
	for doctype in RESET_WITH_CHILDREN:
		for df in frappe.get_meta(doctype).get_table_fields():
			frappe.db.delete(df.options, {"parenttype": doctype})
		_count_delete(counts, doctype)
	contacts = frappe.get_all("Contact", filters={"user": ["is", "not set"]}, pluck="name")
	for name in contacts:
		frappe.delete_doc("Contact", name, ignore_permissions=True, force=True)
	counts["Contact"] = len(contacts)
	_count_delete(counts, "Course Schedule", {"is_demo_data": 1})  # the loader recreates the current weeks
	frappe.db.delete("Series", {"name": ["like", "CRM-LEAD-%"]})  # names start from 1 again
	frappe.db.delete("Series", {"name": ["like", "CRM-DEAL-%"]})
	frappe.db.commit()
	return counts


def summary():
	"""What the sample leaves in the CRM: Lead status/source split, registrations by status and row counts."""
	def split(doctype, field, filters=None):
		return {r[field] or "": r["n"] for r in frappe.get_all(
			doctype, filters=filters or {}, fields=[field, "count(name) as n"], group_by=field)}

	sample = {"email": ["like", "%" + EMAIL_DOMAIN]}
	return {
		"CRM Lead": frappe.db.count("CRM Lead"),
		"CRM Lead by status": split("CRM Lead", "status"),
		"CRM Lead by source": split("CRM Lead", "source"),
		"CRM Deal": frappe.db.count("CRM Deal"),
		"CRM Deal by status": split("CRM Deal", "status"),
		"FCRM Note": frappe.db.count("FCRM Note"),
		"CRM Task": frappe.db.count("CRM Task"),
		"Quiz Attempt": frappe.db.count("Quiz Attempt"),
		"Facebook Post": frappe.db.count("Facebook Post"),
		"Facebook Post by status": split("Facebook Post", "status"),
		"Facebook Comment Reply": frappe.db.count("Facebook Comment Reply"),
		"sample Leads": frappe.db.count("CRM Lead", sample),
	}
