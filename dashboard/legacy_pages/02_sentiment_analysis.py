"""
🧠 Sentiment Analysis Page
Visualizes sentiment distribution, trends over time,
and per-hashtag sentiment breakdowns.
"""

import os
import sys
import time
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from storage.mongo_client import MongoDBClient
from dashboard.components.charts import (
    create_sentiment_donut,
    create_sentiment_timeline,
    create_trending_bar_chart,
    COLORS, SENTIMENT_COLORS,
)
from dashboard.components.filters import render_sidebar_filters

st.set_page_config(
    page_title="Instagram Analytics | Sentiment Analysis",
    page_icon="🧠",
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


def generate_wordcloud_image(texts: list[str], sentiment: str):
    """Generate a word cloud image for a given sentiment."""
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt

        color_map = {
            "positive": "Greens",
            "negative": "Reds",
            "neutral": "Greys",
        }

        text = " ".join(texts)
        if not text.strip():
            return None

        wc = WordCloud(
            width=800,
            height=400,
            background_color="#0B0B14",
            colormap=color_map.get(sentiment, "Purples"),
            max_words=80,
            max_font_size=80,
            random_state=42,
            contour_width=0,
        ).generate(text)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        fig.patch.set_facecolor("#0B0B14")

        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="#0B0B14", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf
    except ImportError:
        return None


def main():
    filters = render_sidebar_filters()

    st.markdown(
        """
        <div class="fade-in" style="padding-bottom: 20px;">
            <h1 style="font-size: 2rem; font-weight: 800;
                       background: linear-gradient(135deg, #8B5CF6, #06B6D4);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                🧠 Sentiment Analysis
            </h1>
            <p style="color: rgba(255,255,255,0.4); margin-top: -8px;">
                ML-powered sentiment classification of Instagram captions
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

    sentiment_coll = mongo.get_collection("sentiment_scores")

    # ---- Build query filter ----
    query_filter = {}
    if filters.get("time_cutoff"):
        query_filter["timestamp"] = {"$gte": filters["time_cutoff"]}

    # ---- Sentiment Distribution ----
    st.markdown('<div class="section-header">📊 Sentiment Distribution</div>', unsafe_allow_html=True)

    pipeline = [
        {"$match": query_filter} if query_filter else {"$match": {}},
        {
            "$group": {
                "_id": "$sentiment_label",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$sentiment_score"},
                "avg_confidence": {"$avg": "$confidence"},
            }
        },
        {"$sort": {"count": -1}},
    ]
    dist_data = list(sentiment_coll.aggregate(pipeline))

    if dist_data:
        df_dist = pd.DataFrame(dist_data).rename(columns={"_id": "sentiment"})
        total = df_dist["count"].sum()

        # Metric cards
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)

        with mcol1:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Total Analyzed</div>
                    <div class="metric-value">{total:,}</div>
                    <div class="metric-delta positive">Posts processed</div>
                </div>""",
                unsafe_allow_html=True,
            )

        for i, sentiment in enumerate(["positive", "negative", "neutral"]):
            row = df_dist[df_dist["sentiment"] == sentiment]
            count = int(row["count"].values[0]) if len(row) > 0 else 0
            pct = (count / total * 100) if total > 0 else 0
            color = SENTIMENT_COLORS.get(sentiment, "#6B7280")
            emoji = {"positive": "😊", "negative": "😞", "neutral": "😐"}.get(sentiment, "")

            with [mcol2, mcol3, mcol4][i]:
                st.markdown(
                    f"""<div class="metric-card">
                        <div class="metric-label">{emoji} {sentiment.title()}</div>
                        <div class="metric-value" style="-webkit-text-fill-color:{color};">{pct:.1f}%</div>
                        <div class="metric-delta" style="color:{color};">{count:,} posts</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Donut chart
        col_donut, col_info = st.columns([3, 2])
        with col_donut:
            fig = create_sentiment_donut(df_dist, title="Overall Sentiment Distribution")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_info:
            st.markdown('<div class="section-header">📋 Breakdown</div>', unsafe_allow_html=True)
            for _, row in df_dist.iterrows():
                sentiment = row["sentiment"]
                count = row["count"]
                pct = count / total * 100
                color = SENTIMENT_COLORS.get(sentiment, "#6B7280")

                st.markdown(
                    f"""
                    <div style="padding: 12px; margin: 8px 0; border-radius: 10px;
                                background: rgba({','.join(str(int(color[i:i+2], 16)) for i in (1,3,5))}, 0.08);
                                border-left: 3px solid {color};">
                        <span style="font-weight: 600; color: {color};">{sentiment.title()}</span>
                        <span style="float: right; color: rgba(255,255,255,0.6);">{count:,} ({pct:.1f}%)</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ---- Sentiment Over Time ----
        st.markdown('<div class="section-header">📈 Sentiment Over Time</div>', unsafe_allow_html=True)

        time_pipeline = [
            {"$match": query_filter} if query_filter else {"$match": {}},
            {
                "$group": {
                    "_id": {
                        "hour": {"$dateToString": {"format": "%Y-%m-%d %H:00", "date": "$timestamp"}},
                        "sentiment": "$sentiment_label",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.hour": 1}},
        ]
        time_data = list(sentiment_coll.aggregate(time_pipeline))

        if time_data:
            # Pivot data for stacked area chart
            time_df = pd.DataFrame([
                {"timestamp": d["_id"]["hour"], "sentiment": d["_id"]["sentiment"], "count": d["count"]}
                for d in time_data
            ])
            pivot_df = time_df.pivot_table(
                index="timestamp", columns="sentiment", values="count", fill_value=0
            ).reset_index()

            fig_timeline = create_sentiment_timeline(pivot_df, title="Sentiment Trends by Hour")
            st.plotly_chart(fig_timeline, use_container_width=True, config={"displayModeBar": False})

        # ---- Word Clouds ----
        st.markdown('<div class="section-header">☁️ Word Clouds by Sentiment</div>', unsafe_allow_html=True)

        wc_cols = st.columns(3)
        for i, sentiment in enumerate(["positive", "neutral", "negative"]):
            with wc_cols[i]:
                st.markdown(
                    f"<h4 style='text-align:center; color:{SENTIMENT_COLORS[sentiment]};'>"
                    f"{sentiment.title()}</h4>",
                    unsafe_allow_html=True,
                )

                captions = list(
                    sentiment_coll.find(
                        {"sentiment_label": sentiment},
                        {"caption": 1, "_id": 0},
                    ).limit(200)
                )
                texts = [c.get("caption", "") for c in captions if c.get("caption")]

                if texts:
                    img_buf = generate_wordcloud_image(texts, sentiment)
                    if img_buf:
                        st.image(img_buf, use_container_width=True)
                    else:
                        st.info("Install `wordcloud` package for word clouds.")
                else:
                    st.info(f"No {sentiment} captions yet.")

        # ---- Recent Sentiment Results ----
        st.markdown('<div class="section-header">🔍 Recent Sentiment Results</div>', unsafe_allow_html=True)

        recent = list(
            sentiment_coll.find(
                query_filter,
                {"_id": 0, "post_id": 1, "caption": 1, "sentiment_label": 1, "sentiment_score": 1, "timestamp": 1},
            )
            .sort("timestamp", -1)
            .limit(20)
        )

        if recent:
            df_recent = pd.DataFrame(recent)
            if "caption" in df_recent.columns:
                df_recent["caption"] = df_recent["caption"].str[:80] + "..."

            st.dataframe(
                df_recent,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "post_id": st.column_config.TextColumn("Post ID", width="small"),
                    "caption": st.column_config.TextColumn("Caption", width="large"),
                    "sentiment_label": st.column_config.TextColumn("Sentiment", width="small"),
                    "sentiment_score": st.column_config.ProgressColumn(
                        "Score", min_value=0, max_value=1, format="%.2f",
                    ),
                    "timestamp": st.column_config.DatetimeColumn("Time", width="medium"),
                },
            )
    else:
        st.info(
            "📭 No sentiment data available yet.\n\n"
            "**To get started:**\n"
            "1. Train the model: `python processing/pyspark-ml/sentiment_model.py`\n"
            "2. Run the stream processor: `python processing/pyspark-ml/stream_processor.py`"
        )

    st.markdown(
        '<div class="footer">Sentiment Analysis · Powered by Spark MLlib</div>',
        unsafe_allow_html=True,
    )

    if filters["auto_refresh"]:
        time.sleep(filters["refresh_interval"])
        st.rerun()


main()
