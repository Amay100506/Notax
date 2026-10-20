"""
NotifyIQ — Privacy-First, Explainable AI System for Android Notification Prioritization.
Streamlit Interactive Dashboard (v2.0 — Enhanced with Shopping Intelligence).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
import pandas as pd
from backend.database.connection import init_db
from backend.database.repository import Repository
from backend.services.import_service import ImportService
from backend.services.notification_service import NotificationService, InboxFilters
from backend.utils.configuration import settings
from dashboard.charts import (
    build_category_distribution_chart,
    build_confusion_matrix_chart,
    build_priority_distribution_chart,
    build_priority_radar_chart,
    build_timeline_volume_chart,
)
from dashboard.components import render_category_badge, render_metric_card, render_priority_badge

# Page Configuration
st.set_page_config(
    page_title="NotifyIQ — Intelligent Notification Prioritization",
    page_icon="🔔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    h1, h2, h3 { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-weight: 600; }
    .stMetric { background: rgba(255,255,255,0.03); border-radius: 8px; padding: 12px; }
    .reason-box {
        background-color: rgba(99, 102, 241, 0.08);
        border-left: 3px solid #6366F1;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-radius: 0 6px 6px 0;
        font-size: 0.9rem;
    }
    .deal-card {
        background: linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(99,102,241,0.05) 100%);
        border: 1px solid rgba(16,185,129,0.25);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .coupon-code {
        background: rgba(245,158,11,0.15);
        border: 2px dashed #F59E0B;
        border-radius: 8px;
        padding: 8px 16px;
        font-family: monospace;
        font-size: 1.1rem;
        font-weight: 700;
        color: #F59E0B;
        display: inline-block;
        margin: 4px 8px 4px 0;
    }
    .attention-alert {
        background: rgba(239,68,68,0.08);
        border-left: 4px solid #EF4444;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Database & Repository
init_db()
repo = Repository()
import_service = ImportService(repository=repo)
notif_service = NotificationService(repository=repo)


def _safe_shopping_import():
    """Safely import shopping modules — returns None if not yet available."""
    try:
        from backend.services.shopping_service import ShoppingService
        return ShoppingService()
    except Exception:
        return None


def main():
    # Sidebar Navigation
    st.sidebar.image("https://img.icons8.com/fluency/96/appointment-reminders.png", width=48)
    st.sidebar.title("NotifyIQ")
    st.sidebar.caption("Explainable AI Notification Intelligence")

    pages = [
        "Overview",
        "Smart Inbox",
        "Notification Details",
        "Action Center",
        "Duplicate Center",
        "🛒 Shopping Intelligence",
        "Analytics & Evaluation",
        "Settings & Privacy",
        "📱 Mobile App & Live Sync",
    ]
    selected_page = st.sidebar.radio("Navigation", pages, index=0)

    st.sidebar.divider()
    st.sidebar.subheader("⚡ Live Ingestion & Sync")

    # Auto-Refresh selector
    refresh_option = st.sidebar.selectbox(
        "Auto-Refresh Rate",
        ["Off", "3 seconds", "5 seconds", "10 seconds", "30 seconds"],
        index=2,
        help="Periodically updates notification counts and smart inbox without restarting the app.",
    )
    if st.sidebar.button("🔄 Refresh Data Now"):
        st.rerun()

    # Server Status Check
    server_online = False
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8000/forward/status", timeout=1) as resp:
            if resp.status == 200:
                server_online = True
    except Exception:
        pass

    if server_online:
        st.sidebar.success("🟢 Server: Online (Port 8000)")
    else:
        st.sidebar.warning("🟡 Server: Offline (Start FastAPI)")

    # Android Ingestion Status
    latest_ingest = repo.get_setting("latest_forward_ingestion_at")
    total_forwarded = repo.get_setting("total_forwarded_count") or "0"

    if latest_ingest:
        try:
            dt = datetime.fromisoformat(latest_ingest.replace("Z", "+00:00"))
            delta_sec = (datetime.now(timezone.utc) - dt).total_seconds()
            if delta_sec < 60:
                st.sidebar.success(f"🟢 Android: Active ({int(delta_sec)}s ago)")
            elif delta_sec < 3600:
                st.sidebar.info(f"🟡 Android: Idle ({int(delta_sec // 60)}m ago)")
            else:
                st.sidebar.info(f"⚪ Last Ingestion: {dt.strftime('%H:%M:%S UTC')}")
        except Exception:
            st.sidebar.info(f"⚪ Last Ingest: {latest_ingest[:19]}")
    else:
        st.sidebar.caption("⚪ Android: Awaiting connection")

    summary_counts = repo.get_analytics_summary()
    st.sidebar.caption(f"📱 Forwarded Events: **{total_forwarded}**")
    st.sidebar.caption(f"🧠 Processed in DB: **{summary_counts['total_notifications']}**")

    st.sidebar.divider()
    st.sidebar.caption("🔒 **Privacy Guarantee**: All processing and SQLite persistence remain strictly local on your machine. No notification text is transmitted to external clouds.")

    # -------------------------------------------------------------
    # PAGE 1: OVERVIEW
    # -------------------------------------------------------------
    if selected_page == "Overview":
        st.title("System Overview & Live Pulse")
        st.markdown("Real-time intelligence dashboard calculated from your captured notifications.")

        # Live Real-Time Ingestion Pulse Banner
        b1, b2, b3 = st.columns([2.5, 1, 1])
        with b1:
            if latest_ingest:
                st.caption(f"⚡ **Live Sync Active** • Last Android event: `{latest_ingest[:19].replace('T', ' ')} UTC` • Forwarded: **{total_forwarded}**")
            else:
                st.caption(f"⚡ **Live Sync Ready** • Awaiting Android forwarding • Total Processed: **{summary_counts['total_notifications']}**")
        with b2:
            st.caption(f"⏱️ Refresh: **{refresh_option}**")
        with b3:
            if st.button("🔄 Refresh Data", key="sync_pulse_overview"):
                st.rerun()

        summary = repo.get_analytics_summary()
        if summary["total_notifications"] == 0:
            st.info("👋 Welcome to NotifyIQ! Your notification database is currently empty.")
            st.markdown(
                """
                To populate realistic notifications:
                1. Click below to run `python scripts/import_notifications.py --file data/sample_notifications.json`
                2. Or use the **Settings & Privacy** page to upload Android JSON export.
                """
            )
            if st.button("🚀 Load 50 Sample Notifications Now"):
                sample_file = BASE_DIR / "data" / "sample_notifications.json"
                if sample_file.exists():
                    from backend.ai.pipeline import AIPipeline
                    pipe = AIPipeline(repository=repo)
                    report = import_service.import_file(sample_file)
                    for ev in report.accepted_records:
                        pipe.process_notification(ev, persist=True)
                    st.success(f"Successfully processed and stored {report.accepted_count} sample notifications!")
                    st.rerun()
            return

        # KPI Metrics Cards — expanded to 6
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            render_metric_card("Total Captured", summary["total_notifications"], "Stored in local SQLite")
        with c2:
            render_metric_card("High Priority", summary["high_priority"], "Requires urgent attention", "#EF4444")
        with c3:
            render_metric_card("Actions Detected", summary["action_required"], "Tasks & requests detected", "#6366F1")
        with c4:
            render_metric_card("Duplicates Grouped", summary["duplicate_count"], "Identical & near alerts", "#10B981")
        with c5:
            render_metric_card("Promotional", summary["promotional_count"], "Marketing & offers", "#8B5CF6")
        with c6:
            render_metric_card("Needs Review", summary["needs_review_count"], "Low-confidence AI", "#F59E0B")

        st.divider()

        # Date Range Filter for Overview
        date_col1, date_col2, _ = st.columns([1, 1, 2])
        with date_col1:
            start_date = st.date_input("From Date", value=None, key="overview_start")
        with date_col2:
            end_date = st.date_input("To Date", value=None, key="overview_end")

        # Visual Charts
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.subheader("Priority Distribution")
            prio_data = repo.get_priority_counts()
            st.plotly_chart(build_priority_distribution_chart(prio_data), use_container_width=True)

        with col_right:
            st.subheader("Category Distribution")
            cat_data = repo.get_category_counts()
            st.plotly_chart(build_category_distribution_chart(cat_data), use_container_width=True)

        # Timeline Volume
        st.subheader("Notification Volume Over Time")
        timeline_data = repo.get_timeline_volume()
        st.plotly_chart(build_timeline_volume_chart(timeline_data), use_container_width=True)

        # Attention Summary
        st.subheader("🚨 Items Needing Your Attention")
        attention = notif_service.get_attention_summary()
        if attention.total_attention_count == 0:
            st.success("✅ All clear! No items currently need your attention.")
        else:
            att_cols = st.columns(4)
            with att_cols[0]:
                st.metric("Overdue Deadlines", attention.overdue_count)
            with att_cols[1]:
                st.metric("Unread High Priority", attention.unread_high_priority_count)
            with att_cols[2]:
                st.metric("Open Actions", attention.open_action_count)
            with att_cols[3]:
                st.metric("Needs Review", attention.needs_review_count)

            # Show top urgent items
            for item in attention.unread_high_priority[:5]:
                st.markdown(
                    f"""
                    <div class="attention-alert">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <strong style="font-size: 1.05rem;">{item.get('title') or 'No Title'}</strong>
                            <span>{render_priority_badge(item['priority_level'], item['priority_score'])}</span>
                        </div>
                        <div style="font-size: 0.82rem; color: #94A3B8; margin-bottom: 6px;">
                            📱 <code>{item['package_name']}</code> | 🕒 {item['received_at'][:19].replace('T', ' ')}
                        </div>
                        <div style="font-size: 0.92rem; color: #E2E8F0; margin-bottom: 8px;">
                            {item.get('text') or ''}
                        </div>
                        <div style="font-size: 0.8rem; color: #CBD5E1;">
                            💡 <em>{'; '.join(item.get('priority_reasons', []))}</em>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # -------------------------------------------------------------
    # PAGE 2: SMART INBOX (Enhanced)
    # -------------------------------------------------------------
    elif selected_page == "Smart Inbox":
        st.title("Smart Inbox")
        st.markdown("Searchable, explainable stream of incoming notifications with comprehensive filters.")

        # Live Real-Time Ingestion Pulse Banner
        ib1, ib2, ib3 = st.columns([2.5, 1, 1])
        with ib1:
            if latest_ingest:
                st.caption(f"⚡ **Real-Time Stream Active** • Latest: `{latest_ingest[:19].replace('T', ' ')} UTC` • Forwarded: **{total_forwarded}**")
            else:
                st.caption(f"⚡ **Stream Ready** • Awaiting Android companion • Total Notifications: **{summary_counts['total_notifications']}**")
        with ib2:
            st.caption(f"⏱️ Auto-Refresh: **{refresh_option}**")
        with ib3:
            if st.button("🔄 Sync Stream", key="sync_pulse_inbox"):
                st.rerun()

        # Enhanced Filters Bar — Row 1
        f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
        with f1:
            search_query = st.text_input("🔍 Search notifications...", placeholder="Keyword, title, or package name")
        with f2:
            prio_filter = st.selectbox("Priority Level", ["All", "high", "medium", "low"])
        with f3:
            cat_filter = st.selectbox(
                "Category",
                ["All", "action_required", "transactional", "social", "promotional", "system", "unknown"],
            )
        with f4:
            # Get unique package names for dropdown
            all_apps = repo.get_app_distribution()
            app_options = ["All"] + [a["package_name"] for a in all_apps]
            app_filter = st.selectbox("Source App", app_options)

        # Enhanced Filters Bar — Row 2
        f5, f6, f7, f8, f9, f10 = st.columns(6)
        with f5:
            action_only = st.checkbox("Has Action", key="inbox_action")
        with f6:
            deadline_only = st.checkbox("Has Deadline", key="inbox_deadline")
        with f7:
            unread_only = st.checkbox("Unread Only", key="inbox_unread")
        with f8:
            needs_review = st.checkbox("Needs Review", key="inbox_review")
        with f9:
            start_dt = st.date_input("From", value=None, key="inbox_start")
        with f10:
            end_dt = st.date_input("To", value=None, key="inbox_end")

        # Build filters
        filters = InboxFilters(
            search=search_query if search_query else None,
            priority_level=None if prio_filter == "All" else prio_filter,
            category=None if cat_filter == "All" else cat_filter,
            package_name=None if app_filter == "All" else app_filter,
            action_detected=True if action_only else None,
            deadline_detected=True if deadline_only else None,
            is_unread=True if unread_only else None,
            needs_review=True if needs_review else None,
            start_date=start_dt.isoformat() if start_dt else None,
            end_date=end_dt.isoformat() + "T23:59:59" if end_dt else None,
            limit=50,
        )

        inbox = notif_service.get_smart_inbox(filters)
        st.caption(f"Showing **{len(inbox.items)}** of **{inbox.total_count}** matching notifications")

        if not inbox.items:
            st.info("No notifications match your current filter settings.")
        else:
            for item in inbox.items:
                with st.expander(
                    f"{'🔴' if item['priority_level']=='high' else ('🟡' if item['priority_level']=='medium' else '🟢')} "
                    f"[{item['priority_score']:.0f}] {item.get('title') or '(No Title)'} — {item['package_name']}"
                ):
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        st.markdown(f"**Content:** {item.get('text')}")
                        st.markdown(f"**Received:** `{item['received_at']}`")
                        if item.get("action_detected"):
                            st.info(f"⚡ **Action:** {item.get('action_text')} ({item.get('action_type')})")
                        if item.get("deadline_status") == "resolved":
                            st.warning(f"⏰ **Deadline:** {item.get('deadline_text')} → `{item.get('deadline_at')}`")

                        st.markdown("**Explanation Reasons:**")
                        for r in item.get("priority_reasons", []):
                            st.markdown(f"<div class='reason-box'>• {r}</div>", unsafe_allow_html=True)

                    with col_b:
                        st.markdown(f"**Category:** {render_category_badge(item['category'])}", unsafe_allow_html=True)
                        st.markdown(f"**Confidence:** `{item['category_confidence']:.2f}` ({item['model_type']})")
                        st.markdown(f"**Priority Level:** `{item['priority_level'].upper()}` ({item['priority_score']:.1f}/100)")
                        if item.get("is_duplicate"):
                            st.markdown("🔁 *Grouped as duplicate alert*")
                        if item.get("is_deferred"):
                            st.markdown("💤 *Received during quiet hours*")

                        # Quick Action Buttons
                        btn_cols = st.columns(2)
                        with btn_cols[0]:
                            if st.button("✅ Mark Read", key=f"read_{item['id']}"):
                                repo.mark_notification_read(item['id'], True)
                                st.toast("Marked as read")
                        with btn_cols[1]:
                            if st.button("🗑️ Delete", key=f"del_{item['id']}"):
                                repo.delete_notification(item['id'])
                                st.toast("Deleted")
                                st.rerun()

    # -------------------------------------------------------------
    # PAGE 3: NOTIFICATION DETAILS & EXPLAINABILITY
    # -------------------------------------------------------------
    elif selected_page == "Notification Details":
        st.title("Notification Deep Inspection & Feedback")
        st.markdown("Inspect priority score mechanics, component breakdown, and provide active feedback.")

        all_items, count = repo.list_notifications(limit=100)
        if not all_items:
            st.warning("No notifications available to inspect.")
            return

        options = {f"[{it['priority_score']:.0f}] {it.get('title') or it['package_name']} ({it['id'][:8]})": it['id'] for it in all_items}
        selected_label = st.selectbox("Select Notification to Inspect", list(options.keys()))
        selected_id = options[selected_label]
        item = repo.get_notification_by_id(selected_id)

        if item:
            col_left, col_right = st.columns([1, 1])
            with col_left:
                st.subheader("Notification Metadata")
                st.write(f"**ID:** `{item['id']}`")
                st.write(f"**Event ID:** `{item['event_id']}`")
                st.write(f"**Source Package:** `{item['package_name']}`")
                st.write(f"**Received At:** `{item['received_at']}`")
                st.write(f"**Title:** {item.get('title')}")
                st.text_area("Permitted Content", value=item.get("text") or "", height=100, disabled=True)
                st.text_area("Normalized Classification Text", value=item.get("normalized_text") or "", height=70, disabled=True)

                st.subheader("Traceable AI Explanations")
                for r in item.get("priority_reasons", []):
                    st.markdown(f"<div class='reason-box'>🔍 {r}</div>", unsafe_allow_html=True)

            with col_right:
                st.subheader("Priority Formula Breakdown")
                st.caption("P = 0.30*U + 0.25*A + 0.25*D + 0.15*I + 0.05*R")
                breakdown = {
                    "urgency_score": item["urgency_score"],
                    "action_score": item["action_score"],
                    "deadline_score": item["deadline_score"],
                    "importance_score": item["importance_score"],
                    "recency_score": item["recency_score"],
                }
                st.plotly_chart(build_priority_radar_chart(breakdown), use_container_width=True)

                c_u, c_a, c_d, c_i, c_r = st.columns(5)
                c_u.metric("Urgency", f"{item['urgency_score']:.0f}")
                c_a.metric("Action", f"{item['action_score']:.0f}")
                c_d.metric("Deadline", f"{item['deadline_score']:.0f}")
                c_i.metric("Importance", f"{item['importance_score']:.0f}")
                c_r.metric("Recency", f"{item['recency_score']:.0f}")

            st.divider()

            # Active Learning Feedback Section — Enhanced with all correction types
            st.subheader("✍️ Provide Human-in-the-Loop Feedback")
            st.caption("Correct any model prediction. Feedback is stored locally in SQLite to train future iterations.")
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                with st.form("feedback_category_form"):
                    st.write("**Correct Category Classification:**")
                    new_cat = st.selectbox(
                        "New Category",
                        ["action_required", "transactional", "social", "promotional", "system", "unknown"],
                        index=["action_required", "transactional", "social", "promotional", "system", "unknown"].index(item["category"]) if item["category"] in ["action_required", "transactional", "social", "promotional", "system", "unknown"] else 0,
                    )
                    submitted_cat = st.form_submit_button("Save Category Correction")
                    if submitted_cat:
                        repo.record_feedback(
                            notification_id=item["id"],
                            feedback_type="category",
                            original_value=item["category"],
                            corrected_value=new_cat,
                        )
                        st.success(f"Updated category from '{item['category']}' to '{new_cat}' and recorded feedback!")
                        st.rerun()

            with fcol2:
                with st.form("feedback_priority_form"):
                    st.write("**Adjust Priority Level:**")
                    new_prio = st.selectbox("Corrected Priority", ["high", "medium", "low"], index=["high", "medium", "low"].index(item["priority_level"]))
                    submitted_prio = st.form_submit_button("Save Priority Adjustment")
                    if submitted_prio:
                        repo.record_feedback(
                            notification_id=item["id"],
                            feedback_type="priority_level",
                            original_value=item["priority_level"],
                            corrected_value=new_prio,
                        )
                        st.success(f"Updated priority level to '{new_prio}' and recorded feedback!")
                        st.rerun()

            # Additional Feedback — Action and Deadline corrections
            fcol3, fcol4 = st.columns(2)
            with fcol3:
                with st.form("feedback_action_form"):
                    st.write("**Action Detection Feedback:**")
                    current_action = "Yes" if item.get("action_detected") else "No"
                    action_correct = st.selectbox(
                        "Is the action detection correct?",
                        ["Yes — correct", "No — false positive (no real action)", "No — missed action"],
                    )
                    submitted_action = st.form_submit_button("Save Action Feedback")
                    if submitted_action:
                        corrected = "correct" if "correct" in action_correct else ("false_positive" if "false positive" in action_correct else "false_negative")
                        repo.record_feedback(
                            notification_id=item["id"],
                            feedback_type="action_detection",
                            original_value=current_action,
                            corrected_value=corrected,
                        )
                        st.success("Action detection feedback recorded!")

            with fcol4:
                with st.form("feedback_deadline_form"):
                    st.write("**Deadline Detection Feedback:**")
                    current_dl = item.get("deadline_status", "none")
                    dl_correct = st.selectbox(
                        "Is the deadline detection correct?",
                        ["Yes — correct", "No — false positive (no real deadline)", "No — missed deadline"],
                    )
                    submitted_dl = st.form_submit_button("Save Deadline Feedback")
                    if submitted_dl:
                        corrected = "correct" if "correct" in dl_correct else ("false_positive" if "false positive" in dl_correct else "false_negative")
                        repo.record_feedback(
                            notification_id=item["id"],
                            feedback_type="deadline_detection",
                            original_value=current_dl,
                            corrected_value=corrected,
                        )
                        st.success("Deadline detection feedback recorded!")

    # -------------------------------------------------------------
    # PAGE 4: ACTION CENTER
    # -------------------------------------------------------------
    elif selected_page == "Action Center":
        st.title("Action Center")
        st.markdown("Track and manage actionable requests extracted from your notifications.")

        status_tab = st.radio("Status Filter", ["All", "open", "completed", "dismissed"], horizontal=True)
        status_filter = None if status_tab == "All" else status_tab
        actions = repo.list_actions(status=status_filter, limit=100)

        st.caption(f"Showing **{len(actions)}** actions")

        if not actions:
            st.info("No action items match the selected status.")
        else:
            for act in actions:
                with st.container():
                    col_act1, col_act2, col_act3 = st.columns([3, 1, 1])
                    with col_act1:
                        st.markdown(f"**⚡ {act['action_text']}**")
                        st.caption(f"App: <code>{act['package_name']}</code> | Type: `{act['action_type']}` | Ref: *{act.get('notification_title') or 'Notification'}*", unsafe_allow_html=True)
                        if act.get("deadline_at"):
                            st.warning(f"⏰ Deadline: `{act['deadline_at'][:19].replace('T', ' ')}`")

                    with col_act2:
                        st.markdown(f"Status: **`{act['status'].upper()}`**")

                    with col_act3:
                        if act["status"] == "open":
                            if st.button("Complete", key=f"comp_{act['id']}"):
                                repo.update_action_status(act["id"], "completed")
                                st.rerun()
                            if st.button("Dismiss", key=f"dism_{act['id']}"):
                                repo.update_action_status(act["id"], "dismissed")
                                st.rerun()
                        else:
                            if st.button("Reopen", key=f"reopen_{act['id']}"):
                                repo.update_action_status(act["id"], "open")
                                st.rerun()
                    st.divider()

    # -------------------------------------------------------------
    # PAGE 5: DUPLICATE CENTER
    # -------------------------------------------------------------
    elif selected_page == "Duplicate Center":
        st.title("Duplicate Grouping Center")
        st.markdown("Inspect duplicate groups formed via exact fingerprinting and conservative similarity.")

        groups = repo.list_duplicate_groups()
        if not groups:
            st.info("No repeated or duplicate notification groups found.")
        else:
            st.success(f"Identified **{len(groups)}** duplicate clusters.")
            for g in groups:
                with st.expander(f"🔁 Cluster `{g['id'][:8]}` — {g['group_size']} notifications (Method: {g.get('grouping_method', g.get('group_method', 'unknown'))})"):
                    st.write(f"**Representative Sample:** {g.get('sample_title')}")
                    st.write(f"**Fingerprint:** `{g['fingerprint']}`")
                    members = repo.get_group_members(g["id"])
                    st.markdown("**Cluster Members:**")
                    for m in members:
                        st.markdown(f"- 🕒 `{m['received_at'][:19]}` | **{m.get('title')}**: {m.get('text')} *(Event: `{m['event_id']}`)*")

    # -------------------------------------------------------------
    # PAGE 6: SHOPPING INTELLIGENCE (BuyHatke-like)
    # -------------------------------------------------------------
    elif selected_page == "🛒 Shopping Intelligence":
        st.title("🛒 Shopping Intelligence — Smart Deal Tracker")
        st.markdown(
            "Automatically detect prices, score deals, extract coupon codes, and track price "
            "drops from your shopping notifications. *Inspired by BuyHatke.*"
        )

        shopping_svc = _safe_shopping_import()
        if shopping_svc is None:
            st.warning("Shopping service is loading... Please reload the page in a few seconds.")
            return

        # Ensure shopping tables exist
        shopping_svc.ensure_shopping_tables()

        # Load shopping data if no shopping notifications exist
        shop_tab1, shop_tab2, shop_tab3, shop_tab4, shop_tab5 = st.tabs([
            "🏷️ Best Deals", "🎟️ Coupon Codes", "📈 Price Tracker", "📊 Shopping Analytics", "🧩 Browser Extension (BuyHatke-Style)"
        ])

        with shop_tab1:
            st.subheader("Top Deals Detected from Your Notifications")

            # Quick-load shopping data
            shopping_file = BASE_DIR / "data" / "shopping_notifications.json"
            if st.button("🛍️ Load 40 Shopping Notifications", key="load_shopping"):
                if shopping_file.exists():
                    from backend.ai.pipeline import AIPipeline
                    pipe = AIPipeline(repository=repo)
                    report = import_service.import_file(shopping_file)
                    for ev in report.accepted_records:
                        result = pipe.process_notification(ev, persist=True)
                        # Run shopping analysis on each
                        try:
                            shopping_svc.analyze_and_store(result)
                        except Exception:
                            pass
                    st.success(f"Loaded {report.accepted_count} shopping notifications!")
                    st.rerun()

            # Get best deals
            try:
                deals = shopping_svc.get_best_deals(limit=20)
            except Exception:
                deals = []

            if not deals:
                st.info("No deals detected yet. Load shopping notifications or process notifications with shopping content.")
            else:
                for deal in deals:
                    quality = deal.get("quality_label", "fair")
                    emoji = "🔥" if quality == "excellent" else ("⭐" if quality == "good" else "📦")
                    score = deal.get("deal_score", 0)
                    coupon_display = ""
                    raw_coupons = deal.get("coupon_codes", [])
                    if isinstance(raw_coupons, list) and raw_coupons:
                        coupon_display = ", ".join(str(c) for c in raw_coupons)
                    elif isinstance(raw_coupons, str) and raw_coupons and raw_coupons != "[]":
                        coupon_display = raw_coupons.strip("[]'\"")
                    if coupon_display:
                        coupon_html = f'<div style="margin-top: 6px;"><span class="coupon-code">🎟️ CODE: {coupon_display}</span></div>'
                    else:
                        coupon_html = ""

                    st.markdown(
                        f"""
                        <div class="deal-card">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong style="font-size: 1.1rem;">{emoji} {deal.get('product_title') or 'Shopping Deal'}</strong>
                                <span style="background: rgba(16,185,129,0.2); color: #10B981; padding: 4px 10px; border-radius: 20px; font-weight: 700;">
                                    Score: {score:.0f}/100
                                </span>
                            </div>
                            <div style="margin-top: 8px; font-size: 0.9rem;">
                                {f'💰 ₹{deal.get("original_price", 0):,.0f} → ₹{deal.get("discounted_price", 0):,.0f}' if deal.get('discounted_price') else ''}
                                {f'<span style="color: #10B981; font-weight: 600;"> ({deal.get("discount_percent", 0):.0f}% OFF)</span>' if deal.get('discount_percent') else ''}
                            </div>
                            <div style="margin-top: 4px; font-size: 0.82rem; color: #94A3B8;">
                                🏪 {deal.get('source_app', 'Unknown')} | 🕒 {str(deal.get('detected_at', ''))[:19].replace('T', ' ')}
                                {' | ⚡ TIME-SENSITIVE' if deal.get('is_time_sensitive') else ''}
                            </div>
                            {coupon_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        with shop_tab2:
            st.subheader("🎟️ Detected Coupon Codes")
            st.caption("Automatically extracted from your shopping notifications.")

            try:
                coupons = shopping_svc.get_all_coupons()
            except Exception:
                coupons = []

            if not coupons:
                st.info("No coupon codes detected yet.")
            else:
                for c in coupons:
                    code = c.get("coupon_code") or c.get("coupon_codes", "")
                    if code:
                        st.markdown(
                            f'<span class="coupon-code">🏷️ {code}</span>',
                            unsafe_allow_html=True,
                        )
                        disc = c.get("discount_percent")
                        disc_str = f" | {disc:.0f}% OFF" if disc else ""
                        st.caption(f"From: {c.get('source_app', 'Unknown')} | {c.get('product_title', '')}{disc_str}")
                        st.divider()

        with shop_tab3:
            st.subheader("📈 Price History Tracker")
            st.caption("Track price changes for products across your notifications.")

            try:
                price_history = shopping_svc.get_all_price_history(limit=50)
            except Exception:
                price_history = []

            if price_history:
                ph_df = pd.DataFrame(price_history)
                if "product_title" in ph_df.columns and "price" in ph_df.columns:
                    # Group by product
                    products = ph_df["product_title"].unique()
                    selected_product = st.selectbox("Select Product", list(products))
                    product_data = ph_df[ph_df["product_title"] == selected_product].sort_values("observed_at")

                    if len(product_data) > 1:
                        import plotly.express as px
                        fig = px.line(product_data, x="observed_at", y="price",
                                      title=f"Price History: {selected_product}",
                                      color_discrete_sequence=["#6366F1"])
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.metric("Current Price", f"₹{product_data['price'].iloc[0]:,.2f}")
                        st.caption(f"Observed: {product_data['observed_at'].iloc[0]}")
            else:
                st.info("No price history data available yet.")

        with shop_tab4:
            st.subheader("📊 Shopping Analytics")
            try:
                summary_obj = shopping_svc.get_shopping_summary()
                time_sens_count = shopping_svc.get_time_sensitive_count()
                sm1, sm2, sm3, sm4 = st.columns(4)
                with sm1:
                    render_metric_card("Active Deals", summary_obj.active_deals_count, "Deals detected")
                with sm2:
                    render_metric_card("Coupons Found", summary_obj.coupons_found, "Promo codes", "#F59E0B")
                with sm3:
                    render_metric_card("Avg Discount", f"{summary_obj.avg_discount_percent:.0f}%", "Average savings", "#10B981")
                with sm4:
                    render_metric_card("Time-Sensitive", time_sens_count, "Expiring soon", "#EF4444")

                # Top stores
                if summary_obj.top_stores:
                    st.subheader("Top Shopping Apps")
                    store_df = pd.DataFrame([s.model_dump() for s in summary_obj.top_stores])
                    st.dataframe(store_df, use_container_width=True)
            except Exception as e:
                st.info(f"Shopping analytics will populate as deals are detected.")

        with shop_tab5:
            st.subheader("🧩 BuyHatke-Style Browser Extension")
            st.markdown(
                """
                NotifyIQ includes a complete **Manifest V3 browser extension** for Chrome, Edge, and Brave.
                It runs seamlessly on **Amazon**, **Flipkart**, **Myntra**, and **Ajio** to show:
                - Floating badge with live AI deal quality score (0–100)
                - In-page price history trend chart
                - Available coupons with 1-click **Copy & Apply**
                - 1-click target price drop alert subscription synced directly with this dashboard!
                """
            )

            ext_col1, ext_col2 = st.columns([1.2, 1])
            with ext_col1:
                st.markdown("### 📥 3-Step Setup in Chrome or Edge")
                st.markdown(
                    f"""
                    1. Open **`chrome://extensions`** (or **`edge://extensions`**).
                    2. Enable **"Developer mode"** in the top-right corner.
                    3. Click **"Load unpacked"** and select:
                       ```
                       {str(BASE_DIR / 'extension')}
                       ```
                    4. Navigate to any product on [Amazon.in](https://www.amazon.in) or [Flipkart.com](https://www.flipkart.com) — the NotifyIQ pill will appear automatically!
                    """
                )

            with ext_col2:
                st.markdown("### 🧪 Test Extension API Gateway")
                st.caption("Verifies that the extension can connect to the local FastAPI shopping engine.")
                if st.button("⚡ Test Extension Connection", key="test_ext_btn"):
                    import requests
                    try:
                        res = requests.post(
                            "http://127.0.0.1:8000/shopping/extension/track",
                            json={
                                "product_title": "Sony WH-1000XM5 Wireless Headphones",
                                "current_price": 22990.0,
                                "original_price": 29990.0,
                                "currency": "INR",
                                "store": "Amazon",
                                "url": "https://www.amazon.in/dp/B09XS7JWHH",
                            },
                            timeout=3,
                        )
                        if res.status_code == 201:
                            data = res.json()
                            st.success(f"✅ Extension API Online! Scored: {data['deal_score']:.0f}/100 ({data['quality_label']})")
                            st.info(f"Verdict: {data['verdict']}")
                        else:
                            st.error(f"Error: {res.status_code} - {res.text}")
                    except Exception as ex:
                        st.error(f"Connection failed: {ex}")

    # -------------------------------------------------------------
    # PAGE 7: ANALYTICS & MODEL EVALUATION
    # -------------------------------------------------------------
    elif selected_page == "Analytics & Evaluation":
        st.title("Analytics & AI Model Evaluation")
        tab_ops, tab_eval = st.tabs(["📊 Operational Analytics", "🔬 Model Evaluation & Benchmarks"])

        with tab_ops:
            st.subheader("Per-Application Notification Analytics")
            app_stats = notif_service.get_notification_stats_by_app()
            if app_stats:
                app_df = pd.DataFrame(app_stats)
                display_cols = [c for c in ["package_name", "total_notifications", "high_priority_count",
                                           "medium_priority_count", "low_priority_count", "action_count",
                                           "deadline_count", "unread_count", "avg_priority_score"] if c in app_df.columns]
                st.dataframe(app_df[display_cols] if display_cols else app_df, use_container_width=True)
            else:
                st.info("No application distribution data available.")

            # Feedback Analysis
            st.subheader("📝 User Feedback History")
            feedback = repo.list_feedback(limit=50)
            if feedback:
                fb_df = pd.DataFrame(feedback)
                display_fb = [c for c in ["feedback_type", "original_value", "corrected_value",
                                         "notification_title", "package_name", "created_at"] if c in fb_df.columns]
                st.dataframe(fb_df[display_fb] if display_fb else fb_df, use_container_width=True)
            else:
                st.info("No feedback recorded yet. Use the Notification Details page to provide corrections.")

        with tab_eval:
            st.subheader("Held-Out Test Set Performance")
            report_file = settings.evaluation_report_path
            if not report_file.exists():
                st.warning("Model evaluation report not found. Run `python scripts/evaluate_model.py` to evaluate.")
            else:
                with open(report_file, "r", encoding="utf-8") as f:
                    eval_data = json.load(f)

                cat_m = eval_data["category_classification"]
                base_c = eval_data["baseline_comparison"]
                high_p = eval_data["high_priority_detection"]
                lat_m = eval_data["latency_ms"]

                # Benchmark Cards
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Category Accuracy", f"{cat_m['accuracy'] * 100:.1f}%")
                m2.metric("NotifyIQ Macro-F1", f"{cat_m['macro_f1']:.3f}", delta=f"+{base_c['macro_f1_improvement']:.3f} vs Baseline")
                m3.metric("High-Priority Precision", f"{high_p['precision'] * 100:.1f}%")
                m4.metric("Median Latency", f"{lat_m['median']:.1f} ms")

                st.divider()

                col_cm, col_perclass = st.columns([1, 1])
                with col_cm:
                    st.subheader("Confusion Matrix")
                    st.plotly_chart(
                        build_confusion_matrix_chart(cat_m["confusion_matrix"], cat_m["labels"]),
                        use_container_width=True,
                    )

                with col_perclass:
                    st.subheader("Per-Class Metrics")
                    per_class_df = pd.DataFrame.from_dict(cat_m["per_class"], orient="index")
                    st.dataframe(per_class_df.style.format("{:.2f}"), use_container_width=True)

                st.info(
                    "📌 **Evaluation Methodology Note**: Metrics were calculated on a held-out synthetic test set "
                    "(126 samples, distinct seed) comparing the scikit-learn TF-IDF + Logistic Regression model "
                    "against a deterministic rules-only baseline."
                )

    # -------------------------------------------------------------
    # PAGE 8: SETTINGS & PRIVACY (Enhanced)
    # -------------------------------------------------------------
    elif selected_page == "Settings & Privacy":
        st.title("Settings & Privacy Controls")
        st.markdown("NotifyIQ is designed privacy-first. You retain complete control over storage and retention.")

        st.subheader("🛡️ Privacy Policy & Security Guarantee")
        st.markdown(
            """
            - **Local Processing**: Ingestion, classification, scoring, and SQLite persistence run 100% locally on your machine.
            - **Zero Cloud APIs**: No notification text is ever dispatched to OpenAI, Anthropic, Google Cloud, or third-party cloud LLMs.
            - **No Raw Text in Logs**: Application logs only record event IDs and operational metrics.
            - **Local-Only API**: Default binds strictly to `127.0.0.1` (loopback interface).
            """
        )

        st.divider()

        # Configuration Controls
        st.subheader("⚙️ Application Configuration")
        cfg_col1, cfg_col2 = st.columns(2)
        with cfg_col1:
            with st.form("settings_form"):
                st.write("**AI & Processing Settings:**")
                stored = repo.get_all_settings()

                conf_thresh = st.slider(
                    "Classification Confidence Threshold",
                    min_value=0.3, max_value=0.95, step=0.05,
                    value=float(stored.get("confidence_threshold", str(settings.confidence_threshold))),
                    help="Notifications below this confidence level are flagged for review."
                )
                dup_thresh = st.slider(
                    "Near-Duplicate Similarity Threshold",
                    min_value=0.5, max_value=0.99, step=0.01,
                    value=float(stored.get("near_dup_threshold", str(settings.near_dup_threshold))),
                    help="Higher = stricter duplicate matching."
                )
                tz_select = st.selectbox(
                    "Timezone",
                    ["Asia/Kolkata", "UTC", "US/Eastern", "US/Pacific", "Europe/London", "Asia/Tokyo", "Australia/Sydney"],
                    index=0,
                )
                retention_days = st.number_input(
                    "Data Retention (days)",
                    min_value=1, max_value=365, step=1,
                    value=int(stored.get("retention_days", str(settings.retention_days_default))),
                    help="Notifications older than this are eligible for automatic cleanup."
                )
                save_settings = st.form_submit_button("💾 Save Settings")
                if save_settings:
                    repo.set_setting("confidence_threshold", str(conf_thresh))
                    repo.set_setting("near_dup_threshold", str(dup_thresh))
                    repo.set_setting("timezone", tz_select)
                    repo.set_setting("retention_days", str(retention_days))
                    st.success("Settings saved successfully!")

        with cfg_col2:
            # Quiet Hours
            st.write("**⏰ Quiet Hours Configuration:**")
            quiet_hours = notif_service.get_quiet_hours()
            qh_enabled = quiet_hours is not None
            enable_qh = st.checkbox("Enable Quiet Hours", value=qh_enabled)
            if enable_qh:
                qh_col1, qh_col2 = st.columns(2)
                with qh_col1:
                    qh_start = st.number_input("Start Hour (24h)", min_value=0, max_value=23,
                                               value=quiet_hours[0] if quiet_hours else 22)
                with qh_col2:
                    qh_end = st.number_input("End Hour (24h)", min_value=0, max_value=23,
                                             value=quiet_hours[1] if quiet_hours else 7)
                if st.button("Save Quiet Hours"):
                    notif_service.set_quiet_hours(qh_start, qh_end)
                    st.success(f"Quiet hours set: {qh_start:02d}:00 to {qh_end:02d}:00")
            elif not enable_qh and qh_enabled:
                notif_service.disable_quiet_hours()
                st.info("Quiet hours disabled.")

            # Package Exclusions
            st.write("**📵 Package Exclusion List:**")
            excluded = notif_service.get_excluded_packages()
            excluded_text = st.text_area(
                "Excluded packages (one per line)",
                value="\n".join(excluded),
                height=120,
                help="Notifications from these apps will be ignored during processing.",
            )
            if st.button("Save Exclusions"):
                new_excluded = [p.strip() for p in excluded_text.split("\n") if p.strip()]
                notif_service.manage_package_exclusions(new_excluded)
                st.success(f"Updated exclusion list: {len(new_excluded)} packages.")

        st.divider()

        # JSON File Upload
        st.subheader("📤 Import Notifications from Android")
        uploaded_file = st.file_uploader(
            "Upload Android JSON Export",
            type=["json"],
            help="Upload the JSON file exported from the NotifyIQ Android app.",
        )
        if uploaded_file is not None:
            content = uploaded_file.read().decode("utf-8")
            if st.button("🚀 Process Uploaded File"):
                from backend.ai.pipeline import AIPipeline
                pipe = AIPipeline(repository=repo)
                report = import_service.validate_and_filter_events(content)
                processed = 0
                for ev in report.accepted_records:
                    pipe.process_notification(ev, persist=True)
                    processed += 1
                st.success(
                    f"Import complete! Accepted: {report.accepted_count}, "
                    f"Rejected: {report.rejected_count}, "
                    f"Already Processed: {report.already_processed_count}"
                )
                if report.rejected_records:
                    with st.expander("View Rejected Records"):
                        st.json(report.rejected_records)
                st.rerun()

        st.divider()

        # Data Export
        st.subheader("📥 Data Export")
        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            json_export = import_service.export_notifications_json()
            st.download_button(
                "📥 Export Processed Notifications (JSON)",
                data=json_export,
                file_name="notifyiq_export.json",
                mime="application/json",
            )
        with c_exp2:
            csv_export = import_service.export_notifications_csv()
            st.download_button(
                "📥 Export Processed Notifications (CSV)",
                data=csv_export,
                file_name="notifyiq_export.csv",
                mime="text/csv",
            )

        st.divider()

        # Retention Cleanup
        st.subheader("🧹 Data Retention Cleanup")
        st.caption("Remove notifications that have exceeded their retention period.")
        if st.button("Run Retention Cleanup Now"):
            deleted = notif_service.cleanup_expired_retention()
            st.success(f"Cleanup complete: {deleted} expired notifications removed.")

        st.divider()

        # Purge
        st.subheader("🗑️ Purge & Delete Data")
        st.warning("Permanently wipe all captured notifications, actions, and feedback from the local database.")
        confirm_purge = st.checkbox("I confirm that I want to delete all stored notification records")
        if st.button("🗑️ Purge All Stored Data", type="primary", disabled=not confirm_purge):
            summary = repo.purge_all_data()
            st.success(f"Purge complete: Deleted {summary['deleted_notifications']} notifications and {summary['deleted_actions']} actions.")
            st.rerun()

    # -------------------------------------------------------------
    # PAGE 9: MOBILE APP & REAL-TIME SYNC
    # -------------------------------------------------------------
    elif selected_page == "📱 Mobile App & Live Sync":
        st.title("📱 Real-Time Mobile Companion & Notification Forwarding")
        st.markdown(
            "Stream Android notifications directly to NotifyIQ in real-time over your local network, "
            "or install the companion web app on any mobile device."
        )

        import io
        import socket
        import qrcode
        from backend.api.routes import get_or_create_api_key

        def get_lan_ip() -> str:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return "127.0.0.1"

        lan_ip = get_lan_ip()
        api_key = get_or_create_api_key(repo)

        # Tab navigation for Companion App and PWA Web App
        tab_android, tab_pwa, tab_test = st.tabs([
            "🤖 Android Real-Time Forwarding",
            "📱 Installable Mobile Web App",
            "⚡ Live Test Ingestion",
        ])

        # ---------------------------------------------------------
        # TAB 1: ANDROID REAL-TIME FORWARDING
        # ---------------------------------------------------------
        with tab_android:
            st.subheader("🤖 Android Kotlin Notification Forwarder")
            st.markdown(
                "NotifyIQ's Android companion app captures notification-posted events via `NotificationListenerService`, "
                "buffers them in a local persistent queue, and securely forwards them to this laptop via authenticated HTTP requests."
            )

            # Live Diagnostics Panel
            st.markdown("#### 📡 Real-Time Connection & Ingestion Diagnostics")
            d1, d2, d3, d4 = st.columns(4)

            # Check server connectivity
            server_live = False
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:8000/forward/status", timeout=1) as resp:
                    if resp.status == 200:
                        server_live = True
            except Exception:
                pass

            latest_ingest_time = repo.get_setting("latest_forward_ingestion_at")
            total_forwarded_count = repo.get_setting("total_forwarded_count") or "0"
            total_db_count = repo.get_analytics_summary()["total_notifications"]

            with d1:
                if server_live:
                    st.metric("FastAPI Server", "🟢 Online", f"Port {settings.port}")
                else:
                    st.metric("FastAPI Server", "🔴 Offline", "Start backend server")

            with d2:
                if latest_ingest_time:
                    try:
                        dt = datetime.fromisoformat(latest_ingest_time.replace("Z", "+00:00"))
                        delta = (datetime.now(timezone.utc) - dt).total_seconds()
                        if delta < 120:
                            st.metric("Android Capture", "🟢 Active", f"{int(delta)}s ago")
                        elif delta < 3600:
                            st.metric("Android Capture", "🟡 Idle", f"{int(delta // 60)}m ago")
                        else:
                            st.metric("Android Capture", "⚪ Connected", dt.strftime("%H:%M UTC"))
                    except Exception:
                        st.metric("Android Capture", "⚪ Active", latest_ingest_time[:19])
                else:
                    st.metric("Android Capture", "⚪ Awaiting", "No events yet")

            with d3:
                st.metric("Forwarded Events", total_forwarded_count, "From Android Queue")

            with d4:
                st.metric("Processed in DB", str(total_db_count), "SQLite Stored")

            st.divider()

            # Pairing Credentials Card
            col_cfg, col_qr_pair = st.columns([1.4, 1])

            with col_cfg:
                st.markdown("#### 🔑 Local Network Pairing Configuration")
                st.caption("Enter these credentials in the Android NotifyIQ app:")

                st.text_input("💻 Laptop IP Address", value=lan_ip, disabled=True)
                st.text_input("🔌 API Port", value=str(settings.port), disabled=True)
                
                c_key, c_regen = st.columns([3, 1])
                with c_key:
                    st.text_input("🔐 API Authentication Key", value=api_key, type="password", disabled=True)
                with c_regen:
                    st.write("")
                    st.write("")
                    if st.button("🔄 Rotate Key"):
                        import secrets
                        new_sec = f"notifyiq_sec_{secrets.token_hex(16)}"
                        repo.set_setting("api_key", new_sec)
                        st.success("New API key generated!")
                        st.rerun()

                st.info(
                    f"💡 **Direct Ingestion Endpoint**: `POST http://{lan_ip}:{settings.port}/notifications/forward`  \n"
                    f"Header: `X-NotifyIQ-API-Key: {api_key}`"
                )

            with col_qr_pair:
                st.markdown("#### 📷 Quick Scan Pairing")
                pairing_uri = f"notifyiq://pair?host={lan_ip}&port={settings.port}&key={api_key}"
                qr_pair = qrcode.QRCode(box_size=7, border=2)
                qr_pair.add_data(pairing_uri)
                qr_pair.make(fit=True)
                img_pair = qr_pair.make_image(fill_color="#4F46E5", back_color="white")
                buf_pair = io.BytesIO()
                img_pair.save(buf_pair, format="PNG")
                st.image(buf_pair.getvalue(), caption="Scan in Android App to pair instantly", width=220)

            st.divider()

            # Security and Network Considerations
            st.markdown("#### 🛡️ Local Network Security & Limitations")
            st.warning(
                "**Local Network (LAN) Threat Model Notice**  \n"
                "- **Trusted Home/Office Wi-Fi**: Plain HTTP with pre-shared API keys is lightweight and suitable for private local subnets.  \n"
                "- **Public/Untrusted Networks (Airports, Coffee Shops)**: Plain HTTP can be sniffed by other devices on the same Wi-Fi. "
                "Always run over a secure local VPN (such as WireGuard or Tailscale) or terminate TLS using a local reverse proxy (Caddy or Nginx) "
                "when operating on public networks. NotifyIQ never exposes its API to the public internet by default."
            )

        # ---------------------------------------------------------
        # TAB 2: PWA MOBILE WEB APP
        # ---------------------------------------------------------
        with tab_pwa:
            st.subheader("📱 Installable Progressive Web App (PWA)")
            st.markdown(
                "NotifyIQ also includes an installable PWA web client with live WebSocket push alerts "
                "and offline caching, accessible from any mobile browser."
            )

            mobile_url = f"http://{lan_ip}:8000/mobile"
            col_pwa_qr, col_pwa_info = st.columns([1, 1.4])
            with col_pwa_qr:
                qr = qrcode.QRCode(box_size=8, border=2)
                qr.add_data(mobile_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#4F46E5", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), caption=f"Scan to open: {mobile_url}", width=240)

            with col_pwa_info:
                st.markdown(
                    f"""
                    1. Connect phone to the **same Wi-Fi network**.
                    2. Open 👉 **[{mobile_url}]({mobile_url})**
                    3. **Install to Home Screen**:
                       - **Android (Chrome)**: Tap `⋮` → **Install App** / **Add to Home Screen**.
                       - **iOS (Safari)**: Tap Share → **Add to Home Screen**.
                    4. The app launches full-screen and connects live over WebSockets!
                    """
                )

        # ---------------------------------------------------------
        # TAB 3: LIVE TEST INGESTION
        # ---------------------------------------------------------
        with tab_test:
            st.subheader("⚡ Send Real-Time Test Forwarding Event")
            st.caption("Injects an authenticated event through the forwarding endpoint to test the AI pipeline, database persistence, and WebSocket broadcast live.")

            test_app = st.selectbox("Simulated App", ["Chase Banking", "Gmail Work", "Slack Team Sync", "Amazon Shopping"])
            test_title = st.text_input("Alert Title", value="Action Required: Confirm Identity Verification")
            test_text = st.text_input("Alert Body", value="Please complete your verification within 24 hours to prevent account freeze.")

            if st.button("🚀 Forward Live Test Event Now"):
                import requests
                test_event_id = f"test-fwd-{int(datetime.now().timestamp())}"
                pkg_name = "com.bank.secure" if "Bank" in test_app else ("com.google.android.gm" if "Gmail" in test_app else "com.slack")
                try:
                    res = requests.post(
                        "http://127.0.0.1:8000/notifications/forward",
                        headers={"X-NotifyIQ-API-Key": api_key},
                        json={
                            "notifications": [
                                {
                                    "schema_version": 1,
                                    "event_id": test_event_id,
                                    "package_name": pkg_name,
                                    "title": test_title,
                                    "text": test_text,
                                    "posted_at": datetime.now(timezone.utc).isoformat(),
                                    "event_type": "posted",
                                }
                            ],
                            "client_version": "1.0.0",
                        },
                        timeout=5,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        st.success(f"✅ Successfully ingested event `{test_event_id}`! (Accepted: {data['accepted_count']}, Duplicates: {data['duplicate_count']})")
                        st.rerun()
                    else:
                        st.error(f"Failed to forward: {res.text}")
                except Exception as ex:
                    st.error(f"Error reaching API: {ex}")
                    st.error(f"Error reaching API gateway: {ex}")


if __name__ == "__main__":
    main()
