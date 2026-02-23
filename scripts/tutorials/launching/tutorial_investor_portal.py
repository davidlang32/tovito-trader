"""
Tutorial: Starting the Investor Portal
========================================

Records how to launch the FastAPI backend and React frontend.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'launch_investor_portal'


class InvestorPortalLaunchTutorial(BaseRecorder):
    """Records how to start the investor portal."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Step 1: Start API
        api_text = (
            "# Starting the Investor Portal\n"
            "#\n"
            "# The investor portal has two components:\n"
            "#   1. FastAPI backend (port 8000)\n"
            "#   2. React frontend (port 3000)\n"
            "#\n"
            "# Start the API backend first:\n"
            "\n"
            "$ cd apps/investor_portal/api\n"
            "$ uvicorn main:app --reload\n"
            "\n"
            "INFO:     Uvicorn running on http://127.0.0.1:8000\n"
            "INFO:     Started reloader process\n"
            "INFO:     Started server process\n"
            "INFO:     Waiting for application startup.\n"
            "INFO:     Application startup complete.\n"
            "\n"
            "# API is ready! Swagger docs at http://localhost:8000/docs"
        )
        path = save_terminal_frame(
            api_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Terminal 1 - API Server',
        )
        self.add_step(
            'Start the API Backend',
            'Open a terminal and run uvicorn to start the FastAPI backend on port 8000. '
            'The --reload flag enables auto-restart when code changes.',
            str(path),
        )

        # Step 2: Start frontend
        frontend_text = (
            "# In a second terminal, start the React frontend:\n"
            "\n"
            "$ cd apps/investor_portal/frontend/investor_portal\n"
            "$ npm run dev\n"
            "\n"
            "  VITE v5.0.0  ready in 523 ms\n"
            "\n"
            "  > Local:   http://localhost:3000/\n"
            "  > Network: http://192.168.1.100:3000/\n"
            "\n"
            "  press h + enter to show help\n"
            "\n"
            "# Frontend is ready! Open http://localhost:3000 in your browser."
        )
        path = save_terminal_frame(
            frontend_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step02.png',
            title='Terminal 2 - Frontend',
        )
        self.add_step(
            'Start the React Frontend',
            'In a second terminal, run npm dev to start the Vite dev server on port 3000. '
            'The frontend proxies API calls to the backend automatically.',
            str(path),
        )

        # Step 3: Access
        access_text = (
            "# Investor Portal is running!\n"
            "#\n"
            "# URLs:\n"
            "#   Portal:     http://localhost:3000\n"
            "#   API Docs:   http://localhost:8000/docs\n"
            "#   Health:     http://localhost:8000/health\n"
            "#\n"
            "# To stop:\n"
            "#   Press Ctrl+C in each terminal window\n"
            "#\n"
            "# Tip: Both servers must be running for the portal to work.\n"
            "# The frontend proxies /api/* requests to the backend."
        )
        path = save_terminal_frame(
            access_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step03.png',
            title='Investor Portal',
        )
        self.add_step(
            'Access the Portal',
            'Open http://localhost:3000 in your browser. The API docs are available at '
            'http://localhost:8000/docs. Both terminals must stay open.',
            str(path),
        )


if __name__ == '__main__':
    InvestorPortalLaunchTutorial(TUTORIAL_ID).run()
