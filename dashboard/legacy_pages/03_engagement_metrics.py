"""
📊 Engagement Metrics Page
Visualizes per-hashtag engagement analysis: likes, comments,
engagement rates, and peak time patterns.
"""

import os
import sys
import time
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from storage.mongo_client import MongoDBClient
from dashboard.components.charts import (
    create_trending_bar_chart,
    create_scatter_chart,
    create_engagement_heatmap,
    create_gauge_chart,
    COLORS, GRADIENT_PALETTE,
)
from dashboard.components.filters import render_sidebar_filters

st.set_page_config(
    page_title="Instagram Analytics | Engagement Metrics",
    page_icon="📊",
    layout="wide",
)

css_path = os.path.join(os.path.dirname(__file__), "..", "styles", "custom.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #0B0B14 0%, #0F0F1A 50%, #0B0B14 100%);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F0F1A, #12121F);
        border-right: 1px solid rgba(139, 92, 246, 0.1);
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_mongo():
    client = MongoDBClient()
    client.connect()
    return client


def main():
    filters = render_sidebar_filters()

    st.markdown(
        """
        <div class="fade-in" style="padding-bottom: 20px;">
            <h1 style="font-size: 2rem; font-weight: 800;
                       background: linear-gradient(135deg, #8B5CF6, #06B6D4);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                📊 Engagement Metrics
            </h1>
            <p style="color: rgba(255,255,255,0.4); margin-top: -8px;">
                Likes, comments, engagement rates, and peak activity times
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        mongo = get_mongo()
    except Exception as e:
        st.error(f"❌ MongoDB connection failed: {e}")
        return

    # ---- Fetch Engagement Data ----
    engagement_data = mongo.get_engagement_leaderboard(limit=filters["top_n"])

    if engagement_data:
        df = pd.DataFrame(engagement_data)

        if filters.get("hashtags"):
            df = df[df["hashtag"].isin(filters["hashtags"])]

        if df.empty:
            st.info("No data matching your hashtag filter.")
            return

        # ---- Top Metrics ----
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)

        avg_engagement = df["engagement_rate"].mean() if "engagement_rate" in df.columns else 0
        max_likes = df["max_likes"].max() if "max_likes" in df.columns else 0
        total_posts = df["total_posts"].sum() if "total_posts" in df.columns else 0
        avg_likes = df["avg_likes"].mean() if "avg_likes" in df.columns else 0

        with mcol1:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Avg Engagement Rate</div>
                    <div class="metric-value">{avg_engagement:.1f}</div>
                    <div class="metric-delta positive">Across all hashtags</div>
                </div>""",
                unsafe_allow_html=True,
            )

        with mcol2:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Peak Likes</div>
                    <div class="metric-value">{max_likes:,}</div>
                    <div class="metric-delta positive">Single post max</div>
                </div>""",
                unsafe_allow_html=True,
            )

        with mcol3:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Total Posts</div>
                    <div class="metric-value">{total_posts:,}</div>
                    <div class="metric-delta positive">All hashtags</div>
                </div>""",
                unsafe_allow_html=True,
            )

        with mcol4:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Avg Likes/Post</div>
                    <div class="metric-value">{avg_likes:,.0f}</div>
                    <div class="metric-delta positive">Per hashtag avg</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ---- Engagement Rate Leaderboard ----
        st.markdown('<div class="section-header">🏆 Engagement Rate Leaderboard</div>', unsafe_allow_html=True)

        if "engagement_rate" in df.columns:
            leaderboard = df.sort_values("engagement_rate", ascending=False).head(filters["top_n"])
            fig = create_trending_bar_chart(
                leaderboard,
                x="hashtag",
                y="engagement_rate",
                title="Hashtags by Engagement Rate",
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ---- Likes vs Comments Scatter ----
        st.markdown('<div class="section-header">💬 Likes vs Comments Analysis</div>', unsafe_allow_html=True)

        if "avg_likes" in df.columns and "avg_comments" in df.columns:
            size_col = "total_posts" if "total_posts" in df.columns else None
            fig_scatter = create_scatter_chart(
                df,
                x="avg_likes",
                y="avg_comments",
                size=size_col,
                color="hashtag" if len(df) <= 20 else None,
                title="Average Likes vs Comments per Hashtag",
            )
            st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})

        # ---- Peak Hour Analysis ----
        st.markdown('<div class="section-header">⏰ Peak Engagement Hours</div>', unsafe_allow_html=True)

        if "peak_hour" in df.columns:
            # Create hour distribution
            hour_counts = df["peak_hour"].value_counts().sort_index()
            all_hours = pd.Series(0, index=range(24))
            all_hours.update(hour_counts)

            fig_hours = go.Figure()
            fig_hours.add_trace(go.Bar(
                x=[f"{h:02d}:00" for h in range(24)],
                y=all_hours.values,
                marker=dict(
                    color=[
                        f"rgba(139, 92, 246, {0.3 + 0.7 * (v / max(all_hours.values) if max(all_hours.values) > 0 else 0)})"
                        for v in all_hours.values
                    ],
                    line=dict(width=0),
                    cornerradius=4,
                ),
                hovertemplate="<b>%{x}</b><br>Peak hashtags: %{y}<extra></extra>",
            ))

            fig_hours.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif", color="#F8FAFC"),
                title=dict(text="Distribution of Peak Engagement Hours", font=dict(size=16)),
                xaxis=dict(title="Hour of Day", gridcolor="rgba(139,92,246,0.08)"),
                yaxis=dict(title="Number of Hashtags", gridcolor="rgba(139,92,246,0.08)"),
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_hours, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Peak hour data not yet available.")

        # ---- Detailed Data Table ----
        st.markdown('<div class="section-header">📋 Detailed Engagement Data</div>', unsafe_allow_html=True)

        display_cols = [c for c in ["hashtag", "total_posts", "avg_likes", "avg_comments",
                                     "engagement_rate", "max_likes", "max_comments", "peak_hour"]
                        if c in df.columns]

        st.dataframe(
            df[display_cols].sort_values("engagement_rate", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "hashtag": st.column_config.TextColumn("Hashtag", width="medium"),
                "total_posts": st.column_config.NumberColumn("Posts", format="%d"),
                "avg_likes": st.column_config.NumberColumn("Avg ❤️", format="%.0f"),
                "avg_comments": st.column_config.NumberColumn("Avg 💬", format="%.0f"),
                "engagement_rate": st.column_config.ProgressColumn(
                    "Engagement Rate", min_value=0,
                    max_value=float(df["engagement_rate"].max()) if "engagement_rate" in df.columns else 100,
                    format="%.1f",
                ),
                "max_likes": st.column_config.NumberColumn("Max ❤️", format="%d"),
                "max_comments": st.column_config.NumberColumn("Max 💬", format="%d"),
                "peak_hour": st.column_config.NumberColumn("Peak Hour", format="%d:00"),
            },
        )

    else:
        st.info(
            "📭 No engagement data yet.\n\n"
            "**To get started:**\n"
            "1. Run `docker-compose up` for Kafka + Spark\n"
            "2. Run the Kafka producer to ingest posts\n"
            "3. Submit the Scala Spark EngagementAnalyzer job"
        )

    st.markdown(
        '<div class="footer">Engagement Metrics · Powered by Spark Structured Streaming</div>',
        unsafe_allow_html=True,
    )

    if filters["auto_refresh"]:
        time.sleep(filters["refresh_interval"])
        st.rerun()


main()
