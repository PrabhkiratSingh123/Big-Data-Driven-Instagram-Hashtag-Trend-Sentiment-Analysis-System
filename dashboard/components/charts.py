"""
Reusable chart components for the Instagram Analytics dashboard.
All charts use Plotly with a consistent dark theme and gradient color palette.
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


# =====================================================================
# Theme Configuration
# =====================================================================

COLORS = {
    "primary": "#8B5CF6",       # Purple
    "secondary": "#06B6D4",     # Cyan
    "accent": "#10B981",        # Emerald
    "warning": "#F59E0B",       # Amber
    "danger": "#EF4444",        # Red
    "bg_dark": "#0B0B14",
    "bg_card": "#12121F",
    "bg_surface": "#1A1A2E",
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "grid": "rgba(139, 92, 246, 0.08)",
}

GRADIENT_PALETTE = [
    "#8B5CF6", "#7C3AED", "#06B6D4", "#0891B2",
    "#10B981", "#059669", "#F59E0B", "#D97706",
    "#EF4444", "#DC2626", "#EC4899", "#DB2777",
    "#6366F1", "#4F46E5", "#14B8A6", "#0D9488",
]

SENTIMENT_COLORS = {
    "positive": "#10B981",
    "neutral": "#6B7280",
    "negative": "#EF4444",
}

DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color=COLORS["text_primary"], size=13),
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(
        gridcolor=COLORS["grid"],
        zerolinecolor=COLORS["grid"],
        tickfont=dict(color=COLORS["text_secondary"]),
    ),
    yaxis=dict(
        gridcolor=COLORS["grid"],
        zerolinecolor=COLORS["grid"],
        tickfont=dict(color=COLORS["text_secondary"]),
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_secondary"]),
    ),
    hoverlabel=dict(
        bgcolor=COLORS["bg_surface"],
        font_size=13,
        font_family="Inter, sans-serif",
    ),
)


# =====================================================================
# Chart Functions
# =====================================================================

def create_trending_bar_chart(df: pd.DataFrame, x: str, y: str, title: str = "") -> go.Figure:
    """Horizontal bar chart for trending hashtags."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df[y],
        y=df[x],
        orientation="h",
        marker=dict(
            color=df[y],
            colorscale=[[0, "#06B6D4"], [0.5, "#8B5CF6"], [1, "#EC4899"]],
            line=dict(width=0),
            cornerradius=4,
        ),
        hovertemplate="<b>%{y}</b><br>Count: %{x:,}<extra></extra>",
    ))

    fig.update_layout(
        **DARK_LAYOUT,
        title=dict(text=title, font=dict(size=16, color=COLORS["text_primary"])),
        height=max(350, len(df) * 32),
        yaxis=dict(
            autorange="reversed",
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(color=COLORS["text_primary"], size=12),
        ),
        xaxis=dict(title="Post Count", gridcolor=COLORS["grid"]),
    )

    return fig


def create_trend_line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str = None,
    title: str = "",
) -> go.Figure:
    """Line chart for trend velocity over time."""
    if color and color in df.columns:
        fig = px.line(
            df, x=x, y=y, color=color,
            color_discrete_sequence=GRADIENT_PALETTE,
        )
    else:
        fig = px.line(df, x=x, y=y)
        fig.update_traces(
            line=dict(color=COLORS["primary"], width=2.5),
            fill="tozeroy",
            fillcolor="rgba(139, 92, 246, 0.1)",
        )

    fig.update_layout(
        **DARK_LAYOUT,
        title=dict(text=title, font=dict(size=16, color=COLORS["text_primary"])),
        height=400,
        xaxis=dict(title="Time"),
        yaxis=dict(title=y.replace("_", " ").title()),
    )

    return fig


def create_sentiment_donut(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Donut chart for sentiment distribution."""
    colors = [SENTIMENT_COLORS.get(label, COLORS["text_muted"]) for label in df["sentiment"]]

    fig = go.Figure(data=[go.Pie(
        labels=df["sentiment"],
        values=df["count"],
        hole=0.65,
        marker=dict(
            colors=colors,
            line=dict(color=COLORS["bg_dark"], width=3),
        ),
        textinfo="label+percent",
        textposition="outside",
        textfont=dict(size=13, color=COLORS["text_primary"]),
        hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>",
    )])

    # Center annotation
    total = df["count"].sum()
    fig.add_annotation(
        text=f"<b>{total:,}</b><br><span style='font-size:11px;color:{COLORS['text_secondary']}'>Total</span>",
        x=0.5, y=0.5,
        font=dict(size=24, color=COLORS["text_primary"]),
        showarrow=False,
    )

    fig.update_layout(
        **DARK_LAYOUT,
        title=dict(text=title, font=dict(size=16, color=COLORS["text_primary"])),
        height=400,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.1,
            xanchor="center",
            x=0.5,
        ),
    )

    return fig


def create_sentiment_timeline(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Stacked area chart showing sentiment over time."""
    fig = go.Figure()

    for sentiment in ["positive", "neutral", "negative"]:
        if sentiment in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index if "timestamp" not in df.columns else df["timestamp"],
                y=df[sentiment],
                name=sentiment.title(),
                mode="lines",
                stackgroup="sentiment",
                line=dict(width=0.5, color=SENTIMENT_COLORS[sentiment]),
                fillcolor=f"rgba({','.join(str(int(SENTIMENT_COLORS[sentiment][i:i+2], 16)) for i in (1, 3, 5))}, 0.4)",
                hovertemplate=f"<b>{sentiment.title()}</b><br>"
                             f"Count: %{{y:,}}<br>"
                             f"Time: %{{x}}<extra></extra>",
            ))

    fig.update_layout(
        **DARK_LAYOUT,
        title=dict(text=title, font=dict(size=16, color=COLORS["text_primary"])),
        height=400,
        yaxis=dict(title="Post Count"),
        xaxis=dict(title="Time"),
        hovermode="x unified",
    )

    return fig


def create_engagement_heatmap(df: pd.DataFrame, title: str = "") -> go.Figure:
    """Heatmap showing engagement rates across hashtags and time."""
    fig = go.Figure(data=go.Heatmap(
        z=df.values,
        x=df.columns,
        y=df.index,
        colorscale=[
            [0, "#0B0B14"],
            [0.25, "#1A1A5E"],
            [0.5, "#6D28D9"],
            [0.75, "#8B5CF6"],
            [1, "#C4B5FD"],
        ],
        hovertemplate="<b>%{y}</b> at <b>%{x}</b><br>Rate: %{z:.2f}<extra></extra>",
        colorbar=dict(
            title="Rate",
            titlefont=dict(color=COLORS["text_secondary"]),
            tickfont=dict(color=COLORS["text_secondary"]),
        ),
    ))

    fig.update_layout(
        **DARK_LAYOUT,
        title=dict(text=title, font=dict(size=16, color=COLORS["text_primary"])),
        height=450,
    )

    return fig


def create_scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    size: str = None,
    color: str = None,
    title: str = "",
) -> go.Figure:
    """Scatter chart for engagement analysis (e.g., likes vs comments)."""
    fig = px.scatter(
        df, x=x, y=y,
        size=size,
        color=color,
        color_discrete_sequence=GRADIENT_PALETTE,
        hover_data=df.columns.tolist(),
    )

    fig.update_traces(
        marker=dict(line=dict(width=1, color="rgba(0,0,0,0.3)")),
    )

    fig.update_layout(
        **DARK_LAYOUT,
        title=dict(text=title, font=dict(size=16, color=COLORS["text_primary"])),
        height=450,
        xaxis=dict(title=x.replace("_", " ").title()),
        yaxis=dict(title=y.replace("_", " ").title()),
    )

    return fig


def create_gauge_chart(value: float, title: str, max_val: float = 100) -> go.Figure:
    """Gauge chart for single metric display."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title=dict(text=title, font=dict(size=14, color=COLORS["text_secondary"])),
        number=dict(font=dict(size=28, color=COLORS["text_primary"])),
        gauge=dict(
            axis=dict(range=[0, max_val], tickcolor=COLORS["text_muted"]),
            bar=dict(color=COLORS["primary"]),
            bgcolor=COLORS["bg_card"],
            bordercolor="rgba(0,0,0,0)",
            steps=[
                dict(range=[0, max_val * 0.33], color="rgba(239, 68, 68, 0.1)"),
                dict(range=[max_val * 0.33, max_val * 0.66], color="rgba(245, 158, 11, 0.1)"),
                dict(range=[max_val * 0.66, max_val], color="rgba(16, 185, 129, 0.1)"),
            ],
        ),
    ))

    fig.update_layout(
        **DARK_LAYOUT,
        height=250,
        margin=dict(l=30, r=30, t=50, b=20),
    )

    return fig
