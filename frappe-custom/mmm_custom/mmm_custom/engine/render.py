"""Template rendering for the bot (D-016, D-050, D-051): Vietnamese filters and the render guard.

Frappe's Jinja is sandboxed but uses DebugUndefined, so a missing value prints as template syntax;
`render_text` refuses any output that still contains `{{` or `{%` (and any rendering exception), and
the caller sends the fallback wording instead. The filters are registered in hooks.py (`jinja`).
"""

from datetime import date, datetime

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

WEEKDAYS = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")


class RenderError(Exception):
    pass


def vnd(value):
    """1200000 → "1.200.000đ"."""
    try:
        amount = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return str(value)
    return f"{amount:,}".replace(",", ".") + "đ"


def date_vi(value):
    """date(2026, 10, 4) → "Chủ nhật, 04/10"."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    if not isinstance(value, date):
        return str(value)
    return f"{WEEKDAYS[value.weekday()]}, {value:%d/%m}"


def render_text(template, context, renderer):
    try:
        out = renderer(template or "", context)
    except Exception as e:
        raise RenderError(f"{type(e).__name__}: {e}") from e
    if "{{" in out or "{%" in out:
        raise RenderError("template syntax left in the output (missing value)")
    return out.strip()


def condition(expr, context, renderer):
    """Evaluate a Bot Skill Template `when` expression, e.g. "not schedules"."""
    return render_text("{% if " + expr + " %}1{% endif %}", context, renderer) == "1"


def frappe_renderer(template, context):
    return frappe.render_template(template, context)


def jinja_renderer():
    """Same sandbox, undefined handling and filters as the bench, without Frappe (tests, tools)."""
    import jinja2
    import jinja2.sandbox

    env = jinja2.sandbox.SandboxedEnvironment(undefined=jinja2.DebugUndefined)
    env.filters.update(vnd=vnd, date_vi=date_vi)
    return lambda template, context: env.from_string(template).render(context)
