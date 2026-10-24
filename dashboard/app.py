"""
SocialTrendML — Streamlit Application Entrypoint
Forwarding entry point to dashboard/streamlit_app.py for unified navigation.
"""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard.streamlit_app import main

if __name__ == "__main__":
    main()
