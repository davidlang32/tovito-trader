"""
CLI Recorder
============

Drives interactive CLI scripts using wexpect (Windows-compatible pexpect)
and renders terminal output to PNG frames using Pillow. These frames
are then stitched into videos by the video_composer.
"""

import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.tutorials.config import (
    PROJECT_ROOT, DEV_DB_PATH, SCREENSHOT_DIR,
    VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
    TERMINAL_COLS, TERMINAL_ROWS, TERMINAL_BG_COLOR, TERMINAL_FG_COLOR,
    TERMINAL_FONT_SIZE, TERMINAL_PADDING,
)


def _get_mono_font(size):
    """Get a monospace font for terminal rendering."""
    mono_fonts = [
        "C:/Windows/Fonts/consola.ttf",  # Consolas
        "C:/Windows/Fonts/cour.ttf",      # Courier New
        "C:/Windows/Fonts/lucon.ttf",     # Lucida Console
    ]
    for font_path in mono_fonts:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue

    # Fallback
    return ImageFont.load_default()


def render_terminal_frame(text, title=None, width=None, height=None):
    """
    Render terminal text content into a PNG image.

    Creates an image that looks like a terminal window with dark background
    and light monospace text.

    Args:
        text: The terminal text content to render
        title: Optional title bar text (shown at top)
        width: Image width (defaults to VIEWPORT_WIDTH)
        height: Image height (defaults to VIEWPORT_HEIGHT)

    Returns:
        PIL Image object.
    """
    width = width or VIEWPORT_WIDTH
    height = height or VIEWPORT_HEIGHT

    img = Image.new('RGB', (width, height), TERMINAL_BG_COLOR)
    draw = ImageDraw.Draw(img)

    font = _get_mono_font(TERMINAL_FONT_SIZE)

    y_offset = TERMINAL_PADDING

    # Draw title bar if provided
    if title:
        title_font = _get_mono_font(14)
        # Title background bar
        draw.rectangle(
            [0, 0, width, 30],
            fill=(50, 50, 70),
        )
        # Window control dots
        for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            draw.ellipse([10 + i * 20, 8, 24 + i * 20, 22], fill=color)

        draw.text((80, 7), title, fill=(180, 180, 200), font=title_font)
        y_offset = 40

    # Render text lines
    lines = text.split('\n')
    line_height = TERMINAL_FONT_SIZE + 4

    for line in lines:
        if y_offset + line_height > height - TERMINAL_PADDING:
            break

        # Truncate long lines
        if len(line) > TERMINAL_COLS:
            line = line[:TERMINAL_COLS - 3] + '...'

        # Simple color support: detect common patterns
        color = TERMINAL_FG_COLOR
        if line.strip().startswith('ERROR') or line.strip().startswith('FAIL'):
            color = (243, 139, 168)  # Red
        elif line.strip().startswith('SUCCESS') or line.strip().startswith('PASS'):
            color = (166, 227, 161)  # Green
        elif line.strip().startswith('WARNING') or line.strip().startswith('WARN'):
            color = (249, 226, 175)  # Yellow
        elif line.strip().startswith('>>>') or line.strip().startswith('$'):
            color = (137, 180, 250)  # Blue (prompt)
        elif line.strip().startswith('#'):
            color = (108, 112, 134)  # Gray (comments)

        draw.text(
            (TERMINAL_PADDING, y_offset),
            line,
            fill=color,
            font=font,
        )
        y_offset += line_height

    return img


def save_terminal_frame(text, output_path, title=None):
    """
    Render terminal text to a PNG file.

    Args:
        text: Terminal text content
        output_path: Where to save the PNG
        title: Optional terminal window title

    Returns:
        Path to the saved image.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = render_terminal_frame(text, title=title)
    img.save(output_path)
    return output_path


class CLIRecorder:
    """
    Drives an interactive CLI script and captures terminal output as frames.

    Uses wexpect to spawn the script with predetermined inputs, capturing
    the terminal state at each step as a rendered PNG.

    Usage:
        recorder = CLIRecorder('scripts/investor/submit_fund_flow.py')
        recorder.spawn()
        recorder.expect_and_respond('Select type', '1')
        frame_path = recorder.capture_frame('step01', 'Selecting contribution type')
        recorder.close()
    """

    def __init__(self, script_path, env_overrides=None, title=None):
        """
        Args:
            script_path: Path to the Python script to drive (relative to PROJECT_ROOT)
            env_overrides: Dict of environment variable overrides
            title: Terminal window title for rendered frames
        """
        self.script_path = PROJECT_ROOT / script_path
        self.title = title or Path(script_path).name
        self._env = os.environ.copy()
        self._env['DATABASE_PATH'] = str(DEV_DB_PATH)
        self._env['PYTHONPATH'] = str(PROJECT_ROOT)

        if env_overrides:
            self._env.update(env_overrides)

        self._child = None
        self._buffer = ''

    def spawn(self):
        """Spawn the script as a child process."""
        import wexpect

        cmd = f'{sys.executable} {self.script_path}'
        self._child = wexpect.spawn(cmd, timeout=30, env=self._env)
        time.sleep(0.5)  # Let it initialize
        return self

    def expect_and_respond(self, pattern, response, timeout=15):
        """
        Wait for a pattern in the output, then send a response.

        Args:
            pattern: String or regex to wait for in the output
            response: String to send as input
            timeout: Seconds to wait for the pattern
        """
        if not self._child:
            raise RuntimeError("Process not spawned. Call spawn() first.")

        self._child.expect(pattern, timeout=timeout)
        self._buffer = self._child.before + self._child.after
        time.sleep(0.3)  # Brief pause for readability

        self._child.sendline(response)
        time.sleep(0.5)  # Let the script process the input

    def wait_for(self, pattern, timeout=15):
        """Wait for a pattern without sending a response."""
        if not self._child:
            raise RuntimeError("Process not spawned. Call spawn() first.")

        self._child.expect(pattern, timeout=timeout)
        self._buffer = self._child.before + self._child.after
        time.sleep(0.3)

    def read_output(self, timeout=5):
        """Read all available output."""
        if not self._child:
            raise RuntimeError("Process not spawned. Call spawn() first.")

        try:
            # Read until timeout (collect all output)
            import wexpect
            self._child.expect(wexpect.EOF, timeout=timeout)
            self._buffer = self._child.before
        except Exception:
            # Timeout is expected — just capture what we have
            if hasattr(self._child, 'before') and self._child.before:
                self._buffer = self._child.before

    def get_buffer(self):
        """Get the current terminal buffer content."""
        return self._buffer

    def capture_frame(self, name, title_override=None):
        """
        Render the current terminal buffer to a PNG screenshot.

        Args:
            name: Screenshot filename (without extension)
            title_override: Override the terminal window title for this frame

        Returns:
            Path to the saved PNG.
        """
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = SCREENSHOT_DIR / f'{name}.png'

        save_terminal_frame(
            text=self._buffer,
            output_path=output_path,
            title=title_override or self.title,
        )
        return output_path

    def close(self):
        """Close the child process."""
        if self._child:
            try:
                self._child.sendline('q')  # Try graceful exit
                time.sleep(0.5)
            except Exception:
                pass
            try:
                if self._child.isalive():
                    self._child.terminate()
            except Exception:
                pass
            self._child = None

    def __enter__(self):
        return self.spawn()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class CLICommandRecorder:
    """
    Records non-interactive CLI commands (scripts that just run and produce output).

    Simpler than CLIRecorder — runs the script, captures stdout/stderr,
    renders to a terminal frame.

    Usage:
        recorder = CLICommandRecorder()
        frame = recorder.run_and_capture(
            'python scripts/utilities/backup_database.py',
            name='backup_step01',
            title='Database Backup',
        )
    """

    def __init__(self, env_overrides=None):
        self._env = os.environ.copy()
        self._env['DATABASE_PATH'] = str(DEV_DB_PATH)
        self._env['PYTHONPATH'] = str(PROJECT_ROOT)

        if env_overrides:
            self._env.update(env_overrides)

    def run_and_capture(self, command, name, title=None, timeout=60):
        """
        Run a command and capture its output as a terminal frame.

        Args:
            command: Shell command string to execute
            name: Screenshot filename (without extension)
            title: Terminal window title
            timeout: Max seconds to wait for command

        Returns:
            Tuple of (output_text, frame_path).
        """
        import subprocess

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=self._env,
        )

        output = ''
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += '\n' + result.stderr

        output = output.strip()

        # Prepend the command for context
        display_text = f"$ {command}\n\n{output}"

        frame_path = save_terminal_frame(
            text=display_text,
            output_path=SCREENSHOT_DIR / f'{name}.png',
            title=title,
        )

        return output, frame_path
