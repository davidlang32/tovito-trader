"""
Start Dev Environment
======================

One-command launcher for the Tovito Trader API in development mode.

What it does:
1. Sets TOVITO_ENV=development
2. Creates dev_tovito.db if it doesn't exist (runs setup_test_database.py)
3. Starts uvicorn on port 8000 with hot reload

Usage:
    python scripts/setup/start_dev.py              # Start dev API
    python scripts/setup/start_dev.py --port 8001   # Custom port
    python scripts/setup/start_dev.py --reset-db     # Rebuild dev database first
    python scripts/setup/start_dev.py --reset-prospects  # Clear prospect data only
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Start Tovito Trader API in development mode")
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--reset-db", action="store_true", help="Rebuild dev database from scratch")
    parser.add_argument("--reset-prospects", action="store_true", help="Clear prospect data only")
    parser.add_argument("--no-reload", action="store_true", help="Disable hot reload")
    args = parser.parse_args()

    # Always use development environment
    os.environ["TOVITO_ENV"] = "development"

    # Resolve paths
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)

    dev_db = project_root / "data" / "dev_tovito.db"
    setup_script = project_root / "scripts" / "setup" / "setup_test_database.py"

    print("")
    print("=" * 60)
    print("   TOVITO TRADER  --  DEVELOPMENT MODE")
    print("=" * 60)
    print(f"   Project root: {project_root}")
    print(f"   Dev database: {dev_db}")
    print(f"   API port:     {args.port}")
    print("=" * 60)
    print("")

    # Handle database setup
    if args.reset_db:
        print("[START] Rebuilding dev database from scratch...")
        result = subprocess.run(
            [sys.executable, str(setup_script), "--env", "dev"],
            cwd=str(project_root)
        )
        if result.returncode != 0:
            print("[ERROR] Database setup failed")
            sys.exit(1)
        print("[OK] Dev database rebuilt")
        print("")
    elif args.reset_prospects:
        print("[START] Clearing prospect data...")
        result = subprocess.run(
            [sys.executable, str(setup_script), "--env", "dev", "--reset-prospects"],
            cwd=str(project_root)
        )
        if result.returncode != 0:
            print("[ERROR] Prospect reset failed")
            sys.exit(1)
        print("[OK] Prospect data cleared")
        print("")
    elif not dev_db.exists():
        print("[WARN] Dev database not found. Creating it now...")
        print("")
        result = subprocess.run(
            [sys.executable, str(setup_script), "--env", "dev"],
            cwd=str(project_root)
        )
        if result.returncode != 0:
            print("[ERROR] Database setup failed")
            sys.exit(1)
        print("")
        print("[OK] Dev database created")
        print("")
    else:
        print(f"[OK] Dev database exists: {dev_db}")
        print("")

    # Start uvicorn
    print(f"[START] Starting API on http://localhost:{args.port}")
    print(f"   Docs: http://localhost:{args.port}/docs")
    print(f"   Press Ctrl+C to stop")
    print("")

    uvicorn_args = [
        sys.executable, "-m", "uvicorn",
        "apps.investor_portal.api.main:app",
        "--port", str(args.port),
    ]
    if not args.no_reload:
        uvicorn_args.append("--reload")

    try:
        subprocess.run(uvicorn_args, cwd=str(project_root))
    except KeyboardInterrupt:
        print("")
        print("[STOP] Dev server stopped")


if __name__ == "__main__":
    main()
