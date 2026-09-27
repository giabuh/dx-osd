"""Handoff to a consultant (D-058): who gets the conversation, which Chatwoot team, labels, conversation
attributes (D-027) and the private summary note. Reads through the repo; the Chatwoot/CRM calls happen
in Effects.handoff."""

from dataclasses import dataclass, field

from mmm_custom.engine.actions import find_schedules
from mmm_custom.engine.context import base_context
from mmm_custom.engine.render import RenderError, date_vi, render_text
from mmm_custom.engine.routing import B2B_TEAM, CENTRAL_TEAM, is_b2b, pick_consultant
from mmm_custom.engine.text import slug


@dataclass
class HandoffPlan:
    consultant: dict
    why: str
    team: str
    labels: list = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    summary: str = ""
    owner: str = ""
    errors: list = field(default_factory=list)

    @property
    def consultant_name(self):
        return (self.consultant or {}).get("name", "")

    @property
    def agent_id(self):
        return (self.consultant or {}).get("chatwoot_agent_id")

    @property
    def consultant_ctx(self):
        if not self.consultant:
            return {}
        return {"name": self.consultant.get("full_name") or self.consultant["name"],
                "branch": self.consultant.get("branch") or self.team}


def next_step(ctx, data, today):
    """The summary's suggestion for the consultant, computed from data — never Jev (D-058)."""
    if not ctx["course"]:
        return "hỏi nhu cầu khóa học của khách"
    rows = find_schedules(data, ctx, today, 1)
    if not rows:
        return f"gửi lịch khai giảng mới của {ctx['course']['name']}"
    s = rows[0]
    return f"gọi xác nhận lớp {date_vi(s['date'])} ({s['shift']}) tại {s['branch']}, còn {s['seats_left']} chỗ"


def plan_handoff(state, decision, catalog, repo, render):
    ctx = base_context(decision.slots, catalog, state)
    branch = ctx["branch"].get("name", "")
    owner = repo.lead_owner(state.lead) if state.is_returning and state.lead else ""
    course_slot = catalog.slot_for("course")
    group = ctx["course"].get("group") or ((decision.slots.get(course_slot.key) or {}).get("parent", "") if course_slot else "")
    hotness = decision.ai.get("hotness", {})
    hot = hotness.get("value") == "hot" and hotness.get("confidence", 0) >= float(catalog.settings["handoff_noul"])
    b2b = is_b2b(state.answered + decision.skills, catalog)
    consultant, why = pick_consultant(branch, repo.consultants(), repo.consultant_load(), owner, group, hot, b2b)
    if b2b and consultant and consultant.get("handles_b2b"):
        team = B2B_TEAM
    else:
        team = (consultant.get("branch") if consultant else branch) or CENTRAL_TEAM
    plan = HandoffPlan(consultant, why, team, owner=(consultant or {}).get("name", ""))
    plan.labels = (["b2b"] if b2b else []) + [slug(x) for x in (group, branch) if x]
    if hot:
        plan.labels.append("hot")
    plan.attributes = {f"bot_{key}": shown for key, shown in ctx["slots"].items()}
    answered = [catalog.skills[k].title for k in dict.fromkeys(state.answered + decision.skills) if k in catalog.skills]
    summary_ctx = {**ctx, "consultant": plan.consultant_ctx, "why": why, "reason": decision.reason,
                   "ai": decision.ai,
                   "answered": answered, "next_step": next_step(ctx, repo, repo.today())}
    template = catalog.settings["summary_template"]
    try:
        plan.summary = render_text(template, summary_ctx, render) if template else ""
    except RenderError as e:
        plan.errors.append({"type": "render_error", "source": "summary", "detail": str(e)[:300]})
    if not plan.summary:
        plan.summary = f"🤖 Bot chuyển khách · {decision.reason} · {why}"
    return plan
