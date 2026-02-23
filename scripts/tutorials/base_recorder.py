"""
Base Recorder
=============

Abstract base class for all tutorial recorders. Provides:
- Step tracking (title, description, screenshot path)
- Automatic HTML guide generation after recording
- Automatic video composition after recording
- Output path management
"""

import time
from abc import ABC, abstractmethod
from pathlib import Path

from scripts.tutorials.config import (
    TUTORIAL_REGISTRY, VIDEO_DIR, GUIDE_DIR, SCREENSHOT_DIR,
    ensure_output_dirs,
)
from scripts.tutorials.html_generator import generate_guide
from scripts.tutorials.video_composer import (
    compose_cli_video, add_title_card, add_end_card, check_ffmpeg,
)


class TutorialStep:
    """A single recorded step in a tutorial."""

    def __init__(self, title, description, screenshot_path=None, timestamp=None):
        self.title = title
        self.description = description
        self.screenshot_path = screenshot_path
        self.timestamp = timestamp or time.time()


class BaseRecorder(ABC):
    """
    Base class for tutorial recorders.

    Subclasses implement `record()` to capture steps. After recording,
    call `generate_outputs()` to produce the video and HTML guide.
    """

    def __init__(self, tutorial_id):
        if tutorial_id not in TUTORIAL_REGISTRY:
            raise ValueError(
                f"Unknown tutorial_id '{tutorial_id}'. "
                f"Register it in config.TUTORIAL_REGISTRY first."
            )

        self.tutorial_id = tutorial_id
        self.meta = TUTORIAL_REGISTRY[tutorial_id]
        self.steps = []
        self._frame_paths = []  # For CLI video composition

        ensure_output_dirs()

    @property
    def video_path(self):
        return VIDEO_DIR / f'{self.tutorial_id}.mp4'

    @property
    def guide_path(self):
        return GUIDE_DIR / f'{self.tutorial_id}.html'

    def screenshot_path(self, step_number):
        """Get the path for a numbered screenshot."""
        return SCREENSHOT_DIR / f'{self.tutorial_id}_step{step_number:02d}.png'

    def add_step(self, title, description, screenshot_path=None):
        """
        Record a tutorial step.

        Args:
            title: Step title (e.g., "Click the Submit button")
            description: Step description with more detail
            screenshot_path: Path to the screenshot for this step
        """
        step = TutorialStep(title, description, screenshot_path)
        self.steps.append(step)

        if screenshot_path:
            self._frame_paths.append(str(screenshot_path))

        step_num = len(self.steps)
        print(f"  Step {step_num}: {title}")

        return step

    @abstractmethod
    def record(self):
        """
        Execute the tutorial recording.

        Subclasses should:
        1. Set up the environment (start services, open browser, etc.)
        2. Perform each step, calling self.add_step() for each
        3. Clean up (stop services, close browser, etc.)
        """
        pass

    def generate_html_guide(self):
        """Generate the HTML screenshot guide from recorded steps."""
        step_data = [
            {
                'title': s.title,
                'description': s.description,
                'screenshot_path': s.screenshot_path,
            }
            for s in self.steps
        ]

        path = generate_guide(
            steps=step_data,
            title=self.meta['title'],
            description=self.meta['description'],
            tutorial_id=self.tutorial_id,
        )
        print(f"  Guide: {path}")
        return path

    def generate_video(self):
        """
        Generate the video from recorded frames.

        For CLI tutorials, stitches frame PNGs into video.
        For browser tutorials, this is overridden to handle Playwright video.
        """
        if not check_ffmpeg():
            print("  WARNING: ffmpeg not found, skipping video generation")
            return None

        if not self._frame_paths:
            print("  WARNING: No frames recorded, skipping video generation")
            return None

        compose_cli_video(self._frame_paths, self.video_path)

        # Add title and end cards
        add_title_card(
            self.video_path,
            title=self.meta['title'],
            subtitle='Tovito Trader',
        )
        add_end_card(self.video_path)

        print(f"  Video: {self.video_path}")
        return self.video_path

    def run(self, skip_video=False):
        """
        Full tutorial recording pipeline.

        1. Record steps
        2. Generate HTML guide
        3. Generate video (unless skip_video=True)
        """
        print(f"\nRecording: {self.meta['title']}")
        print(f"  ID: {self.tutorial_id}")
        print(f"  Category: {self.meta['category']}")

        try:
            self.record()
        except Exception as e:
            print(f"  ERROR during recording: {e}")
            raise

        if not self.steps:
            print("  WARNING: No steps recorded")
            return

        # Generate outputs
        self.generate_html_guide()

        if not skip_video:
            self.generate_video()

        print(f"  Done! ({len(self.steps)} steps recorded)")
