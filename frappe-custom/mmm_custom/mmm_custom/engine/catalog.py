"""Read-only snapshot of the lead-engine data: catalog, bot slots, bot skills and settings.

`build_catalog` takes plain dicts shaped like the demo dataset (`mmm_custom/demo/saoviet/*.json`);
tests build it offline from those files and `engine.repo` builds the same shape from the database.
"""

from dataclasses import dataclass, field

from mmm_custom.demo.loader import map_url

# Used when Lead Engine Settings leaves a field empty (Frappe stores unset Int as 0).
DEFAULT_SETTINGS = {
    "brand_name": "", "bot_name": "", "address_customer": "anh/chị", "address_self": "em",
    "hotline": "", "zalo": "", "website": "", "email": "", "signoff": "",
    "greeting_template": "", "fallback_template": "", "handoff_template": "", "summary_template": "",
    "max_skills_per_reply": 3, "max_stuck_turns": 2, "log_retention_days": 180,
    "jev_live": 0, "jev_timeout": 8, "catalog_act": 0.85, "catalog_confirm": 0.55, "choice_act": 0.80,
    "choice_confirm": 0.50, "skill_act": 0.85, "skill_confirm": 0.60, "handoff_noul": 0.70, "spam_threshold": 0.80,
    "jev_calls_per_hour": 20, "jev_daily_token_budget": 0, "playground_daily_token_budget": 0,
    "advisor_goal_weight": 0.6, "advisor_level_weight": 0.4, "advisor_floor": 0.5, "advisor_shortlist": 8,
    "confirm_slot_template": "Dạ ý {{ brand.you }} là {{ confirm.label }} phải không ạ?",
    "confirm_skill_template": "Dạ {{ brand.you }} muốn hỏi về {{ confirm.label }} phải không ạ?",
}


def _aliases(text):
    return tuple(a.strip() for a in (text or "").split(",") if a.strip())


@dataclass(frozen=True)
class Option:
    value: str
    label: str
    button: str
    aliases: tuple = ()


@dataclass(frozen=True)
class Slot:
    key: str
    label: str
    type: str
    source: str = ""
    required: bool = False
    order: int = 0
    ask_template: str = ""
    options: tuple = ()
    depends_on: tuple = ()  # (slot_key, value) or ()
    lead_field: str = ""

    def option(self, value):
        return next((o for o in self.options if o.value == value), None)


@dataclass(frozen=True)
class Group:
    name: str
    button: str
    emoji: str = ""
    order: int = 0
    aliases: tuple = ()


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    button: str
    group: str
    fee: float = 0.0
    duration: str = ""
    audience: str = ""
    min_age: int = 0
    max_age: int = 0
    certificate: str = ""
    offer: str = "all"
    aliases: tuple = ()
    next_courses: tuple = ()
    image: str = ""


@dataclass(frozen=True)
class Area:
    name: str
    button: str
    aliases: tuple = ()


@dataclass(frozen=True)
class Branch:
    name: str
    button: str
    area: str
    code: str = ""
    tier: str = "standard"
    address: str = ""
    hotline: str = ""
    map_url: str = ""
    aliases: tuple = ()


@dataclass(frozen=True)
class Template:
    key: str
    when: str
    text: str


@dataclass(frozen=True)
class FollowUp:
    title: str
    target_type: str
    target: str = ""


@dataclass(frozen=True)
class Skill:
    key: str
    title: str
    action: str
    params: tuple = ()
    aliases: tuple = ()
    missing_policy: str = "ask"
    config: dict = field(default_factory=dict)
    templates: tuple = ()
    follow_ups: tuple = ()
    creates_lead: bool = True
    handoff_after: bool = False
    order: int = 0
    media: str = ""
    description: str = ""
    examples: tuple = ()


@dataclass
class Catalog:
    groups: dict
    courses: dict
    areas: dict
    branches: dict
    slots: list
    skills: dict
    settings: dict

    def slot(self, key):
        return next((s for s in self.slots if s.key == key), None)

    def slot_for(self, source):
        """The catalog slot holding courses ("course") or branches ("branch"), if configured."""
        return next((s for s in self.slots if s.type == "catalog" and s.source == source), None)

    def courses_in(self, group):
        return [c for c in self.courses.values() if c.group == group]

    def branches_in(self, area):
        return [b for b in self.branches.values() if b.area == area]

    def parent_of(self, slot, value):
        if slot.source == "course" and value in self.courses:
            return self.courses[value].group
        if slot.source == "branch" and value in self.branches:
            return self.branches[value].area
        return ""


def _active(row):
    return row.get("active", 1) not in (0, "0", False)


def _int(value):
    return int(value or 0)


def build_catalog(data):
    groups = {g["group_name"]: Group(g["group_name"], g.get("button_label") or g["group_name"], g.get("emoji") or "",
                                     _int(g.get("sort_order")), _aliases(g.get("aliases")))
              for g in sorted(data.get("course_groups") or [], key=lambda g: _int(g.get("sort_order")))}
    courses = {c["product_code"]: Course(
        code=c["product_code"], name=c["product_name"], button=c.get("button_label") or c["product_name"],
        group=c.get("course_group") or "", fee=float(c.get("standard_rate") or 0),
        duration=c.get("duration_text") or "", audience=c.get("audience") or "",
        min_age=_int(c.get("min_age")), max_age=_int(c.get("max_age")), certificate=c.get("certificate") or "",
        offer=c.get("offer") or "all", aliases=_aliases(c.get("aliases")),
        next_courses=tuple(c.get("next_courses") or ()), image=c.get("image") or "")
        for c in data.get("courses") or [] if _active(c)}
    areas, branches = {}, {}
    for a in (data.get("areas") or {}).get("areas", []):
        areas[a["territory_name"]] = Area(a["territory_name"], a.get("button_label") or a["territory_name"],
                                          _aliases(a.get("aliases")))
        for b in a.get("branches", []):
            address = b.get("address") or ""
            branches[b["territory_name"]] = Branch(
                name=b["territory_name"], button=b.get("button_label") or b["territory_name"], area=a["territory_name"],
                code=b.get("branch_code") or "", tier=b.get("tier") or "standard", address=address,
                hotline=b.get("hotline") or "", map_url=b.get("map_url") or (map_url(address) if address else ""),
                aliases=_aliases(b.get("aliases")))
    slots = sorted((Slot(
        key=s["slot_key"], label=s["label"], type=s["slot_type"], source=s.get("catalog_source") or "",
        required=bool(s.get("required")), order=_int(s.get("sort_order")), ask_template=s.get("ask_template") or "",
        options=tuple(Option(o["value"], o["label"], o.get("button_label") or o["label"], _aliases(o.get("aliases")))
                      for o in s.get("options") or ()),
        depends_on=(s["depends_on_slot"], s.get("depends_on_value") or "") if s.get("depends_on_slot") else (),
        lead_field=s.get("lead_field") or "")
        for s in data.get("bot_slots") or [] if _active(s)), key=lambda s: s.order)
    skills = {k["skill_key"]: Skill(
        key=k["skill_key"], title=k["title"], action=k["action_type"], params=tuple(k.get("parameters") or ()),
        aliases=_aliases(k.get("aliases")), missing_policy=k.get("missing_policy") or "ask",
        config=dict(k.get("action_config") or {}),
        templates=tuple(Template(t["variant_key"], t.get("when") or "", t["template"]) for t in k.get("templates") or ()),
        follow_ups=tuple(FollowUp(f["title"], f["target_type"], f.get("target") or "") for f in k.get("follow_ups") or ()),
        creates_lead=bool(k.get("creates_lead", 1)), handoff_after=bool(k.get("handoff_after")),
        order=_int(k.get("sort_order")), media=k.get("media") or "",
        description=k.get("jev_description") or "",
        examples=tuple(line.strip() for line in (k.get("examples") or "").splitlines() if line.strip()))
        for k in data.get("bot_skills") or [] if _active(k)}
    settings = dict(DEFAULT_SETTINGS)
    settings.update({k: v for k, v in (data.get("settings") or {}).items() if v not in (None, "", 0)})
    return Catalog(groups, courses, areas, branches, slots, skills, settings)
