"""
SocialTrendML — CLI Runner
Convenient entrypoint for starting API, Dashboard, Pipeline, or running Tests.

Usage:
    python run.py dashboard     # Start Streamlit dashboard
    python run.py api           # Start FastAPI backend server
    python run.py test          # Run automated test suite
    python run.py seed          # Seed demo data into MongoDB
    python run.py pipeline      # Run trend analytics aggregation pipeline
"""

import sys
import subprocess

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def start_dashboard():
    print("🚀 Starting Streamlit Dashboard on http://localhost:8501 ...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "dashboard/streamlit_app.py",
        "--server.port=8501", "--theme.base=dark"
    ])


def start_api():
    print("🚀 Starting SocialTrendML FastAPI Backend on http://localhost:8000 ...")
    print("   OpenAPI Docs available at: http://localhost:8000/docs")
    subprocess.run([
        sys.executable, "-m", "uvicorn", "backend.app.main:app",
        "--host", "0.0.0.0", "--port", "8000", "--reload"
    ])


def run_tests():
    print("🧪 Running Pytest Test Suite ...")
    sys.exit(subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"]).returncode)


def seed_data():
    print("🌱 Seeding demo data into MongoDB ...")
    from backend.app.database.mongodb import get_db
    from backend.app.services.demo_data import seed_demo_data
    db = get_db()
    count = seed_demo_data(db, count=200)
    print(f"✅ Successfully seeded {count} demo posts with engagement and sentiment metrics.")


def run_pipeline():
    print("⚡ Running PySpark / Pandas Analytics Aggregation Pipeline ...")
    from pipeline.spark_processor import run_spark_aggregation
    res = run_spark_aggregation()
    print(f"✅ Pipeline complete: {res}")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return

    cmd = args[0].lower()
    commands = {
        "dashboard": start_dashboard,
        "app": start_dashboard,
        "api": start_api,
        "server": start_api,
        "backend": start_api,
        "test": run_tests,
        "tests": run_tests,
        "seed": seed_data,
        "pipeline": run_pipeline,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: '{cmd}'. Supported commands: {', '.join(commands.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
