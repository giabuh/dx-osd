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
    phone: str | None = None


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


def _match_course(user_input: str) -> str | None:
    """Resolve user input (key, label, emoji, or text) to a course key."""
    if not user_input:
        return None
    raw = user_input.strip().lower()
    if raw in COURSES:
        return raw
    for key, label in COURSES.items():
        if raw == label.lower():
            return key
    if "tiếng anh" in raw or "tieng anh" in raw or "tieng_anh" in raw:
        return "tieng_anh"
    if "bơi" in raw or "boi" in raw or "boi_loi" in raw:
        return "boi_loi"
    if "toán" in raw or "toan" in raw or "toan_tu_duy" in raw:
        return "toan_tu_duy"
    return None


def _is_done_token(user_input: str) -> bool:
    """Check if the user input signifies completion of course selection."""
    if not user_input:
        return False
    raw = user_input.strip().lower()
    if raw in (DONE_TOKEN, "done"):
        return True
    return any(w in raw for w in ("xong", "tiếp tục", "tiep tuc", "hoàn thành"))


def _match_branch(user_input: str) -> str | None:
    """Resolve user input (key, label, emoji, or text) to a branch key."""
    if not user_input:
        return None
    raw = user_input.strip().lower()
    if raw in BRANCHES:
        return raw
    for key, label in BRANCHES.items():
        if raw == label.lower():
            return key
    if "bình thạnh" in raw or "binh thanh" in raw or "binh_thanh" in raw or "cs1" in raw:
        return "binh_thanh"
    if "quận 1" in raw or "quan 1" in raw or "quan_1" in raw or "cs2" in raw:
        return "quan_1"
    if "thủ đức" in raw or "thu duc" in raw or "thu_duc" in raw or "cs3" in raw:
        return "thu_duc"
    return None


SKIP_TOKEN = "skip_phone"


def _is_skip_token(user_input: str) -> bool:
    """Check if the user wants to skip providing a phone number."""
    if not user_input:
        return False
    raw = user_input.strip().lower()
    return raw in (SKIP_TOKEN, "skip", "bỏ qua", "bo qua", "không", "khong")


def _normalize_vn_phone(raw: str) -> str | None:
    """Validate and normalize a Vietnamese phone number.

    Accepts:
      - 10-digit starting with 0 (e.g. 0901234567)
      - With +84 prefix (e.g. +84901234567)
      - With 84 prefix (e.g. 84901234567)
      - Spaces/dots/dashes are stripped

    Returns the normalized phone (e.g. +84901234567) or None if invalid.
    """
    import re
    digits = re.sub(r"[\s.\-\(\)]+", "", raw.strip())
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    elif digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    if re.fullmatch(r"0\d{9}", digits):
        return "+84" + digits[1:]
    return None


def _ask_phone(selected_courses: list[str], branch: str) -> TransitionResult:
    """Transition to the phone collection step."""
    return TransitionResult(
        next_state="await_phone",
        message=(
            "📞 Bạn vui lòng cho em số điện thoại để tư vấn viên liên hệ nhé!\n"
            "(Ví dụ: 0901234567)"
        ),
        quick_replies=[{"title": "⏭ Bỏ qua", "value": SKIP_TOKEN}],
        selected_courses=list(selected_courses),
        branch=branch,
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
        # "Done" → transition to branch if at least one course selected
        if _is_done_token(user_input) and selected_courses:
            return _ask_branch(selected_courses)

        # Valid course selection
        matched_course = _match_course(user_input)
        if matched_course and matched_course not in selected_courses:
            new_courses = list(selected_courses) + [matched_course]

            # All courses selected → auto-transition to branch
            if len(new_courses) >= len(COURSES):
                result = _ask_branch(new_courses)
                courses_display = _format_courses_display(new_courses)
                result.message = (
                    f"Đã ghi nhận {courses_display} ✅\n\n" + result.message
                )
                return result

            # Still courses remaining → offer more
            course_label = COURSES[matched_course]
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
        matched_branch = _match_branch(user_input)
        if matched_branch:
            return _ask_phone(selected_courses, matched_branch)

        return _invalid_input_reminder(
            "await_branch", _build_branch_replies(), selected_courses
        )

    if state == "await_phone":
        # Read branch from context — stored in custom_attributes by bot_api
        # The branch is passed via selected_courses context workaround:
        # bot_api stores bot_branch in custom_attrs, we receive it here
        branch = None  # caller must pass via context; we extract from input

        # Skip phone
        if _is_skip_token(user_input):
            courses_display = _format_courses_display(selected_courses)
            return TransitionResult(
                next_state="completed",
                message=(
                    f"✅ Cảm ơn bạn đã cung cấp thông tin!\n"
                    f"📚 Bộ môn: {courses_display}\n\n"
                    f"Chuyên viên tư vấn sẽ liên hệ bạn ngay bây giờ nhé! 😊"
                ),
                quick_replies=None,
                actions=["update_lead", "assign_agent", "bot_handoff"],
                selected_courses=list(selected_courses),
                phone=None,
            )

        # Validate phone
        normalized = _normalize_vn_phone(user_input)
        if normalized:
            courses_display = _format_courses_display(selected_courses)
            return TransitionResult(
                next_state="completed",
                message=(
                    f"✅ Cảm ơn bạn đã cung cấp thông tin!\n"
                    f"📚 Bộ môn: {courses_display}\n"
                    f"📞 SĐT: {normalized}\n\n"
                    f"Chuyên viên tư vấn sẽ liên hệ bạn ngay bây giờ nhé! 😊"
                ),
                quick_replies=None,
                actions=["update_lead", "assign_agent", "bot_handoff"],
                selected_courses=list(selected_courses),
                phone=normalized,
            )

        # Invalid phone format
        return TransitionResult(
            next_state="await_phone",
            message=(
                "Số điện thoại chưa đúng định dạng. Vui lòng nhập lại nhé!\n"
                "(Ví dụ: 0901234567 hoặc +84901234567)"
            ),
            quick_replies=[{"title": "⏭ Bỏ qua", "value": SKIP_TOKEN}],
            selected_courses=list(selected_courses),
        )

    # Unknown state — treat as greeting
    return _greeting()

