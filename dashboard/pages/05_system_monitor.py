"""
SocialTrendML — System Monitoring Page
API status, Kafka, database, collection history, and error log.
"""

import os
import sys
import time
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

st.set_page_config(page_title="SocialTrendML | System Monitor", page_icon="🖥️", layout="wide")

from dashboard.streamlit_app import COLORS, render_sidebar, get_mongo
from backend.app.core.config import get_settings

render_sidebar()

st.markdown("""
<div style="text-align: center; padding: 12px 0 20px 0;">
    <h1 style="font-size: 2rem; font-weight: 800;
               background: linear-gradient(135deg, #8B5CF6, #06B6D4);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🖥️ System Monitoring
    </h1>
    <p style="color: rgba(255,255,255,0.4); font-size: 0.9rem;">
        Service health, collection history, and diagnostics
    </p>
</div>
""", unsafe_allow_html=True)

settings = get_settings()

# ---- Service Status Cards ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">🔌 Service Status</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

# Database
db = get_mongo()
db_ok = db is not None and db.is_connected()
with col1:
    color = COLORS["positive"] if db_ok else COLORS["negative"]
    status = "Connected" if db_ok else "Disconnected"
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="font-size: 2rem;">🗄️</div>
        <div style="color: #F8FAFC; font-weight: 700; margin: 4px 0;">MongoDB</div>
        <div style="color: {color}; font-weight: 600; font-size: 0.9rem;">{status}</div>
        <div style="color: rgba(255,255,255,0.3); font-size: 0.72rem; margin-top: 4px;">
            {settings.mongodb_database}
        </div>
    </div>
    """, unsafe_allow_html=True)

# Instagram API
with col2:
    if settings.meta_access_token:
        api_color = COLORS["positive"]
        api_status = "Configured"
    else:
        api_color = COLORS["warning"]
        api_status = "Demo Mode"
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="font-size: 2rem;">📸</div>
        <div style="color: #F8FAFC; font-weight: 700; margin: 4px 0;">Instagram API</div>
        <div style="color: {api_color}; font-weight: 600; font-size: 0.9rem;">{api_status}</div>
        <div style="color: rgba(255,255,255,0.3); font-size: 0.72rem; margin-top: 4px;">
            {settings.meta_graph_api_version}
        </div>
    </div>
    """, unsafe_allow_html=True)

# Kafka
kafka_ok = False
try:
    from kafka import KafkaProducer
    kp = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        request_timeout_ms=3000,
    )
    kp.close()
    kafka_ok = True
except Exception:
    pass

with col3:
    color = COLORS["positive"] if kafka_ok else COLORS["negative"]
    status = "Connected" if kafka_ok else "Disconnected"
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="font-size: 2rem;">📨</div>
        <div style="color: #F8FAFC; font-weight: 700; margin: 4px 0;">Kafka</div>
        <div style="color: {color}; font-weight: 600; font-size: 0.9rem;">{status}</div>
        <div style="color: rgba(255,255,255,0.3); font-size: 0.72rem; margin-top: 4px;">
            {settings.kafka_bootstrap_servers}
        </div>
    </div>
    """, unsafe_allow_html=True)

# Spark ML
spark_ok = False
try:
    from pyspark.sql import SparkSession
    spark_ok = True
except ImportError:
    pass

with col4:
    color = COLORS["positive"] if spark_ok else COLORS["warning"]
    status = "Available" if spark_ok else "Not Installed"
    st.markdown(f"""
    <div style="background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.15);
                border-radius: 14px; padding: 20px; text-align: center;">
        <div style="font-size: 2rem;">⚡</div>
        <div style="color: #F8FAFC; font-weight: 700; margin: 4px 0;">Spark ML</div>
        <div style="color: {color}; font-weight: 600; font-size: 0.9rem;">{status}</div>
        <div style="color: rgba(255,255,255,0.3); font-size: 0.72rem; margin-top: 4px;">
            PySpark MLlib
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if not db:
    st.error("Cannot show more details — database is disconnected.")
    st.stop()

# ---- Database Stats ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">📊 Database Statistics</div>', unsafe_allow_html=True)

stat_cols = st.columns(4)
collections = ["instagram_posts", "hashtag_metrics", "sentiment_results", "collection_runs"]
emojis = ["📝", "📊", "💭", "🔄"]

for i, (coll, emoji) in enumerate(zip(collections, emojis)):
    with stat_cols[i]:
        try:
            count = db.get_collection(coll).count_documents({})
        except Exception:
            count = "?"
        st.metric(f"{emoji} {coll}", count)

# ---- Collection History ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">📋 Collection History</div>', unsafe_allow_html=True)

runs = db.get_collection_runs(limit=15)
if runs:
    df = pd.DataFrame(runs)
    display_cols = ["run_id", "status", "posts_collected", "hashtags", "is_demo", "started_at", "completed_at"]
    available_cols = [c for c in display_cols if c in df.columns]
    df_display = df[available_cols].copy()

    if "hashtags" in df_display.columns:
        df_display["hashtags"] = df_display["hashtags"].apply(lambda x: ", ".join(x[:3]) if isinstance(x, list) else str(x))
    if "started_at" in df_display.columns:
        df_display["started_at"] = pd.to_datetime(df_display["started_at"])
    if "completed_at" in df_display.columns:
        df_display["completed_at"] = pd.to_datetime(df_display["completed_at"])

    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.info("📭 No collection runs recorded")

# ---- Recent Errors ----
st.markdown('<div style="color: #F8FAFC; font-size: 1.1rem; font-weight: 700; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(139, 92, 246, 0.2);">⚠️ Recent Errors</div>', unsafe_allow_html=True)

errors = db.get_recent_errors(limit=5)
if errors:
    for err in errors:
        # Sanitize — never show tokens
        sanitized = err
        if settings.meta_access_token and settings.meta_access_token in sanitized:
            sanitized = sanitized.replace(settings.meta_access_token, "[REDACTED]")
        st.markdown(f"""
        <div style="background: rgba(239,68,68,0.06); border-left: 3px solid {COLORS['negative']};
                    border-radius: 0 8px 8px 0; padding: 10px 14px; margin-bottom: 6px;
                    color: rgba(255,255,255,0.7); font-size: 0.85rem;">
            {sanitized}
        </div>
        """, unsafe_allow_html=True)
else:
    st.success("✅ No recent errors")

# ---- Configuration (sanitized) ----
with st.expander("⚙️ Current Configuration (sanitized)"):
    st.json({
        "mongodb_uri": settings.mongodb_uri,
        "mongodb_database": settings.mongodb_database,
        "kafka_bootstrap_servers": settings.kafka_bootstrap_servers,
        "kafka_topic": settings.kafka_topic,
        "instagram_user_id": settings.instagram_user_id,
        "meta_graph_api_version": settings.meta_graph_api_version,
        "api_configured": settings.is_api_configured,
        "collection_interval_seconds": settings.collection_interval_seconds,
        "default_hashtags": settings.default_hashtags_list,
        "meta_access_token": "***REDACTED***" if settings.meta_access_token else "(not set)",
    })
