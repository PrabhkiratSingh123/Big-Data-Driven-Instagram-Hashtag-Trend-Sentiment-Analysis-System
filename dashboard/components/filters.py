"""
Sidebar filter components for the Instagram Analytics dashboard.
Provides time range, hashtag, and engagement threshold filters.
"""

import streamlit as st
from datetime import datetime, timedelta, timezone


def render_sidebar_filters():
    """Render all sidebar filter controls and return selected values."""

    st.sidebar.markdown(
        """
        <div style="text-align: center; padding: 16px 0 8px 0;">
            <span style="font-size: 1.8rem;">📊</span>
            <h2 style="margin: 4px 0; font-size: 1.1rem; font-weight: 700;
                       background: linear-gradient(135deg, #8B5CF6, #06B6D4);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                Instagram Analytics
            </h2>
            <p style="color: rgba(255,255,255,0.4); font-size: 0.75rem; margin: 0;">
                Real-Time Hashtag Trends & Sentiment
            </p>
        </div>
        <hr style="border-color: rgba(139,92,246,0.15); margin: 12px 0;">
        """,
        unsafe_allow_html=True,
    )

    # ---- Time Range Filter ----
    st.sidebar.markdown("#### ⏱️ Time Range")
    time_options = {
        "Last 15 minutes": 15,
        "Last 1 hour": 60,
        "Last 6 hours": 360,
        "Last 24 hours": 1440,
        "Last 7 days": 10080,
        "All time": 0,
    }
    selected_time = st.sidebar.selectbox(
        "Select period",
        options=list(time_options.keys()),
        index=3,  # Default: Last 24 hours
        label_visibility="collapsed",
    )
    time_minutes = time_options[selected_time]

    if time_minutes > 0:
        time_cutoff = datetime.now(timezone.utc) - timedelta(minutes=time_minutes)
    else:
        time_cutoff = None

    st.sidebar.markdown("---")

    # ---- Hashtag Filter ----
    st.sidebar.markdown("#### #️⃣ Hashtag Filter")
    hashtag_input = st.sidebar.text_input(
        "Filter by hashtag",
        placeholder="e.g., travel, fitness",
        label_visibility="collapsed",
    )
    selected_hashtags = [
        h.strip().lower().lstrip("#")
        for h in hashtag_input.split(",")
        if h.strip()
    ]

    st.sidebar.markdown("---")

    # ---- Top N Control ----
    st.sidebar.markdown("#### 🔝 Display Limit")
    top_n = st.sidebar.slider(
        "Number of items to show",
        min_value=5,
        max_value=50,
        value=15,
        step=5,
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")

    # ---- Auto-Refresh ----
    st.sidebar.markdown("#### 🔄 Auto-Refresh")
    auto_refresh = st.sidebar.checkbox("Enable auto-refresh", value=True)
    refresh_interval = st.sidebar.select_slider(
        "Interval (seconds)",
        options=[10, 15, 30, 60, 120],
        value=30,
        label_visibility="collapsed",
        disabled=not auto_refresh,
    )

    st.sidebar.markdown("---")

    # ---- Pipeline Status ----
    st.sidebar.markdown("#### 📡 Pipeline Status")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.82rem; line-height: 2;">
            <span class="live-dot" style="width:6px;height:6px;background:#10B981;
                  border-radius:50%;display:inline-block;animation:pulse 2s infinite;">
            </span> MongoDB Connected<br>
            <span style="width:6px;height:6px;background:#F59E0B;
                  border-radius:50%;display:inline-block;">
            </span> Kafka Streaming<br>
            <span style="width:6px;height:6px;background:#8B5CF6;
                  border-radius:50%;display:inline-block;">
            </span> Spark Processing
        </div>
        """,
        unsafe_allow_html=True,
    )

    return {
        "time_cutoff": time_cutoff,
        "time_label": selected_time,
        "hashtags": selected_hashtags if selected_hashtags else None,
        "top_n": top_n,
        "auto_refresh": auto_refresh,
        "refresh_interval": refresh_interval,
    }
