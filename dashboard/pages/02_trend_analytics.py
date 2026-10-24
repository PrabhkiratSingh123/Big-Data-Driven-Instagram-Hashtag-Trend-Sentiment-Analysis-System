"""
SocialTrendML — Trend Analytics Page
Posts over time, hashtag activity comparison, trending topics, hourly/daily charts.
"""

import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.database.mongodb import MongoDBManager

st.set_page_config(page_title="SocialTrendML | Trend Analytics", page_icon="📈", layout="wide")

from dashboard.streamlit_app import COLORS, render_sidebar, get_mongo, ensure_demo_data

render_sidebar()

st.markdown("""
<div style="text-align: center; padding: 12px 0 20px 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
               background: linear-gradient(135deg, #8B5CF6, #06B6D4);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        📈 Trend Analytics
    </h1>
    <p style="color: rgba(255,255,255,0.4); font-size: 0.9rem;">
        Post activity, hashtag comparisons, and trending topics
    </p>
</div>
""", unsafe_allow_html=True)

db = get_mongo()
if db is None:
    st.error("❌ Cannot connect to MongoDB")
    st.stop()

ensure_demo_data(db)

# Controls
ctrl_col1, ctrl_col2 = st.columns([2, 1])
with ctrl_col1:
    available = db.get_unique_hashtags()
    selected = st.multiselect("Select hashtags", available, default=available[:min(4, len(available))])
with ctrl_col2:
    days = st.slider("Time range (days)", 1, 30, 7)

if not selected:
    st.warning("Select at least one hashtag")
    st.stop()

# ---- Trending Topics Leaderboard ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 20px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">🏆 Trending Topics</div>', unsafe_allow_html=True)

trends = db.get_trending_hashtags(limit=20)
if trends:
    df_trends = pd.DataFrame(trends)
    df_trends["hashtag"] = df_trends["_id"]
    df_trends = df_trends[df_trends["hashtag"].isin(selected)] if selected else df_trends

    if not df_trends.empty:
        cols = st.columns(min(len(df_trends), 5))
        for i, (_, row) in enumerate(df_trends.head(5).iterrows()):
            with cols[i]:
                score = row.get("trend_score", 0)
                count = row.get("post_count", 0)
                sentiment = row.get("avg_sentiment", 0)
                emoji = "🟢" if sentiment > 0 else "🔴" if sentiment < 0 else "⚪"

                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(139,92,246,0.1), rgba(6,182,212,0.06));
                            border: 1px solid rgba(139,92,246,0.2); border-radius: 14px; padding: 16px; text-align: center;">
                    <div style="font-size: 1.4rem; font-weight: 800; color: #F8FAFC;">#{row['hashtag']}</div>
                    <div style="font-size: 0.75rem; color: rgba(255,255,255,0.4); margin: 4px 0;">Trend Score</div>
                    <div style="font-size: 1.6rem; font-weight: 800; background: linear-gradient(135deg, #8B5CF6, #06B6D4);
                                -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{score:.1f}</div>
                    <div style="font-size: 0.8rem; color: rgba(255,255,255,0.5); margin-top: 4px;">
                        {count} posts · {emoji} {sentiment:+.2f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---- Activity Over Time ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">📅 Posts Over Time</div>', unsafe_allow_html=True)

all_daily = []
for hashtag in selected:
    activity = db.get_hashtag_activity(hashtag, days=days)
    for d in activity:
        all_daily.append({"date": d["_id"], "count": d["count"], "hashtag": hashtag})

if all_daily:
    df_daily = pd.DataFrame(all_daily)
    df_daily["date"] = pd.to_datetime(df_daily["date"])

    fig = px.line(
        df_daily, x="date", y="count", color="hashtag",
        markers=True,
        color_discrete_sequence=COLORS["gradient"],
        labels={"count": "Posts", "date": "Date", "hashtag": "Hashtag"},
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
        xaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
        yaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=10, b=40),
        height=380,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("📭 No daily activity data available")

# ---- Hourly Distribution ----
hour_col, compare_col = st.columns(2)

with hour_col:
    st.markdown('<div style="color: #F8FAFC; font-size: 1.05rem; font-weight: 700; margin: 12px 0 8px 0;">⏰ Hourly Activity</div>', unsafe_allow_html=True)

    hourly = db.get_hourly_activity(days=days)
    if hourly:
        df_h = pd.DataFrame([{"hour": h["_id"], "count": h["count"]} for h in hourly])
        df_h = df_h.sort_values("hour")
        df_h["hour_label"] = df_h["hour"].apply(lambda x: f"{x:02d}:00")

        fig = px.bar(
            df_h, x="hour_label", y="count",
            color="count", color_continuous_scale=["#6D28D9", "#8B5CF6", "#06B6D4"],
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.7)", size=10),
            coloraxis_showscale=False, margin=dict(t=5, b=5), height=300,
            xaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
            yaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No hourly data")

with compare_col:
    st.markdown('<div style="color: #F8FAFC; font-size: 1.05rem; font-weight: 700; margin: 12px 0 8px 0;">📊 Hashtag Volume Comparison</div>', unsafe_allow_html=True)

    compare_data = []
    for h in selected:
        count = db.get_post_count(hashtag=h)
        compare_data.append({"hashtag": h, "posts": count})

    if compare_data:
        df_c = pd.DataFrame(compare_data).sort_values("posts", ascending=True)
        fig = px.bar(
            df_c, y="hashtag", x="posts", orientation="h",
            color="posts", color_continuous_scale=["#6D28D9", "#06B6D4", "#10B981"],
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.7)", size=10),
            coloraxis_showscale=False, margin=dict(t=5, b=5), height=300,
            xaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
            yaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# Trend Score Explanation
with st.expander("ℹ️ How is the Trend Score calculated?"):
    st.markdown("""
    **Trend Score Formula:**

    ```
    trend_score = (1 + growth_rate) × volume_factor × sentiment_boost × (1 + velocity × 0.1)
    ```

    - **Growth Rate**: `(current_posts - previous_posts) / max(previous_posts, 1)` — measures acceleration
    - **Volume Factor**: `log₂(current_posts + 1)` — rewards higher volume with diminishing returns
    - **Sentiment Boost**: `1.0 + (avg_sentiment × 0.2)` — slight boost for positive sentiment
    - **Velocity**: `posts_per_hour` — measures posting frequency

    Higher scores indicate hashtags gaining attention rapidly with positive reception.
    """)
