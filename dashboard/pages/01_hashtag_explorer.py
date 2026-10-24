"""
SocialTrendML — Hashtag Explorer Page
Search, select, and compare hashtags with keyword frequency and related tags.
"""

import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.database.mongodb import MongoDBManager
from backend.app.ml.sentiment import extract_keywords, extract_hashtags_from_caption

st.set_page_config(page_title="SocialTrendML | Hashtag Explorer", page_icon="🔍", layout="wide")

# Import shared styles
from dashboard.streamlit_app import COLORS, render_sidebar, get_mongo, ensure_demo_data

render_sidebar()

st.markdown("""
<div style="text-align: center; padding: 12px 0 20px 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
               background: linear-gradient(135deg, #8B5CF6, #06B6D4);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🔍 Hashtag Explorer
    </h1>
    <p style="color: rgba(255,255,255,0.4); font-size: 0.9rem;">
        Search, explore, and compare hashtags
    </p>
</div>
""", unsafe_allow_html=True)

db = get_mongo()
if db is None:
    st.error("❌ Cannot connect to MongoDB")
    st.stop()

ensure_demo_data(db)

# Hashtag Selection
available = db.get_unique_hashtags()
if not available:
    st.info("📭 No hashtags tracked yet. Run a collection first.")
    st.stop()

selected = st.multiselect(
    "Select hashtags to explore",
    options=available,
    default=available[:min(3, len(available))],
    max_selections=5,
)

if not selected:
    st.warning("Select at least one hashtag above.")
    st.stop()

# Comparison metrics
st.markdown('<div class="section-header" style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">📊 Hashtag Comparison</div>', unsafe_allow_html=True)

cols = st.columns(len(selected))
for i, hashtag in enumerate(selected):
    with cols[i]:
        count = db.get_post_count(hashtag=hashtag)
        sentiment = db.get_sentiment_distribution(hashtag=hashtag)
        total_s = sum(sentiment.values()) or 1
        pos_pct = sentiment.get("positive", 0) / total_s * 100

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.08), rgba(6, 182, 212, 0.06));
                    border: 1px solid rgba(139, 92, 246, 0.15); border-radius: 14px; padding: 18px; text-align: center;">
            <div style="color: rgba(255,255,255,0.5); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;">#{hashtag}</div>
            <div style="font-size: 1.8rem; font-weight: 800; background: linear-gradient(135deg, #8B5CF6, #06B6D4);
                        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{count}</div>
            <div style="color: #10B981; font-size: 0.8rem;">😊 {pos_pct:.0f}% positive</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Posts per hashtag
tab_names = [f"#{h}" for h in selected]
tabs = st.tabs(tab_names)

for i, hashtag in enumerate(selected):
    with tabs[i]:
        posts = db.get_posts(hashtag=hashtag, limit=50)
        if not posts:
            st.info(f"No posts for #{hashtag}")
            continue

        # Keyword frequency
        kw_col, posts_col = st.columns([1, 2])

        with kw_col:
            st.markdown("**🔑 Top Keywords**")
            all_keywords = []
            all_related = []
            for p in posts:
                all_keywords.extend(extract_keywords(p.get("caption", "")))
                all_related.extend(extract_hashtags_from_caption(p.get("caption", "")))

            from collections import Counter
            kw_counts = Counter(all_keywords).most_common(15)
            if kw_counts:
                kw_df = pd.DataFrame(kw_counts, columns=["keyword", "count"])
                fig = px.bar(
                    kw_df, y="keyword", x="count", orientation="h",
                    color="count", color_continuous_scale=["#6D28D9", "#06B6D4"],
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="rgba(255,255,255,0.7)", size=11),
                    yaxis=dict(autorange="reversed"), showlegend=False,
                    coloraxis_showscale=False, margin=dict(t=5, b=5, l=5, r=5),
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            st.markdown("**#️⃣ Related Hashtags**")
            related_counts = Counter(h for h in all_related if h != hashtag).most_common(10)
            if related_counts:
                for tag, cnt in related_counts:
                    st.markdown(f"<span style='color: #8B5CF6; font-weight: 600;'>#{tag}</span> <span style='color: rgba(255,255,255,0.3);'>({cnt})</span>", unsafe_allow_html=True)

        with posts_col:
            st.markdown("**📝 Recent Posts**")
            df = pd.DataFrame(posts)
            for idx, row in df.head(15).iterrows():
                caption = (row.get("caption", "") or "")[:200]
                media = row.get("media_type", "IMAGE")
                permalink = row.get("permalink", "")
                ts = row.get("timestamp", "")
                is_demo = row.get("is_demo", False)

                demo_badge = ' <span style="color: #F59E0B; font-size: 0.7rem;">[DEMO]</span>' if is_demo else ""

                st.markdown(f"""
                <div style="background: rgba(139,92,246,0.04); border: 1px solid rgba(139,92,246,0.1);
                            border-radius: 10px; padding: 12px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="color: rgba(255,255,255,0.4); font-size: 0.75rem;">📷 {media}{demo_badge}</span>
                        <span style="color: rgba(255,255,255,0.3); font-size: 0.72rem;">{str(ts)[:19]}</span>
                    </div>
                    <div style="color: rgba(255,255,255,0.8); font-size: 0.88rem; line-height: 1.4;">{caption}</div>
                    {"<a href='" + permalink + "' target='_blank' style='color: #8B5CF6; font-size: 0.78rem; text-decoration: none;'>View on Instagram →</a>" if permalink and not is_demo else ""}
                </div>
                """, unsafe_allow_html=True)
