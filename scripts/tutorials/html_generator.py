"""
HTML Guide Generator
====================

Renders self-contained HTML screenshot guides from tutorial step data
using Jinja2 templates. Screenshots are base64-embedded so each HTML
file is fully standalone.
"""

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from scripts.tutorials.config import TEMPLATES_DIR, GUIDE_DIR


def _image_to_base64(image_path):
    """Read an image file and return its base64-encoded data URI."""
    image_path = Path(image_path)
    if not image_path.exists():
        return ''

    suffix = image_path.suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    mime = mime_types.get(suffix, 'image/png')

    with open(image_path, 'rb') as f:
        encoded = base64.b64encode(f.read()).decode('utf-8')

    return f'data:{mime};base64,{encoded}'


def generate_guide(steps, title, description, output_path=None, tutorial_id=None):
    """
    Generate a self-contained HTML screenshot guide.

    Args:
        steps: List of dicts with keys:
            - title (str): Step title
            - description (str): Step description
            - screenshot_path (str/Path): Path to the screenshot image
        title: Tutorial title (shown in header)
        description: Tutorial description (shown below title)
        output_path: Where to save the HTML file. Defaults to GUIDE_DIR/{tutorial_id}.html
        tutorial_id: Tutorial identifier for default output naming

    Returns:
        Path to the generated HTML file.
    """
    if output_path is None:
        if tutorial_id is None:
            raise ValueError("Either output_path or tutorial_id must be provided")
        output_path = GUIDE_DIR / f'{tutorial_id}.html'

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare step data with embedded images
    rendered_steps = []
    for i, step in enumerate(steps, 1):
        screenshot_data = ''
        if step.get('screenshot_path'):
            screenshot_data = _image_to_base64(step['screenshot_path'])

        rendered_steps.append({
            'number': i,
            'title': step['title'],
            'description': step['description'],
            'screenshot_data': screenshot_data,
        })

    # Render template
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template('guide_template.html')

    html = template.render(
        title=title,
        description=description,
        steps=rendered_steps,
        total_steps=len(rendered_steps),
    )

    output_path.write_text(html, encoding='utf-8')
    return output_path
