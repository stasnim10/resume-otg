"""
Shared screen-layout scaffolding and UI primitives.

Extracted from streamlit_app.py so that all screen modules can import
these helpers without creating a circular dependency on the main module.
"""
from __future__ import annotations

import streamlit as st


# ---------------------------------------------------------------------------
# Flow navigation constants
# ---------------------------------------------------------------------------

FLOW_STEPS = [
    ("landing", "Start"),
    ("input", "Upload"),
    ("mode", "Run"),
    ("review", "Review"),
    ("complete", "Download"),
]

FLOW_STEP_ALIASES = {
    "builder_input": "input",
    "onboarding_welcome": "input",
    "onboarding_questions": "input",
    "builder_stub": "mode",
    "builder_review": "review",
    "fit_report": "input",
    "local_ai_setup": "mode",
    "local_ai_run": "review",
    "manual": "mode",
    "api": "mode",
    "application_match": "input",
    "application_workspace": "input",
}


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def _is_builder_flow_screen(screen_key: str) -> bool:
    """Return whether the current screen belongs to the builder flow."""
    return screen_key in {"builder_input", "builder_stub", "builder_review"}


def _resolve_step_target(step_key: str, current_screen: str) -> str | None:
    """Map a top-level step to the concrete screen for the active flow."""
    if step_key not in {key for key, _label in FLOW_STEPS}:
        return None

    if _is_builder_flow_screen(current_screen):
        builder_targets = {
            "landing": "landing",
            "input": "builder_input",
            "mode": "builder_stub",
            "review": "builder_review",
            "complete": "builder_review",
        }
        return builder_targets.get(step_key)

    default_targets = {
        "landing": "landing",
        "input": "input",
        "mode": "mode",
        "review": "review",
        "complete": "review",
    }
    return default_targets.get(step_key)


def _can_access_step(step_key: str, current_screen: str) -> bool:
    """Guard progress-step navigation so users can move safely through the journey."""
    if step_key == "landing":
        return True
    if step_key == "input":
        return True

    if _is_builder_flow_screen(current_screen):
        if step_key == "mode":
            return bool(st.session_state.get("builder_prompt"))
        if step_key in {"review", "complete"}:
            return bool(st.session_state.get("builder_payload"))
        return False

    if step_key == "mode":
        jd = st.session_state.get("job_description") or ""
        return bool(st.session_state.get("resume_text") and jd.strip())
    if step_key in {"review", "complete"}:
        return bool(st.session_state.get("validated_payload"))
    return False


def handle_step_navigation_request() -> None:
    """Read `?nav=` query param and route to the correct step target."""
    requested_step = st.query_params.get("nav")
    if not requested_step:
        return

    requested_step = str(requested_step)
    current_screen = st.session_state.screen
    target_screen = _resolve_step_target(requested_step, current_screen)
    if target_screen and _can_access_step(requested_step, current_screen):
        st.session_state.screen = target_screen

    st.query_params.clear()


# ---------------------------------------------------------------------------
# Layout shell
# ---------------------------------------------------------------------------

def render_shell_start() -> None:
    """No-op wrapper hook for shared screen layout."""
    return


def render_shell_end() -> None:
    """No-op wrapper hook for shared screen layout."""
    return


# ---------------------------------------------------------------------------
# Progress stepper and screen header
# ---------------------------------------------------------------------------

def render_progress_stepper(current_key: str) -> None:
    """Render the guided progress stepper."""
    current_key = FLOW_STEP_ALIASES.get(current_key, current_key)
    current_index = next((index for index, (key, _label) in enumerate(FLOW_STEPS) if key == current_key), 0)
    steps_html = []
    for index, (step_key, label) in enumerate(FLOW_STEPS):
        classes = ["apple-step"]
        if index < current_index:
            classes.append("done")
        elif index == current_index:
            classes.append("active")
        if not _can_access_step(step_key, st.session_state.screen):
            classes.append("disabled")
            steps_html.append(f'<span class="{" ".join(classes)}">{index + 1}. {label}</span>')
        else:
            steps_html.append(
                f'<a class="{" ".join(classes)}" href="?nav={step_key}">{index + 1}. {label}</a>'
            )
    st.markdown(f'<div class="apple-stepper">{"".join(steps_html)}</div>', unsafe_allow_html=True)


def render_screen_intro(step_key: str, eyebrow: str, title: str, subtitle: str) -> None:
    """Render a calm screen header with progress."""
    flow_keys = {key for key, _label in FLOW_STEPS}
    if step_key in flow_keys or step_key in FLOW_STEP_ALIASES:
        render_progress_stepper(step_key)
    st.markdown(
        f"""
        <div class="apple-hero apple-hero-dashboard">
          <div class="apple-eyebrow">{eyebrow}</div>
          <div class="apple-page-title">{title}</div>
          <p class="apple-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# UI primitives
# ---------------------------------------------------------------------------

def render_chip_row(items: list[str]) -> None:
    """Render small trust or detected-value chips."""
    if not items:
        return
    html = "".join(f'<div class="apple-chip">{item}</div>' for item in items)
    st.markdown(f'<div class="apple-trust-row">{html}</div>', unsafe_allow_html=True)


def build_inline_chip_row(items: list[str]) -> str:
    """Return compact chip HTML for use inside local card layouts."""
    if not items:
        return ""
    chips = "".join(f'<div class="apple-inline-chip">{item}</div>' for item in items)
    return f'<div class="apple-inline-chip-row">{chips}</div>'


def build_readiness_rows(items: list[tuple[str, str]]) -> str:
    """Return structured readiness rows for setup and summary cards."""
    rows = "".join(
        (
            f'<div class="apple-readiness-row">'
            f'<div class="apple-readiness-key">{label}</div>'
            f'<div class="apple-readiness-value">{value}</div>'
            f"</div>"
        )
        for label, value in items
    )
    return f'<div class="apple-readiness-card">{rows}</div>'


# ---------------------------------------------------------------------------
# Text utility
# ---------------------------------------------------------------------------

def format_preview_text(text: str, max_len: int = 260) -> str:
    """Trim long paragraph previews so comparison cards stay readable."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len].rstrip()}..."


# ---------------------------------------------------------------------------
# Replacement review helpers
# ---------------------------------------------------------------------------

def _section_label(count: int, singular: str, plural: str) -> str:
    """Return a compact count label."""
    return f"{count} {singular if count == 1 else plural}"


def _group_review_results(review_results: list[dict]) -> dict[str, list[dict]]:
    """Group review items into user-facing sections."""
    grouped: dict[str, list[dict]] = {"Summary": [], "Bullet": [], "Skills": []}
    for item in review_results:
        grouped.setdefault(item.get("section", "Other"), []).append(item)
    return grouped


def render_replacement_preview(item: dict, index: int, key_prefix: str, show_status: bool = True) -> None:
    """Render a cleaner before/after preview for one replacement."""
    status = item["status"]
    if show_status:
        if status == "matched":
            st.markdown("**✏️ AI-updated**")
        elif status == "duplicate":
            st.markdown("**⚠️ Needs manual review: multiple paragraphs matched**")
        else:
            st.markdown("**⚠️ Needs manual review: no exact anchor was found**")

    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown("**Current Resume Text**")
        st.text_area(
            f"Current Resume Text {index}",
            value=item["match_anchor"],
            height=130,
            disabled=True,
            key=f"{key_prefix}-anchor-{index}",
        )
    with right_col:
        st.markdown("**Proposed Replacement**")
        st.text_area(
            f"Proposed Replacement {index}",
            value=item["replacement_text"],
            height=130,
            disabled=True,
            key=f"{key_prefix}-replacement-{index}",
        )

    if item["suggestions"]:
        suggestion_lines = [
            f"{suggestion['score']}: {format_preview_text(suggestion['text'], 180)}"
            for suggestion in item["suggestions"]
        ]
        st.caption("Closest resume paragraphs:")
        st.code("\n\n".join(suggestion_lines), language="text")


def render_review_section(title: str, items: list[dict], expanded: bool = False) -> None:
    """Render one grouped review section with progressive disclosure."""
    count_label = _section_label(len(items), "change", "changes")
    section_slug = title.lower().replace(" ", "-")
    with st.expander(f"{title} · {count_label}", expanded=expanded):
        if not items:
            st.caption("No changes in this section.")
            return

        if title != "Bullet Points" and len(items) == 1:
            render_replacement_preview(items[0], 1, f"{section_slug}-1", show_status=True)
            return

        for index, item in enumerate(items, start=1):
            status = item["status"]
            if status == "matched":
                status_label = "✏️ AI-updated"
            elif status == "duplicate":
                status_label = "⚠️ Needs manual review"
            else:
                status_label = "⚠️ Needs manual review"

            nested_title = f"{index}. {status_label}"
            if title == "Bullet Points":
                nested_title = f"{index}. {status_label} · {format_preview_text(item['replacement_text'], 72)}"

            with st.expander(nested_title, expanded=(len(items) == 1 and expanded)):
                render_replacement_preview(item, index, f"{section_slug}-{index}", show_status=False)
