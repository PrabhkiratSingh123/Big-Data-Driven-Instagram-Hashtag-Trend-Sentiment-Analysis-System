"""
SocialTrendML — Sentiment Analysis Page
Sentiment distribution charts, changes over time, keyword analysis, and example posts.
"""

import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

st.set_page_config(page_title="SocialTrendML | Sentiment Analysis", page_icon="💭", layout="wide")

from dashboard.streamlit_app import COLORS, render_sidebar, get_mongo, ensure_demo_data

render_sidebar()

st.markdown("""
<div style="text-align: center; padding: 12px 0 20px 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
               background: linear-gradient(135deg, #8B5CF6, #06B6D4);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        💭 Sentiment Analysis
    </h1>
    <p style="color: rgba(255,255,255,0.4); font-size: 0.9rem;">
        Powered by Spark ML · Caption sentiment classification and keyword insights
    </p>
</div>
""", unsafe_allow_html=True)

db = get_mongo()
if db is None:
    st.error("❌ Cannot connect to MongoDB")
    st.stop()

ensure_demo_data(db)

# Filters
filter_col1, filter_col2 = st.columns([2, 1])
with filter_col1:
    available = db.get_unique_hashtags()
    filter_hashtag = st.selectbox("Filter by hashtag", ["All Hashtags"] + available)
with filter_col2:
    time_range = st.selectbox("Time range", ["7 days", "14 days", "30 days"])
    days = int(time_range.split()[0])

hashtag_filter = None if filter_hashtag == "All Hashtags" else filter_hashtag

# ---- Overall Distribution ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">📊 Sentiment Distribution</div>', unsafe_allow_html=True)

dist = db.get_sentiment_distribution(hashtag=hashtag_filter)

if dist:
    dist_col1, dist_col2 = st.columns([1, 1])

    with dist_col1:
        labels = list(dist.keys())
        values = list(dist.values())
        total = sum(values)
        color_map = {"positive": COLORS["positive"], "negative": COLORS["negative"], "neutral": COLORS["neutral"]}

        fig = go.Figure(data=[go.Pie(
            labels=[l.capitalize() for l in labels],
            values=values,
            hole=0.6,
            marker=dict(colors=[color_map.get(l, "#6366F1") for l in labels],
                       line=dict(color="rgba(0,0,0,0.3)", width=2)),
            textinfo="label+percent",
            textfont=dict(color="white", size=13),
        )])
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
            showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300,
            annotations=[dict(text=f"{total}", x=0.5, y=0.5, font_size=28,
                            font_color="#F8FAFC", showarrow=False)],
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with dist_col2:
        # Sentiment by hashtag comparison
        if len(available) > 1:
            st.markdown("**Per-Hashtag Sentiment**")
            rows = []
            for h in available[:8]:
                h_dist = db.get_sentiment_distribution(hashtag=h)
                h_total = sum(h_dist.values()) or 1
                rows.append({
                    "hashtag": f"#{h}",
                    "Positive": h_dist.get("positive", 0) / h_total * 100,
                    "Neutral": h_dist.get("neutral", 0) / h_total * 100,
                    "Negative": h_dist.get("negative", 0) / h_total * 100,
                })
            df_h = pd.DataFrame(rows)
            fig = px.bar(
                df_h, x="hashtag", y=["Positive", "Neutral", "Negative"],
                barmode="stack",
                color_discrete_map={"Positive": COLORS["positive"], "Neutral": COLORS["neutral"], "Negative": COLORS["negative"]},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="rgba(255,255,255,0.7)", size=10),
                yaxis_title="Percentage (%)", margin=dict(t=5, b=5), height=300,
                legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.15),
                xaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
                yaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("📭 No sentiment data available")
    st.stop()

# ---- Sentiment Over Time ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">📈 Sentiment Over Time</div>', unsafe_allow_html=True)

over_time = db.get_sentiment_over_time(days=days, hashtag=hashtag_filter)
if over_time:
    rows = [{"date": r["_id"]["date"], "sentiment": r["_id"]["sentiment"], "count": r["count"]} for r in over_time]
    df_time = pd.DataFrame(rows)
    df_time["date"] = pd.to_datetime(df_time["date"])
    df_time["sentiment"] = df_time["sentiment"].str.capitalize()

    color_map = {"Positive": COLORS["positive"], "Negative": COLORS["negative"], "Neutral": COLORS["neutral"]}
    fig = px.area(
        df_time, x="date", y="count", color="sentiment",
        color_discrete_map=color_map,
        labels={"count": "Posts", "date": "Date"},
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="rgba(255,255,255,0.7)", family="Inter"),
        xaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
        yaxis=dict(gridcolor="rgba(139,92,246,0.08)"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=10, b=40), height=350,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("📭 No time-series sentiment data")

# ---- Top Keywords ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">🔑 Top Keywords by Sentiment</div>', unsafe_allow_html=True)

kw_col1, kw_col2 = st.columns(2)

with kw_col1:
    st.markdown("**😊 Positive Keywords**")
    pos_kw = db.get_top_keywords(sentiment="positive", limit=12)
    if pos_kw:
        df_pk = pd.DataFrame([{"keyword": k["_id"], "count": k["count"]} for k in pos_kw])
        fig = px.bar(df_pk, y="keyword", x="count", orientation="h", color_discrete_sequence=[COLORS["positive"]])
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.7)", size=10),
            yaxis=dict(autorange="reversed"), margin=dict(t=5, b=5, l=5, r=5), height=350,
            xaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("No positive keywords found")

with kw_col2:
    st.markdown("**😡 Negative Keywords**")
    neg_kw = db.get_top_keywords(sentiment="negative", limit=12)
    if neg_kw:
        df_nk = pd.DataFrame([{"keyword": k["_id"], "count": k["count"]} for k in neg_kw])
        fig = px.bar(df_nk, y="keyword", x="count", orientation="h", color_discrete_sequence=[COLORS["negative"]])
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.7)", size=10),
            yaxis=dict(autorange="reversed"), margin=dict(t=5, b=5, l=5, r=5), height=350,
            xaxis=dict(gridcolor="rgba(139,92,246,0.05)"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("No negative keywords found")

# ---- Example Analyzed Captions ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">📝 Example Analyzed Captions</div>', unsafe_allow_html=True)

sentiment_coll = db.get_collection("sentiment_results")
query = {}
if hashtag_filter:
    query["source_hashtag"] = hashtag_filter

examples = list(
    sentiment_coll.find(query, {"_id": 0})
    .sort("analyzed_at", -1)
    .limit(12)
)

if examples:
    for ex in examples:
        sentiment = ex.get("sentiment", "neutral")
        confidence = ex.get("confidence", 0)
        caption = (ex.get("caption", "") or "")[:250]
        model = ex.get("model", "unknown")
        post_id = ex.get("post_id", "")

        color = COLORS.get(sentiment, "#6366F1")
        emoji = {"positive": "😊", "negative": "😡", "neutral": "😐"}.get(sentiment, "❓")

        # Try to find permalink from posts
        post = db.get_collection("instagram_posts").find_one({"post_id": post_id}, {"permalink": 1, "is_demo": 1})
        permalink = post.get("permalink", "") if post else ""
        is_demo = post.get("is_demo", False) if post else False

        st.markdown(f"""
        <div style="background: rgba(139,92,246,0.04); border-left: 3px solid {color};
                    border-radius: 0 10px 10px 0; padding: 12px 16px; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="color: {color}; font-weight: 700; font-size: 0.85rem;">
                    {emoji} {sentiment.capitalize()} ({confidence:.0%})
                </span>
                <span style="color: rgba(255,255,255,0.25); font-size: 0.7rem;">
                    Model: {model} {'[DEMO]' if is_demo else ''}
                </span>
            </div>
            <div style="color: rgba(255,255,255,0.75); font-size: 0.88rem; line-height: 1.45;">{caption}</div>
            {"<a href='" + permalink + "' target='_blank' style='color: #8B5CF6; font-size: 0.75rem; text-decoration: none; margin-top: 4px; display: block;'>View original post →</a>" if permalink and not is_demo else ""}
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("📭 No analyzed captions")

# Model info
with st.expander("ℹ️ About the Sentiment Model"):
    st.markdown("""
    **SocialTrendML uses a PySpark MLlib pipeline for sentiment classification:**

    - **Pipeline**: `RegexTokenizer → StopWordsRemover → CountVectorizer → IDF → LogisticRegression`
    - **Classes**: Positive, Neutral, Negative (3-class multinomial)
    - **Training Data**: Curated English-language labeled examples (demo training set)
    - **Fallback**: VADER (rule-based) when Spark is unavailable

    **Limitations:**
    - English-only — non-English captions may produce unreliable results
    - Trained on curated examples, not a production-grade NLP corpus
    - Sentiment scores are model predictions, not objective truth
    - Emojis and slang may not be fully captured
    """)
