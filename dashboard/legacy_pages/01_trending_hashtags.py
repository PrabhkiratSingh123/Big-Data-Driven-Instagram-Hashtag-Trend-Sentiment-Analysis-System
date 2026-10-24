"""
📈 Trending Hashtags Page
Visualizes real-time hashtag trends with bar charts, velocity line charts,
and co-occurrence network analysis.
"""

import os
import sys
import time
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from storage.mongo_client import MongoDBClient
from dashboard.components.charts import (
    create_trending_bar_chart,
    create_trend_line_chart,
    create_scatter_chart,
    COLORS, GRADIENT_PALETTE,
)
from dashboard.components.filters import render_sidebar_filters

# Page config
st.set_page_config(
    page_title="Instagram Analytics | Trending Hashtags",
    page_icon="📈",
    layout="wide",
)

# Load CSS
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

    # Header
    st.markdown(
        """
        <div class="fade-in" style="padding-bottom: 20px;">
            <h1 style="font-size: 2rem; font-weight: 800;
                       background: linear-gradient(135deg, #8B5CF6, #06B6D4);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                📈 Trending Hashtags
            </h1>
            <p style="color: rgba(255,255,255,0.4); margin-top: -8px;">
                Real-time hashtag frequency, velocity, and co-occurrence analysis
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

    # ---- Window Duration Selector ----
    col_w1, col_w2, col_w3 = st.columns([1, 1, 3])
    with col_w1:
        window_duration = st.selectbox(
            "Window Duration",
            options=[5, 15, 60],
            format_func=lambda x: f"{x} minutes",
            index=0,
        )

    # ---- Top Trending Bar Chart ----
    st.markdown('<div class="section-header">🔥 Top Trending Hashtags</div>', unsafe_allow_html=True)

    top_hashtags = mongo.get_top_hashtags(
        window_duration_min=window_duration,
        limit=filters["top_n"],
    )

    if top_hashtags:
        df = pd.DataFrame(top_hashtags)
        df = df.rename(columns={"_id": "hashtag", "latest_count": "count"})

        if filters.get("hashtags"):
            df = df[df["hashtag"].isin(filters["hashtags"])]

        if not df.empty:
            # Metrics row
            mcol1, mcol2, mcol3 = st.columns(3)
            with mcol1:
                st.markdown(
                    f"""<div class="metric-card">
                        <div class="metric-label">Top Hashtag</div>
                        <div class="metric-value" style="font-size:1.6rem;">#{df.iloc[0]['hashtag']}</div>
                        <div class="metric-delta positive">{df.iloc[0]['count']:,} posts</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with mcol2:
                total = df["count"].sum()
                st.markdown(
                    f"""<div class="metric-card">
                        <div class="metric-label">Total Activity</div>
                        <div class="metric-value" style="font-size:1.6rem;">{total:,}</div>
                        <div class="metric-delta positive">In {window_duration}min window</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with mcol3:
                unique = len(df)
                st.markdown(
                    f"""<div class="metric-card">
                        <div class="metric-label">Unique Hashtags</div>
                        <div class="metric-value" style="font-size:1.6rem;">{unique}</div>
                        <div class="metric-delta positive">Active now</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # Bar chart
            fig = create_trending_bar_chart(
                df.head(filters["top_n"]),
                x="hashtag",
                y="count",
                title=f"Top {min(len(df), filters['top_n'])} Hashtags ({window_duration}min window)",
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # ---- Velocity Analysis ----
            st.markdown('<div class="section-header">⚡ Hashtag Velocity</div>', unsafe_allow_html=True)

            if "latest_velocity" in df.columns:
                velocity_df = df.sort_values("latest_velocity", ascending=False).head(10)
                fig_vel = create_trending_bar_chart(
                    velocity_df,
                    x="hashtag",
                    y="latest_velocity",
                    title="Fastest Growing Hashtags (posts/min)",
                )
                st.plotly_chart(fig_vel, use_container_width=True, config={"displayModeBar": False})

            # ---- Trend Over Time ----
            st.markdown('<div class="section-header">📊 Trend Over Time</div>', unsafe_allow_html=True)

            # Get time series data for top 5 hashtags
            top5 = df.head(5)["hashtag"].tolist()
            trend_collection = mongo.get_collection("hashtag_trends")

            match_filter = {
                "hashtag": {"$in": top5},
                "window_duration_min": window_duration,
            }
            if filters.get("time_cutoff"):
                match_filter["window_start"] = {"$gte": filters["time_cutoff"]}

            trend_data = list(
                trend_collection.find(match_filter, {"_id": 0})
                .sort("window_start", -1)
                .limit(500)
            )

            if trend_data:
                trend_df = pd.DataFrame(trend_data)
                fig_trend = create_trend_line_chart(
                    trend_df,
                    x="window_start",
                    y="count",
                    color="hashtag",
                    title="Hashtag Trends Over Time",
                )
                st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

            # ---- Hashtag Tags Cloud ----
            st.markdown('<div class="section-header">#️⃣ Active Hashtags</div>', unsafe_allow_html=True)

            tags_html = " ".join(
                f'<span class="hashtag-tag">#{row["hashtag"]}</span>'
                for _, row in df.iterrows()
            )
            st.markdown(f'<div class="fade-in">{tags_html}</div>', unsafe_allow_html=True)

        else:
            st.info("No data matching your hashtag filter.")
    else:
        st.info(
            "📭 No hashtag trend data yet.\n\n"
            "**To get started:**\n"
            "1. Run `docker-compose up` for Kafka + Spark\n"
            "2. Run the Kafka producer: `python ingestion/kafka_producer.py`\n"
            "3. Submit the Scala Spark job for hashtag processing"
        )

    # Footer
    st.markdown(
        '<div class="footer">Trending Hashtags · Updated in real-time</div>',
        unsafe_allow_html=True,
    )

    if filters["auto_refresh"]:
        time.sleep(filters["refresh_interval"])
        st.rerun()


main()
