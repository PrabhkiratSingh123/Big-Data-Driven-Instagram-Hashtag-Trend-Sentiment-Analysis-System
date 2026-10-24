"""
SocialTrendML — Streamlit Dashboard
Main application entry point with overview page.
"""

import os
import sys
import time

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.database.mongodb import MongoDBManager, get_db
from backend.app.core.config import get_settings

# =====================================================================
# Page Configuration
# =====================================================================

st.set_page_config(
    page_title="SocialTrendML | Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================================
# Theme & Styling
# =====================================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        background: linear-gradient(180deg, #0a0a1a 0%, #0d0d24 50%, #0a0a1a 100%);
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d24 0%, #10102a 100%);
        border-right: 1px solid rgba(139, 92, 246, 0.15);
    }

    [data-testid="stHeader"] {
        background: rgba(10, 10, 26, 0.85);
        backdrop-filter: blur(16px);
    }

    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.08), rgba(6, 182, 212, 0.06));
        border: 1px solid rgba(139, 92, 246, 0.15);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        transition: all 0.3s ease;
        backdrop-filter: blur(10px);
    }
    .metric-card:hover {
        border-color: rgba(139, 92, 246, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(139, 92, 246, 0.15);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #8B5CF6, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 4px 0;
    }
    .metric-label {
        color: rgba(255, 255, 255, 0.5);
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-delta {
        font-size: 0.8rem;
        margin-top: 4px;
    }
    .metric-delta.positive { color: #10B981; }
    .metric-delta.negative { color: #EF4444; }
    .metric-delta.neutral { color: rgba(255,255,255,0.4); }

    /* Section Headers */
    .section-header {
        color: #F8FAFC;
        font-size: 1.2rem;
        font-weight: 700;
        margin: 16px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(139, 92, 246, 0.2);
    }

    /* Status Badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .status-live {
        background: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-demo {
        background: rgba(245, 158, 11, 0.15);
        color: #F59E0B;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .live-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #10B981;
        animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); }
        50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
    }

    /* Footer */
    .footer {
        text-align: center;
        padding: 32px 0 16px 0;
        color: rgba(255, 255, 255, 0.25);
        font-size: 0.8rem;
        border-top: 1px solid rgba(139, 92, 246, 0.1);
        margin-top: 40px;
    }

    /* Data tables */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Fade-in animation */
    .fade-in { animation: fadeIn 0.6s ease-out; }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Headings */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #F8FAFC !important;
    }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# Color Palette
# =====================================================================

COLORS = {
    "primary": "#8B5CF6",
    "secondary": "#06B6D4",
    "accent": "#10B981",
    "positive": "#10B981",
    "negative": "#EF4444",
    "neutral": "#6366F1",
    "warning": "#F59E0B",
    "bg_dark": "#0a0a1a",
    "bg_card": "rgba(139, 92, 246, 0.08)",
    "text_primary": "#F8FAFC",
    "text_secondary": "rgba(255, 255, 255, 0.5)",
    "gradient": ["#8B5CF6", "#7C3AED", "#6D28D9", "#06B6D4", "#0891B2", "#10B981"],
}


# =====================================================================
# Shared Helpers
# =====================================================================

@st.cache_resource
def get_mongo():
    """Cached MongoDB connection for the dashboard."""
    try:
        db = MongoDBManager()
        db.connect()
        db.setup_collections()
        return db
    except Exception as e:
        return None


def ensure_demo_data(db):
    """Seed demo data if the database is empty."""
    if db and db.get_post_count() == 0:
        try:
            from backend.app.services.demo_data import seed_demo_data
            with st.spinner("🌱 Seeding demo data for first-time exploration..."):
                seed_demo_data(db, count=200)
            st.success("✅ Demo data loaded! Explore the dashboard.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.warning(f"Could not seed demo data: {e}")


def render_sidebar():
    """Render sidebar with filters and info."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 8px 0;">
            <div style="font-size: 1.5rem; font-weight: 800;
                        background: linear-gradient(135deg, #8B5CF6, #06B6D4);
                        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                SocialTrendML
            </div>
            <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem; margin-top: 2px;">
                Hashtag Trend & Sentiment Analysis
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        settings = get_settings()
        if settings.is_api_configured:
            st.markdown('<span class="status-badge status-live"><span class="live-dot"></span> Live API</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-badge status-demo">⚡ Demo Mode</span>', unsafe_allow_html=True)
            st.caption("Configure META_ACCESS_TOKEN in .env for live data")

        st.markdown("---")

        # Collection trigger
        st.markdown("**🔄 Data Collection**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶ Collect", use_container_width=True, type="primary"):
                _trigger_collection()
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        st.markdown("---")
        st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")


def _trigger_collection():
    """Trigger a data collection run from the dashboard."""
    try:
        from backend.app.services.analytics import AnalyticsService
        with st.spinner("Collecting data..."):
            service = AnalyticsService()
            result = service.run_collection()
        if result.get("status") == "completed":
            st.success(f"✅ Collected {result.get('posts_collected', 0)} posts")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Collection failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        st.error(f"Collection error: {e}")


# =====================================================================
# Main Overview Page
# =====================================================================

def main():
    render_sidebar()

    # Header
    st.markdown("""
    <div style="text-align: center; padding: 16px 0 24px 0;" class="fade-in">
        <h1 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 4px;
                   background: linear-gradient(135deg, #8B5CF6, #06B6D4, #10B981);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            📊 Analytics Overview
        </h1>
        <p style="color: rgba(255,255,255,0.4); font-size: 0.95rem; margin-top: 0;">
            Real-time hashtag trends · Spark ML sentiment analysis · Trend insights
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Connect to MongoDB
    db = get_mongo()
    if db is None:
        st.error("❌ Cannot connect to MongoDB. Ensure it's running on localhost:27017")
        st.info("💡 Start MongoDB via MongoDB Compass or run `mongod` in terminal.")
        return

    ensure_demo_data(db)

    # Key Metrics
    total_posts = db.get_post_count()
    hashtags = db.get_unique_hashtags()
    sentiment_dist = db.get_sentiment_distribution()
    last_run = db.get_latest_collection_run()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card fade-in">
            <div class="metric-label">Total Posts</div>
            <div class="metric-value">{total_posts:,}</div>
            <div class="metric-delta positive">📥 Collected</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card fade-in">
            <div class="metric-label">Tracked Hashtags</div>
            <div class="metric-value">{len(hashtags)}</div>
            <div class="metric-delta positive">📈 Active</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        total_s = sum(sentiment_dist.values()) or 1
        pos_pct = sentiment_dist.get("positive", 0) / total_s * 100
        st.markdown(f"""
        <div class="metric-card fade-in">
            <div class="metric-label">Positive Sentiment</div>
            <div class="metric-value">{pos_pct:.0f}%</div>
            <div class="metric-delta positive">😊 Of all posts</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        analyzed = sum(sentiment_dist.values())
        st.markdown(f"""
        <div class="metric-card fade-in">
            <div class="metric-label">Analyzed</div>
            <div class="metric-value">{analyzed:,}</div>
            <div class="metric-delta neutral">🧠 Spark ML</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts Row
    chart_col1, chart_col2 = st.columns([3, 2])

    with chart_col1:
        st.markdown('<div class="section-header">🔥 Trending Hashtags</div>', unsafe_allow_html=True)
        trends = db.get_trending_hashtags(limit=10)
        if trends:
            df = pd.DataFrame(trends)
            df["hashtag"] = df["_id"]
            fig = px.bar(
                df, x="hashtag", y="trend_score",
                color="trend_score",
                color_continuous_scale=["#6D28D9", "#8B5CF6", "#06B6D4", "#10B981"],
                labels={"trend_score": "Trend Score", "hashtag": "Hashtag"},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
                xaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
                yaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
                coloraxis_showscale=False,
                margin=dict(t=10, b=40),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("📭 No trend data yet. Run a collection to start.")

    with chart_col2:
        st.markdown('<div class="section-header">💭 Sentiment Distribution</div>', unsafe_allow_html=True)
        if sentiment_dist:
            labels = list(sentiment_dist.keys())
            values = list(sentiment_dist.values())
            colors_map = {"positive": COLORS["positive"], "negative": COLORS["negative"], "neutral": COLORS["neutral"]}
            colors = [colors_map.get(l, COLORS["primary"]) for l in labels]

            fig = go.Figure(data=[go.Pie(
                labels=[l.capitalize() for l in labels],
                values=values,
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0.3)", width=2)),
                textinfo="label+percent",
                textfont=dict(color="white", size=12),
            )])
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("📭 No sentiment data yet.")

    # Recent Posts
    st.markdown('<div class="section-header">📋 Recent Posts</div>', unsafe_allow_html=True)
    posts = db.get_posts(limit=10)
    if posts:
        df = pd.DataFrame(posts)
        display_cols = ["post_id", "source_hashtag", "caption", "media_type", "timestamp", "is_demo"]
        available = [c for c in display_cols if c in df.columns]
        df_display = df[available].copy()
        if "caption" in df_display.columns:
            df_display["caption"] = df_display["caption"].str[:120] + "..."
        if "timestamp" in df_display.columns:
            df_display["timestamp"] = pd.to_datetime(df_display["timestamp"])

        st.dataframe(
            df_display, use_container_width=True, hide_index=True,
            column_config={
                "post_id": st.column_config.TextColumn("ID", width="small"),
                "source_hashtag": st.column_config.TextColumn("#Hashtag", width="small"),
                "caption": st.column_config.TextColumn("Caption", width="large"),
                "media_type": st.column_config.TextColumn("Type", width="small"),
                "timestamp": st.column_config.DatetimeColumn("Time", width="medium"),
                "is_demo": st.column_config.CheckboxColumn("Demo", width="small"),
            },
        )
    else:
        st.info("📭 No posts collected yet.")

    # Last Collection
    if last_run:
        st.markdown('<div class="section-header">🕐 Last Collection</div>', unsafe_allow_html=True)
        lc1, lc2, lc3, lc4 = st.columns(4)
        lc1.metric("Status", last_run.get("status", "unknown").capitalize())
        lc2.metric("Posts", last_run.get("posts_collected", 0))
        lc3.metric("Hashtags", ", ".join(last_run.get("hashtags", [])[:3]))
        started = last_run.get("started_at")
        lc4.metric("When", started.strftime("%H:%M %b %d") if isinstance(started, datetime) else str(started)[:16])

    # Footer
    st.markdown("""
    <div class="footer">
        SocialTrendML — Hashtag Trend & Sentiment Analysis<br>
        Built with Python · FastAPI · PySpark ML · Kafka · MongoDB · Streamlit
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
