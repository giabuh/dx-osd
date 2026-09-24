"""Pure-logic state machine for the EduFlow Lead Qualification Bot.

This module has ZERO side effects — no HTTP calls, no database access, no
imports of frappe or requests. It is a pure function: given the current state,
user input, and list of already-selected courses, it returns the next state,
the message to send, optional Quick Reply items, and a list of action tags
for the caller to execute.

License: MIT
"""

from dataclasses import dataclass, field


COURSES = {
    "tieng_anh": "🇬🇧 Tiếng Anh",
    "boi_loi": "🏊 Bơi lội",
    "toan_tu_duy": "🧮 Toán tư duy",
}

BRANCHES = {
    "binh_thanh": "📍 CS1 Bình Thạnh",
    "quan_1": "📍 CS2 Quận 1",
    "thu_duc": "📍 CS3 Thủ Đức",
}

DONE_TOKEN = "done"


@dataclass
class TransitionResult:
    next_state: str
    message: str
    quick_replies: list | None = None
    actions: list = field(default_factory=list)
    selected_courses: list = field(default_factory=list)
    branch: str | None = None


def _build_course_replies(exclude: list[str]) -> list[dict]:
    """Build Quick Reply items for courses not yet selected, plus a done button."""
    replies = []
    for key, label in COURSES.items():
        if key not in exclude:
            replies.append({"title": label, "value": key})
    replies.append({"title": "✅ Xong, tiếp tục", "value": DONE_TOKEN})
    return replies


def _build_branch_replies() -> list[dict]:
    """Build Quick Reply items for all branches."""
    return [{"title": label, "value": key} for key, label in BRANCHES.items()]


def _format_courses_display(course_keys: list[str]) -> str:
    """Format selected course keys into a human-readable Vietnamese string."""
    return ", ".join(COURSES.get(k, k) for k in course_keys)


def _greeting() -> TransitionResult:
    """Handle the initial greeting state."""
    replies = [{"title": label, "value": key} for key, label in COURSES.items()]
    return TransitionResult(
        next_state="await_course",
        message=(
            "🎓 Chào bạn! EduFlow Academy rất vui được hỗ trợ.\n"
            "Bạn đang quan tâm đến bộ môn nào ạ?"
        ),
        quick_replies=replies,
        selected_courses=[],
    )


def _ask_branch(selected_courses: list[str]) -> TransitionResult:
    """Transition to the branch selection step."""
    return TransitionResult(
        next_state="await_branch",
        message="📍 Tuyệt vời! Bạn muốn học tại cơ sở nào ạ?",
        quick_replies=_build_branch_replies(),
        selected_courses=list(selected_courses),
    )


def _invalid_input_reminder(state: str, quick_replies: list[dict],
                            selected_courses: list[str]) -> TransitionResult:
    """Re-send the current menu with a gentle reminder."""
    return TransitionResult(
        next_state=state,
        message="Bạn vui lòng chọn một trong các tùy chọn bên dưới nhé 👇",
        quick_replies=quick_replies,
        selected_courses=list(selected_courses),
    )


def transition(state: str | None, user_input: str,
               selected_courses: list[str]) -> TransitionResult | None:
    """Compute the next state given current state, user input, and context.

    Args:
        state: Current bot state (None/"" for new conversations).
        user_input: The text content of the customer's message, or the
                    Quick Reply ``value`` if they tapped a button.
        selected_courses: List of course keys already selected.

    Returns:
        A TransitionResult describing what to do next, or None if the
        conversation is completed and should be ignored.
    """
    if not state or state == "greeting":
        return _greeting()

    if state == "completed":
        return None

    if state == "await_course":
        user_input_clean = user_input.strip().lower() if user_input else ""

        # "Done" → transition to branch if at least one course selected
        if user_input_clean == DONE_TOKEN and selected_courses:
            return _ask_branch(selected_courses)

        # Valid course selection
        if user_input_clean in COURSES and user_input_clean not in selected_courses:
            new_courses = list(selected_courses) + [user_input_clean]

            # All courses selected → auto-transition to branch
            if len(new_courses) >= len(COURSES):
                result = _ask_branch(new_courses)
                courses_display = _format_courses_display(new_courses)
                result.message = (
                    f"Đã ghi nhận {courses_display} ✅\n\n" + result.message
                )
                return result

            # Still courses remaining → offer more
            course_label = COURSES[user_input_clean]
            return TransitionResult(
                next_state="await_course",
                message=(
                    f"Đã ghi nhận {course_label} ✅\n"
                    "Bạn muốn đăng ký thêm bộ môn nào không?"
                ),
                quick_replies=_build_course_replies(new_courses),
                selected_courses=new_courses,
            )

        # Invalid input (free-text or duplicate selection)
        return _invalid_input_reminder(
            "await_course",
            _build_course_replies(selected_courses) if selected_courses
            else [{"title": label, "value": key} for key, label in COURSES.items()],
            selected_courses,
        )

    if state == "await_branch":
        user_input_clean = user_input.strip().lower() if user_input else ""

        if user_input_clean in BRANCHES:
            branch_label = BRANCHES[user_input_clean]
            courses_display = _format_courses_display(selected_courses)
            return TransitionResult(
                next_state="completed",
                message=(
                    f"✅ Cảm ơn bạn đã cung cấp thông tin!\n"
                    f"📚 Bộ môn: {courses_display}\n"
                    f"📍 Cơ sở: {branch_label}\n\n"
                    f"Chuyên viên tư vấn sẽ liên hệ bạn ngay bây giờ nhé! 😊"
                ),
                quick_replies=None,
                actions=["update_lead", "assign_agent", "bot_handoff"],
                selected_courses=list(selected_courses),
                branch=user_input_clean,
            )

        return _invalid_input_reminder(
            "await_branch", _build_branch_replies(), selected_courses
        )

    # Unknown state — treat as greeting
    return _greeting()
