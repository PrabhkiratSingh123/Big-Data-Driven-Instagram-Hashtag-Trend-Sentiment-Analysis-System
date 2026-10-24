"""
SocialTrendML — Engagement Metrics Page
Visualizes hashtag engagement rates, likes vs comments distributions, and peak hours.
"""

import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

st.set_page_config(page_title="SocialTrendML | Engagement Metrics", page_icon="⚡", layout="wide")

from dashboard.streamlit_app import COLORS, render_sidebar, get_mongo, ensure_demo_data

render_sidebar()

st.markdown("""
<div style="text-align: center; padding: 12px 0 20px 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
               background: linear-gradient(135deg, #8B5CF6, #06B6D4, #10B981);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        ⚡ Engagement Metrics
    </h1>
    <p style="color: rgba(255,255,255,0.4); font-size: 0.9rem;">
        Interaction rates, likes vs comments distributions, and activity heatmaps
    </p>
</div>
""", unsafe_allow_html=True)

db = get_mongo()
if db is None:
    st.error("❌ Cannot connect to MongoDB. Ensure it's running on localhost:27017")
    st.stop()

ensure_demo_data(db)

# Summary Cards
summary = db.get_engagement_summary()
leaderboard = db.get_engagement_leaderboard(limit=20)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; text-transform: uppercase;">Total Likes</div>
        <div style="font-size: 2rem; font-weight: 800; color: #F8FAFC; margin: 4px 0;">{summary.get('total_likes', 0):,}</div>
        <div style="color: #10B981; font-size: 0.8rem;">❤️ Reactions</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; text-transform: uppercase;">Total Comments</div>
        <div style="font-size: 2rem; font-weight: 800; color: #F8FAFC; margin: 4px 0;">{summary.get('total_comments', 0):,}</div>
        <div style="color: #06B6D4; font-size: 0.8rem;">💬 Conversations</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; text-transform: uppercase;">Avg Engagement Rate</div>
        <div style="font-size: 2rem; font-weight: 800; color: #F8FAFC; margin: 4px 0;">{summary.get('avg_engagement_rate', 0):.1f}</div>
        <div style="color: #8B5CF6; font-size: 0.8rem;">⚡ Interactions / Post</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    top_tag = leaderboard[0].get("hashtag", "None") if leaderboard else "N/A"
    top_rate = leaderboard[0].get("engagement_rate", 0) if leaderboard else 0
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; text-transform: uppercase;">Most Engaged Tag</div>
        <div style="font-size: 1.6rem; font-weight: 800; color: #10B981; margin: 4px 0;">#{top_tag}</div>
        <div style="color: rgba(255,255,255,0.5); font-size: 0.8rem;">Rate: {top_rate:.1f}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Charts Row
chart_col1, chart_col2 = st.columns([3, 2])

with chart_col1:
    st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin-bottom: 12px;">📊 Engagement Leaderboard</div>', unsafe_allow_html=True)
    if leaderboard:
        df_lead = pd.DataFrame(leaderboard)
        fig = px.bar(
            df_lead.head(10),
            x="hashtag",
            y="engagement_rate",
            color="engagement_rate",
            color_continuous_scale=["#6D28D9", "#8B5CF6", "#06B6D4", "#10B981"],
            labels={"engagement_rate": "Engagement Rate", "hashtag": "Hashtag"},
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
            xaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
            yaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
            coloraxis_showscale=False,
            margin=dict(t=10, b=40),
            height=340,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No engagement data available yet.")

with chart_col2:
    st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin-bottom: 12px;">🕒 Hourly Post Activity</div>', unsafe_allow_html=True)
    hourly = db.get_hourly_activity(days=7)
    if hourly:
        hours = list(range(24))
        counts = {h["_id"]: h["count"] for h in hourly if h["_id"] is not None}
        hour_counts = [counts.get(h, 0) for h in hours]

        fig = go.Figure(data=go.Scatter(
            x=hours,
            y=hour_counts,
            mode="lines+markers",
            line=dict(color="#06B6D4", width=3, shape="spline"),
            marker=dict(size=6, color="#10B981"),
            fill="tozeroy",
            fillcolor="rgba(6,182,212,0.15)",
        ))
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
            xaxis=dict(title="Hour of Day (UTC)", gridcolor="rgba(139,92,246,0.08)", dtick=4),
            yaxis=dict(title="Posts", gridcolor="rgba(139,92,246,0.08)"),
            margin=dict(t=10, b=40, l=40, r=10),
            height=340,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No hourly data available.")

# Scatter Plot: Likes vs Comments
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 20px 0 12px 0;">🎯 Likes vs Comments Correlation</div>', unsafe_allow_html=True)

scatter_data = db.get_likes_vs_comments(limit=120)
if scatter_data:
    df_scatter = pd.DataFrame(scatter_data)
    fig_scatter = px.scatter(
        df_scatter,
        x="likes_count",
        y="comments_count",
        color="source_hashtag",
        hover_data=["media_type"],
        labels={"likes_count": "Likes", "comments_count": "Comments", "source_hashtag": "Hashtag"},
        color_discrete_sequence=["#8B5CF6", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#3B82F6"],
    )
    fig_scatter.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
        xaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
        yaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
        margin=dict(t=10, b=40),
        height=380,
    )
    st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("No post interaction data available.")

# Detailed Leaderboard Table
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 20px 0 12px 0;">📋 Metric Details by Hashtag</div>', unsafe_allow_html=True)
if leaderboard:
    df_table = pd.DataFrame(leaderboard)[["hashtag", "total_posts", "total_likes", "total_comments", "avg_likes", "avg_comments", "engagement_rate"]]
    st.dataframe(
        df_table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "hashtag": st.column_config.TextColumn("#Hashtag", width="medium"),
            "total_posts": st.column_config.NumberColumn("Posts", format="%d"),
            "total_likes": st.column_config.NumberColumn("Total Likes", format="%d"),
            "total_comments": st.column_config.NumberColumn("Total Comments", format="%d"),
            "avg_likes": st.column_config.NumberColumn("Avg Likes", format="%.1f"),
            "avg_comments": st.column_config.NumberColumn("Avg Comments", format="%.1f"),
            "engagement_rate": st.column_config.NumberColumn("Engagement Rate", format="%.2f"),
        },
    )
