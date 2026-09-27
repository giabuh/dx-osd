"""Slot-type registry (D-023): how each kind of slot is understood from a message and offered as
quick-reply buttons. A new kind of answer = one SlotType subclass + @register("name") + the Select
option in catalog_rules.SLOT_TYPES / the Bot Slot DocType."""

import re

from mmm_custom.engine.state import value
from mmm_custom.engine.text import find_phone, find_phrases

REGISTRY = {}


def register(name):
    def wrap(cls):
        REGISTRY[name] = cls()
        return cls
    return wrap


def _fill(u, slot, val):
    u.fills[slot.key] = {"value": val, "source": "keyword", "confidence": 1.0}


def course_phrases(catalog):
    return {c.code: (c.name, c.button, *c.aliases) for c in catalog.courses.values()}


class SlotType:
    late = False  # understood after skills (free-text answers such as a name)

    def understand(self, slot, text, folded, pending, catalog, u):
        pass

    def buttons(self, slot, slots, catalog):
        return []


@register("catalog")
class CatalogSlot(SlotType):
    """Courses (group → course) or branches (area → branch), matched on names, button labels and aliases."""

    def tables(self, slot, catalog):
        if slot.source == "course":
            parents = {g.name: (g.name, g.button, *g.aliases) for g in catalog.groups.values()}
            return course_phrases(catalog), parents
        leaves = {b.name: (b.name, b.button, *b.aliases) for b in catalog.branches.values()}
        parents = {a.name: (a.name, a.button, *a.aliases) for a in catalog.areas.values()}
        return leaves, parents

    def understand(self, slot, text, folded, pending, catalog, u):
        leaves, parents = self.tables(slot, catalog)
        hits = find_phrases(folded, leaves)
        if hits:
            u.spans.extend(hits.values())
            u.matches.append({"slot": slot.key, "kind": "value", "values": sorted(hits)})
            if len(hits) == 1:
                _fill(u, slot, next(iter(hits)))
                return
            u.ambiguous[slot.key] = sorted(hits)
            common = {catalog.parent_of(slot, v) for v in hits}
            if len(common) == 1:
                u.parents[slot.key] = common.pop()
            return
        found = find_phrases(folded, parents)
        u.spans.extend(found.values())
        if len(found) == 1:
            u.parents[slot.key] = next(iter(found))
            u.matches.append({"slot": slot.key, "kind": "parent", "values": sorted(found)})

    def items(self, slot, slots, catalog):
        """(value, button title, parent) of every offerable leaf, in catalog order."""
        if slot.source == "course":
            return [(c.code, c.button, c.group) for c in catalog.courses.values()]
        course_slot = catalog.slot_for("course")
        course = catalog.courses.get(value(slots, course_slot.key)) if course_slot else None
        full_only = course is not None and course.offer == "full"  # advanced courses run at full branches only
        return [(b.name, b.button, b.area) for b in catalog.branches.values() if not full_only or b.tier == "full"]

    def buttons(self, slot, slots, catalog):
        entry = slots.get(slot.key) or {}
        items = self.items(slot, slots, catalog)
        chosen = []
        if entry.get("candidates"):
            chosen = [i for i in items if i[0] in entry["candidates"]]
        elif entry.get("parent"):
            chosen = [i for i in items if i[2] == entry["parent"]]
        if not chosen:
            order = catalog.groups if slot.source == "course" else catalog.areas
            parents = [p for p in order if any(i[2] == p for i in items)]
            if len(parents) > 1:
                return [{"title": order[p].button, "action": {"type": "parent", "slot": slot.key, "value": p}}
                        for p in parents]
            chosen = items
        return [{"title": title, "action": {"type": "slot", "slot": slot.key, "value": val}} for val, title, _ in chosen]


@register("choice")
class ChoiceSlot(SlotType):
    def understand(self, slot, text, folded, pending, catalog, u):
        table = {o.value: (o.label, o.button, *o.aliases) for o in slot.options}
        hits = find_phrases(folded, table, min_words=1 if pending else 2)  # D-068
        if len(hits) == 1:
            _fill(u, slot, next(iter(hits)))
            u.spans.extend(hits.values())
            u.matches.append({"slot": slot.key, "kind": "value", "values": sorted(hits)})
        elif hits and pending:
            u.ambiguous[slot.key] = sorted(hits)

    def buttons(self, slot, slots, catalog):
        return [{"title": o.button, "action": {"type": "slot", "slot": slot.key, "value": o.value}} for o in slot.options]


@register("phone")
class PhoneSlot(SlotType):
    def understand(self, slot, text, folded, pending, catalog, u):
        phone = find_phone(text)
        if phone:
            _fill(u, slot, phone)
            u.matches.append({"slot": slot.key, "kind": "phone", "values": [phone]})

    def buttons(self, slot, slots, catalog):
        return [] if slot.required else [{"title": "Bỏ qua", "action": {"type": "skip", "slot": slot.key}}]


@register("number")
class NumberSlot(SlotType):
    def understand(self, slot, text, folded, pending, catalog, u):
        m = re.search(r"\b(\d{1,3})\b", folded) if pending else None  # D-069
        if m and 0 < int(m.group(1)) < 120:
            _fill(u, slot, int(m.group(1)))


@register("text")
class TextSlot(SlotType):
    late = True

    def understand(self, slot, text, folded, pending, catalog, u):
        if not pending or u.fills or u.skills or u.parents or u.ambiguous:  # D-069
            return
        answer = " ".join((text or "").split())[:60]
        if answer and len(answer.split()) <= 6:
            _fill(u, slot, answer)
