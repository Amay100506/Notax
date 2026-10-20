"""
UI Components and HTML helpers for NotifyIQ Streamlit Dashboard.
"""

import streamlit as st


def render_metric_card(title: str, value: str | int, subtitle: str = "", delta_color: str = "#6366F1"):
    """Renders a styled KPI metric card with clean typography."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        ">
            <div style="font-size: 0.85rem; font-weight: 500; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
                {title}
            </div>
            <div style="font-size: 1.85rem; font-weight: 700; color: #F8FAFC; margin-bottom: 4px;">
                {value}
            </div>
            <div style="font-size: 0.8rem; color: #64748B;">
                {subtitle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_priority_badge(level: str, score: float) -> str:
    """Returns HTML for an accessible priority indicator badge."""
    lvl = level.lower()
    if lvl == "high":
        bg, text_color = "rgba(239, 68, 68, 0.15)", "#EF4444"
        icon = "🔴"
    elif lvl == "medium":
        bg, text_color = "rgba(245, 158, 11, 0.15)", "#F59E0B"
        icon = "🟡"
    else:
        bg, text_color = "rgba(16, 185, 129, 0.15)", "#10B981"
        icon = "🟢"

    return f"""<span style="background-color: {bg}; color: {text_color}; border: 1px solid {text_color}44; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 0.82rem;">{icon} {lvl.upper()} ({score:.0f})</span>"""


def render_category_badge(category: str) -> str:
    """Returns HTML for category tag."""
    cat = category.replace("_", " ").title()
    return f"""<span style="background-color: rgba(99, 102, 241, 0.15); color: #818CF8; border: 1px solid rgba(99, 102, 241, 0.3); padding: 3px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 500;">{cat}</span>"""
