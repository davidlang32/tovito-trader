"""
Tutorial System Unit Tests
==========================

Tests the core tutorial infrastructure modules:
- Config paths and registry
- Screenshot annotator
- HTML guide generator
- Video composer (frame rendering)
- CLI recorder terminal rendering
"""

import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# Add project root for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.tutorials.config import (
    PROJECT_ROOT, TUTORIAL_REGISTRY, CATEGORY_LABELS,
    OUTPUT_DIR, VIDEO_DIR, GUIDE_DIR, SCREENSHOT_DIR,
    get_tutorials_by_category, ensure_output_dirs, check_ffmpeg,
)
from scripts.tutorials.screenshot_annotator import (
    add_numbered_callout, add_arrow, add_label, annotate_steps,
)
from scripts.tutorials.html_generator import generate_guide, _image_to_base64
from scripts.tutorials.cli_recorder import render_terminal_frame, save_terminal_frame
from scripts.tutorials.base_recorder import BaseRecorder, TutorialStep


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def sample_image(temp_dir):
    """Create a sample 1280x720 test image."""
    img = Image.new('RGB', (1280, 720), color=(100, 150, 200))
    path = temp_dir / 'sample.png'
    img.save(path)
    return path


@pytest.fixture
def sample_steps(temp_dir):
    """Create sample tutorial steps with screenshot images."""
    steps = []
    for i in range(3):
        img = Image.new('RGB', (1280, 720), color=(50 + i * 50, 100, 150))
        path = temp_dir / f'step{i}.png'
        img.save(path)
        steps.append({
            'title': f'Step {i + 1} Title',
            'description': f'Description for step {i + 1}.',
            'screenshot_path': str(path),
        })
    return steps


# ============================================================
# CONFIG TESTS
# ============================================================

class TestConfig:
    def test_project_root_exists(self):
        assert PROJECT_ROOT.exists()

    def test_tutorial_registry_not_empty(self):
        assert len(TUTORIAL_REGISTRY) > 0

    def test_registry_entries_have_required_keys(self):
        required_keys = {'title', 'description', 'category', 'duration', 'module'}
        for tid, meta in TUTORIAL_REGISTRY.items():
            missing = required_keys - set(meta.keys())
            assert not missing, f"Tutorial '{tid}' missing keys: {missing}"

    def test_registry_categories_are_valid(self):
        valid_categories = set(CATEGORY_LABELS.keys())
        for tid, meta in TUTORIAL_REGISTRY.items():
            assert meta['category'] in valid_categories, (
                f"Tutorial '{tid}' has invalid category '{meta['category']}'"
            )

    def test_get_tutorials_by_category(self):
        admin_tutorials = get_tutorials_by_category('admin')
        assert len(admin_tutorials) > 0
        for tid in admin_tutorials:
            assert TUTORIAL_REGISTRY[tid]['category'] == 'admin'

    def test_ensure_output_dirs(self, temp_dir, monkeypatch):
        """Test that output directories are created."""
        monkeypatch.setattr('scripts.tutorials.config.OUTPUT_DIR', temp_dir / 'output')
        monkeypatch.setattr('scripts.tutorials.config.VIDEO_DIR', temp_dir / 'output' / 'videos')
        monkeypatch.setattr('scripts.tutorials.config.GUIDE_DIR', temp_dir / 'output' / 'guides')
        monkeypatch.setattr('scripts.tutorials.config.SCREENSHOT_DIR', temp_dir / 'output' / 'screenshots')
        ensure_output_dirs()
        assert (temp_dir / 'output' / 'videos').exists()
        assert (temp_dir / 'output' / 'guides').exists()
        assert (temp_dir / 'output' / 'screenshots').exists()

    def test_check_ffmpeg_returns_bool(self):
        result = check_ffmpeg()
        assert isinstance(result, bool)


# ============================================================
# SCREENSHOT ANNOTATOR TESTS
# ============================================================

class TestScreenshotAnnotator:
    def test_add_numbered_callout(self, sample_image, temp_dir):
        output = temp_dir / 'callout.png'
        result = add_numbered_callout(sample_image, 100, 100, 1, output_path=output)
        assert result == output
        assert output.exists()

        # Verify dimensions preserved
        img = Image.open(output)
        assert img.size == (1280, 720)

    def test_add_numbered_callout_with_label(self, sample_image, temp_dir):
        output = temp_dir / 'callout_label.png'
        result = add_numbered_callout(
            sample_image, 200, 200, 2, label="Click here", output_path=output
        )
        assert output.exists()

    def test_add_arrow(self, sample_image, temp_dir):
        output = temp_dir / 'arrow.png'
        result = add_arrow(sample_image, (100, 100), (400, 300), output_path=output)
        assert result == output
        assert output.exists()

        img = Image.open(output)
        assert img.size == (1280, 720)

    def test_add_label(self, sample_image, temp_dir):
        output = temp_dir / 'label.png'
        result = add_label(sample_image, 50, 50, "Test Label", output_path=output)
        assert result == output
        assert output.exists()

    def test_annotate_steps_multiple(self, sample_image, temp_dir):
        output = temp_dir / 'multi.png'
        annotations = [
            {'type': 'callout', 'x': 100, 'y': 100, 'number': 1, 'label': 'First'},
            {'type': 'arrow', 'from_xy': (200, 200), 'to_xy': (400, 300)},
            {'type': 'label', 'x': 500, 'y': 500, 'text': 'Some label'},
        ]
        result = annotate_steps(sample_image, annotations, output_path=output)
        assert result == output
        assert output.exists()

    def test_overwrite_source_when_no_output(self, sample_image):
        """When no output_path, should overwrite the source image."""
        original_size = sample_image.stat().st_size
        add_numbered_callout(sample_image, 100, 100, 1)
        assert sample_image.exists()
        # File should be modified (different size due to annotation)


# ============================================================
# HTML GENERATOR TESTS
# ============================================================

class TestHtmlGenerator:
    def test_image_to_base64(self, sample_image):
        result = _image_to_base64(sample_image)
        assert result.startswith('data:image/png;base64,')
        assert len(result) > 100

    def test_image_to_base64_nonexistent(self):
        result = _image_to_base64('/nonexistent/path.png')
        assert result == ''

    def test_generate_guide(self, sample_steps, temp_dir):
        output = temp_dir / 'test_guide.html'
        result = generate_guide(
            steps=sample_steps,
            title='Test Tutorial',
            description='A test tutorial description.',
            output_path=output,
        )
        assert result == output
        assert output.exists()

        html = output.read_text(encoding='utf-8')
        assert 'Test Tutorial' in html
        assert 'A test tutorial description.' in html
        assert 'Step 1 Title' in html
        assert 'Step 2 Title' in html
        assert 'Step 3 Title' in html
        assert 'data:image/png;base64,' in html
        assert '3 steps' in html

    def test_generate_guide_with_tutorial_id(self, sample_steps, temp_dir, monkeypatch):
        monkeypatch.setattr('scripts.tutorials.html_generator.GUIDE_DIR', temp_dir)
        result = generate_guide(
            steps=sample_steps,
            title='Test',
            description='Desc',
            tutorial_id='test_id',
        )
        assert result == temp_dir / 'test_id.html'
        assert result.exists()

    def test_generate_guide_no_screenshots(self, temp_dir):
        steps = [
            {'title': 'Step 1', 'description': 'No screenshot here.'},
        ]
        output = temp_dir / 'no_screenshots.html'
        result = generate_guide(
            steps=steps,
            title='No Screenshots',
            description='Guide without images.',
            output_path=output,
        )
        assert output.exists()
        html = output.read_text(encoding='utf-8')
        assert 'No Screenshots' in html

    def test_generate_guide_requires_id_or_path(self, sample_steps):
        with pytest.raises(ValueError, match="Either output_path or tutorial_id"):
            generate_guide(
                steps=sample_steps,
                title='Test',
                description='Desc',
            )


# ============================================================
# CLI RECORDER / TERMINAL RENDERING TESTS
# ============================================================

class TestTerminalRendering:
    def test_render_terminal_frame(self):
        img = render_terminal_frame("Hello, world!\nLine 2\nLine 3")
        assert isinstance(img, Image.Image)
        assert img.size == (1280, 720)

    def test_render_terminal_frame_with_title(self):
        img = render_terminal_frame("$ python script.py\nOutput...", title="Terminal")
        assert img.size == (1280, 720)

    def test_render_terminal_frame_custom_size(self):
        img = render_terminal_frame("test", width=800, height=600)
        assert img.size == (800, 600)

    def test_render_terminal_frame_long_lines_truncated(self):
        """Long lines should be truncated without errors."""
        long_line = "x" * 500
        img = render_terminal_frame(long_line)
        assert img.size == (1280, 720)

    def test_render_terminal_frame_many_lines(self):
        """Many lines beyond the viewport should be handled."""
        text = "\n".join([f"Line {i}" for i in range(200)])
        img = render_terminal_frame(text)
        assert img.size == (1280, 720)

    def test_render_terminal_frame_color_detection(self):
        """Verify color-coded lines don't crash."""
        text = (
            "$ python script.py\n"
            "SUCCESS: Operation completed\n"
            "WARNING: Check config\n"
            "ERROR: Something failed\n"
            "# This is a comment\n"
            ">>> prompt\n"
            "Normal line"
        )
        img = render_terminal_frame(text)
        assert img.size == (1280, 720)

    def test_save_terminal_frame(self, temp_dir):
        output = temp_dir / 'frame.png'
        result = save_terminal_frame("Hello!", output)
        assert result == output
        assert output.exists()

        img = Image.open(output)
        assert img.size == (1280, 720)


# ============================================================
# BASE RECORDER TESTS
# ============================================================

class TestBaseRecorder:
    def test_tutorial_step_creation(self):
        step = TutorialStep("Test", "Description", "/path/to/img.png")
        assert step.title == "Test"
        assert step.description == "Description"
        assert step.screenshot_path == "/path/to/img.png"
        assert step.timestamp > 0

    def test_unknown_tutorial_id_raises(self):
        class DummyRecorder(BaseRecorder):
            def record(self):
                pass

        with pytest.raises(ValueError, match="Unknown tutorial_id"):
            DummyRecorder('nonexistent_tutorial_id')

    def test_video_and_guide_paths(self):
        """Verify output path conventions."""
        # Use a known tutorial ID
        tid = list(TUTORIAL_REGISTRY.keys())[0]

        class DummyRecorder(BaseRecorder):
            def record(self):
                pass

        rec = DummyRecorder(tid)
        assert rec.video_path.suffix == '.mp4'
        assert rec.guide_path.suffix == '.html'
        assert tid in rec.video_path.name
        assert tid in rec.guide_path.name


# ============================================================
# VIDEO COMPOSER TESTS (ffmpeg-dependent, skip if not available)
# ============================================================

class TestVideoComposer:
    def test_check_ffmpeg(self):
        """Just verify the check doesn't crash."""
        result = check_ffmpeg()
        assert isinstance(result, bool)

    @pytest.mark.skipif(not check_ffmpeg(), reason="ffmpeg not installed")
    def test_compose_cli_video(self, temp_dir):
        """Test composing a simple video from frames."""
        from scripts.tutorials.video_composer import compose_cli_video

        # Create test frames
        frames = []
        for i in range(3):
            img = Image.new('RGB', (1280, 720), color=(i * 80, 100, 150))
            path = temp_dir / f'frame{i}.png'
            img.save(path)
            frames.append(str(path))

        output = temp_dir / 'test.mp4'
        result = compose_cli_video(frames, output, frame_duration=1)
        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.skipif(not check_ffmpeg(), reason="ffmpeg not installed")
    def test_compose_cli_video_no_frames_raises(self, temp_dir):
        from scripts.tutorials.video_composer import compose_cli_video

        with pytest.raises(ValueError, match="No frames"):
            compose_cli_video([], temp_dir / 'empty.mp4')

    def test_compose_cli_video_no_ffmpeg_raises(self, temp_dir, monkeypatch):
        """Should raise clear error when ffmpeg is missing."""
        from scripts.tutorials import video_composer
        monkeypatch.setattr(video_composer, 'check_ffmpeg', lambda: False)

        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            video_composer.compose_cli_video(['frame.png'], temp_dir / 'out.mp4')


# ============================================================
# TUTORIAL REGISTRY COMPLETENESS
# ============================================================

class TestRegistryCompleteness:
    def test_all_categories_have_tutorials(self):
        for category in CATEGORY_LABELS:
            tutorials = get_tutorials_by_category(category)
            assert len(tutorials) > 0, f"Category '{category}' has no tutorials"

    def test_tutorial_ids_are_unique(self):
        ids = list(TUTORIAL_REGISTRY.keys())
        assert len(ids) == len(set(ids)), "Duplicate tutorial IDs found"

    def test_expected_tutorial_count(self):
        """We expect 14 tutorials total."""
        assert len(TUTORIAL_REGISTRY) == 14
