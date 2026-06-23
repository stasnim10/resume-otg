"""Render function for optimization history dashboard screen."""
from datetime import datetime
import streamlit as st
import logging
from profile_store import get_optimization_history
from shell import build_readiness_rows, render_shell_start, render_shell_end, render_screen_intro
from ui_helpers import primary_button, secondary_button

logger = logging.getLogger(__name__)


def render_optimization_history_screen() -> None:
    """Display past optimizations for the user."""
    render_shell_start()
    history = get_optimization_history(user_id="local-user")

    render_screen_intro(
        "optimization_history",
        "Past Optimizations",
        "Your application history.",
        "Review previous optimizations, compare match improvements, or try optimizing the same role again.",
    )

    if not history:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">No optimizations yet.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">Once you optimize a resume for a job, it will appear here. You can review past results and re-optimize roles later.</div>', unsafe_allow_html=True)
            if st.button("Start Your First Optimization", use_container_width=True):
                st.session_state.screen = "input"
                st.rerun()
    else:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Summary</div>', unsafe_allow_html=True)
            summary_col1, summary_col2, summary_col3 = st.columns(3, gap="large")
            with summary_col1:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Total Optimizations</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-value">{len(history)}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with summary_col2:
                avg_improvement = sum(int(h["match_after"]) - int(h["match_before"]) for h in history) / len(history)
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Average Improvement</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-value">+{avg_improvement:.0f}%</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with summary_col3:
                best_improvement = max(int(h["match_after"]) - int(h["match_before"]) for h in history)
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Best Improvement</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-value">+{best_improvement}%</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Optimization History</div>', unsafe_allow_html=True)

        for opt in history:
            with st.container(border=True):
                company_text = f" at {opt['company']}" if opt.get("company") else ""
                st.markdown(
                    f'<div class="apple-section-title">{opt.get("job_title", "Untitled role")}{company_text}</div>',
                    unsafe_allow_html=True,
                )

                try:
                    created_date = datetime.fromisoformat(opt["created_at"].replace("Z", "+00:00"))
                    date_str = created_date.strftime("%b %d, %Y")
                except (ValueError, AttributeError):
                    date_str = "Date unknown"

                match_before = int(opt.get("match_before", 0))
                match_after = int(opt.get("match_after", 0))
                match_delta = match_after - match_before

                st.markdown(
                    f"""<div style="display: flex; align-items: center; justify-content: space-between; margin: 1rem 0;">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="text-align: center;">
                            <div style="font-size: 11px; color: var(--muted-light); text-transform: uppercase;">BEFORE</div>
                            <div style="font-size: 28px; font-weight: bold; color: var(--text);">{match_before}%</div>
                        </div>
                        <div style="font-size: 18px; color: var(--muted);" aria-hidden="true">→</div>
                        <div style="text-align: center;">
                            <div style="font-size: 11px; color: var(--muted-light); text-transform: uppercase;">AFTER</div>
                            <div style="font-size: 28px; font-weight: bold; color: var(--green);">{match_after}%</div>
                        </div>
                        <div style="padding: 0.5rem 0.75rem; background: var(--surface-muted); border: 1px solid var(--line); border-radius: 8px; text-align: center;">
                            <div style="font-size: 11px; color: var(--muted-light); text-transform: uppercase;">IMPROVEMENT</div>
                            <div style="font-size: 18px; font-weight: bold; color: var(--green);">{match_delta:+d}%</div>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: var(--muted);">{date_str}</div>
                </div>""",
                    unsafe_allow_html=True,
                )

                improvements_count = opt.get("improvements_count", 0)
                if improvements_count > 0:
                    st.markdown(f'<div class="apple-minor-copy">{improvements_count} improvements captured</div>', unsafe_allow_html=True)

                action_col1, action_col2, action_col3 = st.columns(3, gap="large")
                with action_col1:
                    if primary_button("Optimize Again", key=f"history-optimize-{opt['id']}", use_container_width=True):
                        st.session_state.job_description = ""
                        st.session_state.screen = "input"
                        logger.info(f"User starting new optimization from history item {opt['id']}")
                        st.rerun()

                with action_col2:
                    if secondary_button("View Details", key=f"history-view-{opt['id']}", use_container_width=True):
                        active_detail = st.session_state.get("history_detail_open")
                        st.session_state.history_detail_open = None if active_detail == opt["id"] else opt["id"]
                        st.rerun()

                with action_col3:
                    st.markdown('')

                if st.session_state.get("history_detail_open") == opt["id"]:
                    with st.container(border=True):
                        st.markdown('<div class="apple-kicker">Details</div>', unsafe_allow_html=True)
                        st.markdown(
                            build_readiness_rows([
                                ("Execution mode", opt.get("execution_mode") or "Not recorded"),
                                ("Before score", f"{match_before}%"),
                                ("After score", f"{match_after}%"),
                                ("Score change", f"{match_delta:+d}%"),
                            ]),
                            unsafe_allow_html=True,
                        )
                        improvements = opt.get("improvements") or []
                        if improvements:
                            st.markdown('<div class="apple-section-copy">Captured improvements from this run:</div>', unsafe_allow_html=True)
                            for improvement in improvements[:8]:
                                if isinstance(improvement, dict):
                                    label = improvement.get("label") or improvement.get("type") or "Improvement"
                                    text = improvement.get("text") or improvement.get("description") or improvement.get("replacement_text") or ""
                                    st.markdown(f"- **{label}:** {text}" if text else f"- **{label}**")
                                else:
                                    st.markdown(f"- {improvement}")
                        else:
                            st.caption("No detailed improvements were stored for this older run.")

    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    with col1:
        if primary_button("Start New Optimization", key="history-new-opt", use_container_width=True):
            st.session_state.screen = "input"
            st.rerun()

    with col2:
        if secondary_button("Back to Profile", key="history-back-profile", use_container_width=True):
            st.session_state.screen = "profile_dashboard"
            st.rerun()

    with col3:
        if secondary_button("Home", key="history-home", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()

    render_shell_end()
