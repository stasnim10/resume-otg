"""Render function for optimization history dashboard screen."""
from datetime import datetime
import streamlit as st
import logging
from profile_store import get_optimization_history

logger = logging.getLogger(__name__)


def render_optimization_history_screen() -> None:
    """Display past optimizations for the user."""
    from streamlit_app import render_shell_start, render_shell_end, render_screen_intro

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
                            <div style="font-size: 11px; color: #999; text-transform: uppercase;">BEFORE</div>
                            <div style="font-size: 28px; font-weight: bold;">{match_before}%</div>
                        </div>
                        <div style="font-size: 18px; color: #999;">ARROW</div>
                        <div style="text-align: center;">
                            <div style="font-size: 11px; color: #999; text-transform: uppercase;">AFTER</div>
                            <div style="font-size: 28px; font-weight: bold; color: #2ecc71;">{match_after}%</div>
                        </div>
                        <div style="padding: 0.5rem 0.75rem; background: #f0f0f0; border-radius: 4px; text-align: center;">
                            <div style="font-size: 11px; color: #666; text-transform: uppercase;">IMPROVEMENT</div>
                            <div style="font-size: 18px; font-weight: bold; color: #2ecc71;">{match_delta:+d}%</div>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: #999;">{date_str}</div>
                </div>""",
                    unsafe_allow_html=True,
                )

                improvements_count = opt.get("improvements_count", 0)
                if improvements_count > 0:
                    st.markdown(f'<div class="apple-minor-copy">✨ {improvements_count} improvements captured</div>', unsafe_allow_html=True)

                action_col1, action_col2, action_col3 = st.columns(3, gap="large")
                with action_col1:
                    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                    if st.button("Optimize Again", use_container_width=True, key=f"history-optimize-{opt['id']}"):
                        st.session_state.job_description = ""
                        st.session_state.screen = "input"
                        logger.info(f"User starting new optimization from history item {opt['id']}")
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

                with action_col2:
                    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                    st.button("View Details", use_container_width=True, key=f"history-view-{opt['id']}", disabled=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                with action_col3:
                    st.markdown('')

    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    with col1:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Start New Optimization", use_container_width=True):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Profile", use_container_width=True):
            st.session_state.screen = "profile_dashboard"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Home", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    render_shell_end()
