"""
Video Composer
==============

Wraps ffmpeg to handle video encoding and composition:
- Encode Playwright webm recordings to H.264 MP4
- Stitch CLI terminal frame PNGs into MP4 video
- Add title and end cards
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.tutorials.config import (
    VIDEO_CRF, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
    FRAME_DURATION_SECONDS, TITLE_CARD_DURATION, END_CARD_DURATION,
    check_ffmpeg,
)


def _get_font(size):
    """Get a font, falling back to default if system fonts aren't available."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _run_ffmpeg(args, timeout=120):
    """Run ffmpeg with given args, raising on failure."""
    cmd = ['ffmpeg', '-y'] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}):\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stderr: {result.stderr[:1000]}"
        )
    return result


def _create_card_image(text, subtitle=None, width=None, height=None):
    """Create a title/end card image and return its path as a temp file."""
    width = width or VIEWPORT_WIDTH
    height = height or VIEWPORT_HEIGHT

    img = Image.new('RGB', (width, height), (15, 23, 42))  # Dark blue-gray
    draw = ImageDraw.Draw(img)

    # Main title
    title_font = _get_font(36)
    bbox = draw.textbbox((0, 0), text, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - tw) // 2, (height - th) // 2 - 20),
        text,
        fill=(255, 255, 255),
        font=title_font,
    )

    # Subtitle
    if subtitle:
        sub_font = _get_font(18)
        sbbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sw = sbbox[2] - sbbox[0]
        draw.text(
            ((width - sw) // 2, (height + th) // 2 + 10),
            subtitle,
            fill=(148, 163, 184),  # Gray
            font=sub_font,
        )

    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(tmp.name)
    return tmp.name


def encode_browser_video(raw_video_path, output_path):
    """
    Re-encode a Playwright webm recording to H.264 MP4.

    Args:
        raw_video_path: Path to the raw webm from Playwright
        output_path: Path for the final MP4

    Returns:
        Path to the output MP4.
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg not found on PATH. Install from https://ffmpeg.org/")

    raw_video_path = Path(raw_video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _run_ffmpeg([
        '-i', str(raw_video_path),
        '-c:v', 'libx264',
        '-crf', str(VIDEO_CRF),
        '-preset', 'medium',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        str(output_path),
    ])

    return output_path


def compose_cli_video(frame_paths, output_path, frame_duration=None):
    """
    Create a video from a sequence of PNG frames (for CLI tutorials).

    Each frame is displayed for `frame_duration` seconds.

    Args:
        frame_paths: List of paths to PNG frame images
        output_path: Path for the final MP4
        frame_duration: Seconds per frame (defaults to FRAME_DURATION_SECONDS)

    Returns:
        Path to the output MP4.
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg not found on PATH. Install from https://ffmpeg.org/")
    if not frame_paths:
        raise ValueError("No frames provided")

    frame_duration = frame_duration or FRAME_DURATION_SECONDS
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a concat file for ffmpeg
    concat_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False, encoding='utf-8'
    )
    for fp in frame_paths:
        # ffmpeg concat format
        concat_file.write(f"file '{Path(fp).resolve()}'\n")
        concat_file.write(f"duration {frame_duration}\n")
    # Repeat last frame to avoid truncation
    if frame_paths:
        concat_file.write(f"file '{Path(frame_paths[-1]).resolve()}'\n")
    concat_file.close()

    _run_ffmpeg([
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file.name,
        '-c:v', 'libx264',
        '-crf', str(VIDEO_CRF),
        '-preset', 'medium',
        '-pix_fmt', 'yuv420p',
        '-vf', f'scale={VIEWPORT_WIDTH}:{VIEWPORT_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIEWPORT_WIDTH}:{VIEWPORT_HEIGHT}:(ow-iw)/2:(oh-ih)/2',
        '-movflags', '+faststart',
        str(output_path),
    ])

    # Cleanup temp file
    Path(concat_file.name).unlink(missing_ok=True)

    return output_path


def add_title_card(video_path, title, subtitle=None, duration=None):
    """
    Prepend a title card to an existing video.

    Modifies the video in-place (re-encodes).

    Args:
        video_path: Path to existing MP4
        title: Title text
        subtitle: Optional subtitle text
        duration: Title card duration in seconds

    Returns:
        Path to the modified video.
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg not found on PATH. Install from https://ffmpeg.org/")

    duration = duration or TITLE_CARD_DURATION
    video_path = Path(video_path)

    # Create title card image
    card_path = _create_card_image(title, subtitle)

    # Create title card video — close temp file before ffmpeg writes (Windows lock)
    card_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    card_video_path = card_video.name
    card_video.close()
    _run_ffmpeg([
        '-loop', '1',
        '-i', card_path,
        '-c:v', 'libx264',
        '-t', str(duration),
        '-pix_fmt', 'yuv420p',
        '-vf', f'scale={VIEWPORT_WIDTH}:{VIEWPORT_HEIGHT}',
        card_video_path,
    ])

    # Concat title + main video
    concat_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False, encoding='utf-8'
    )
    concat_file.write(f"file '{Path(card_video_path).resolve()}'\n")
    concat_file.write(f"file '{video_path.resolve()}'\n")
    concat_file.close()

    output = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    output_path = output.name
    output.close()
    _run_ffmpeg([
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file.name,
        '-c', 'copy',
        '-movflags', '+faststart',
        output_path,
    ])

    # Replace original
    import shutil
    shutil.move(output_path, video_path)

    # Cleanup
    Path(card_path).unlink(missing_ok=True)
    Path(card_video_path).unlink(missing_ok=True)
    Path(concat_file.name).unlink(missing_ok=True)

    return video_path


def add_end_card(video_path, text="Tovito Trader", duration=None):
    """
    Append an end card to an existing video.

    Args:
        video_path: Path to existing MP4
        text: End card text
        duration: End card duration in seconds

    Returns:
        Path to the modified video.
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg not found on PATH. Install from https://ffmpeg.org/")

    duration = duration or END_CARD_DURATION
    video_path = Path(video_path)

    card_path = _create_card_image(text, subtitle="www.tovitotrader.com")

    card_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    card_video_path = card_video.name
    card_video.close()
    _run_ffmpeg([
        '-loop', '1',
        '-i', card_path,
        '-c:v', 'libx264',
        '-t', str(duration),
        '-pix_fmt', 'yuv420p',
        '-vf', f'scale={VIEWPORT_WIDTH}:{VIEWPORT_HEIGHT}',
        card_video_path,
    ])

    concat_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False, encoding='utf-8'
    )
    concat_file.write(f"file '{video_path.resolve()}'\n")
    concat_file.write(f"file '{Path(card_video_path).resolve()}'\n")
    concat_file.close()

    output = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    output_path = output.name
    output.close()
    _run_ffmpeg([
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file.name,
        '-c', 'copy',
        '-movflags', '+faststart',
        output_path,
    ])

    import shutil
    shutil.move(output_path, video_path)

    Path(card_path).unlink(missing_ok=True)
    Path(card_video_path).unlink(missing_ok=True)
    Path(concat_file.name).unlink(missing_ok=True)

    return video_path
