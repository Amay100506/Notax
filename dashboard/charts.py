"""
Plotly Chart Builders for NotifyIQ Dashboard.
Provides interactive visualizations with a modern, clean visual theme.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Any

COLOR_MAP_PRIORITY = {
    "high": "#EF4444",    # Vibrant red
    "medium": "#F59E0B",  # Amber / orange
    "low": "#10B981",     # Emerald green
}

COLOR_MAP_CATEGORY = {
    "action_required": "#6366F1",  # Indigo
    "transactional": "#0EA5E9",    # Sky blue
    "social": "#EC4899",           # Pink
    "promotional": "#8B5CF6",      # Purple
    "system": "#64748B",           # Slate
    "unknown": "#94A3B8",          # Neutral slate
}


def build_priority_distribution_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Builds a donut chart for priority level distribution."""
    if not data:
        fig = go.Figure()
        fig.update_layout(title="No Priority Data Available")
        return fig

    df = pd.DataFrame(data)
    colors = [COLOR_MAP_PRIORITY.get(lvl.lower(), "#94A3B8") for lvl in df["priority_level"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=df["priority_level"].str.capitalize(),
                values=df["count"],
                hole=0.55,
                marker=dict(colors=colors),
                textinfo="label+percent",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        margin=dict(t=30, b=20, l=20, r=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_category_distribution_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Builds a horizontal bar chart of notification categories."""
    if not data:
        fig = go.Figure()
        fig.update_layout(title="No Category Data Available")
        return fig

    df = pd.DataFrame(data).sort_values("count", ascending=True)
    colors = [COLOR_MAP_CATEGORY.get(cat.lower(), "#6366F1") for cat in df["category"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["count"],
                y=df["category"].str.replace("_", " ").str.title(),
                orientation="h",
                marker=dict(color=colors),
                text=df["count"],
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        margin=dict(t=30, b=20, l=40, r=20),
        xaxis_title="Notification Count",
        yaxis_title="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_priority_radar_chart(breakdown: dict[str, float]) -> go.Figure:
    """Builds a radar/spider chart showing component score breakdown (0-100)."""
    categories = ["Urgency (U)", "Action (A)", "Deadline (D)", "Importance (I)", "Recency (R)"]
    values = [
        breakdown.get("urgency_score", 0.0),
        breakdown.get("action_score", 0.0),
        breakdown.get("deadline_score", 0.0),
        breakdown.get("importance_score", 0.0),
        breakdown.get("recency_score", 0.0),
    ]
    # Close the radar polygon
    categories.append(categories[0])
    values.append(values[0])

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values,
                theta=categories,
                fill="toself",
                fillcolor="rgba(99, 102, 241, 0.25)",
                line=dict(color="#6366F1", width=2),
                marker=dict(size=6, color="#4F46E5"),
            )
        ]
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100]),
        ),
        margin=dict(t=30, b=30, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def build_timeline_volume_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Builds an area chart of notification volume across time buckets."""
    if not data:
        fig = go.Figure()
        fig.update_layout(title="No Timeline Data Available")
        return fig

    df = pd.DataFrame(data)
    fig = px.area(
        df,
        x="hour_bucket",
        y="count",
        labels={"hour_bucket": "Time (UTC Hour)", "count": "Volume"},
        color_discrete_sequence=["#3B82F6"],
    )
    fig.update_layout(
        margin=dict(t=30, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(150,150,150,0.15)"),
    )
    return fig


def build_confusion_matrix_chart(cm_data: list[list[int]], labels: list[str]) -> go.Figure:
    """Builds a heatmap visualization of the model confusion matrix."""
    formatted_labels = [l.replace("_", " ").title() for l in labels]
    fig = go.Figure(
        data=go.Heatmap(
            z=cm_data,
            x=formatted_labels,
            y=formatted_labels,
            colorscale="Blues",
            text=cm_data,
            texttemplate="%{text}",
            textfont={"size": 12},
        )
    )
    fig.update_layout(
        xaxis_title="Predicted Category",
        yaxis_title="True Category",
        margin=dict(t=30, b=30, l=50, r=30),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
