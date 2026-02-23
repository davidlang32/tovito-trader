"""
Screenshot Annotator
====================

Uses Pillow to add visual annotations to screenshots:
- Numbered callout circles
- Arrows pointing to UI elements
- Text labels with semi-transparent backgrounds
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from scripts.tutorials.config import (
    CALLOUT_COLOR, CALLOUT_FONT_SIZE,
    ARROW_COLOR, LABEL_BG_COLOR, LABEL_FG_COLOR,
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


def add_numbered_callout(image_path, x, y, number, label=None, output_path=None):
    """
    Draw a numbered circle callout at (x, y) on the image.

    Args:
        image_path: Path to source image
        x, y: Center coordinates for the callout circle
        number: Number to display inside the circle
        label: Optional text label displayed near the callout
        output_path: Where to save. If None, overwrites the source.

    Returns:
        Path to the annotated image.
    """
    image_path = Path(image_path)
    output_path = Path(output_path) if output_path else image_path

    img = Image.open(image_path).convert('RGBA')
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    radius = 16
    # Draw filled circle
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius],
        fill=(*CALLOUT_COLOR, 230),
        outline=(255, 255, 255, 255),
        width=2,
    )

    # Draw number text centered in circle
    font = _get_font(CALLOUT_FONT_SIZE)
    text = str(number)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (x - tw // 2, y - th // 2 - 1),
        text,
        fill=(255, 255, 255, 255),
        font=font,
    )

    # Draw label if provided
    if label:
        label_font = _get_font(14)
        lbbox = draw.textbbox((0, 0), label, font=label_font)
        lw, lh = lbbox[2] - lbbox[0], lbbox[3] - lbbox[1]
        label_x = x + radius + 8
        label_y = y - lh // 2

        # Background rectangle
        padding = 4
        draw.rectangle(
            [label_x - padding, label_y - padding,
             label_x + lw + padding, label_y + lh + padding],
            fill=LABEL_BG_COLOR,
        )
        draw.text((label_x, label_y), label, fill=LABEL_FG_COLOR, font=label_font)

    result = Image.alpha_composite(img, overlay)
    result = result.convert('RGB')
    result.save(output_path)
    return output_path


def add_arrow(image_path, from_xy, to_xy, output_path=None, color=None):
    """
    Draw an arrow from from_xy to to_xy on the image.

    Args:
        image_path: Path to source image
        from_xy: (x, y) start point
        to_xy: (x, y) end point (arrowhead)
        output_path: Where to save. If None, overwrites the source.
        color: Arrow color tuple (R, G, B). Defaults to ARROW_COLOR.

    Returns:
        Path to the annotated image.
    """
    import math

    image_path = Path(image_path)
    output_path = Path(output_path) if output_path else image_path
    color = color or ARROW_COLOR

    img = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(img)

    # Draw line
    draw.line([from_xy, to_xy], fill=color, width=3)

    # Draw arrowhead
    angle = math.atan2(to_xy[1] - from_xy[1], to_xy[0] - from_xy[0])
    arrow_len = 12
    arrow_angle = math.pi / 6  # 30 degrees

    p1 = (
        to_xy[0] - arrow_len * math.cos(angle - arrow_angle),
        to_xy[1] - arrow_len * math.sin(angle - arrow_angle),
    )
    p2 = (
        to_xy[0] - arrow_len * math.cos(angle + arrow_angle),
        to_xy[1] - arrow_len * math.sin(angle + arrow_angle),
    )
    draw.polygon([to_xy, p1, p2], fill=color)

    img.save(output_path)
    return output_path


def add_label(image_path, x, y, text, output_path=None):
    """
    Draw a text label with a semi-transparent background at (x, y).

    Args:
        image_path: Path to source image
        x, y: Top-left corner of the label
        text: Label text
        output_path: Where to save. If None, overwrites the source.

    Returns:
        Path to the annotated image.
    """
    image_path = Path(image_path)
    output_path = Path(output_path) if output_path else image_path

    img = Image.open(image_path).convert('RGBA')
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _get_font(14)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    padding = 6
    draw.rectangle(
        [x - padding, y - padding, x + tw + padding, y + th + padding],
        fill=LABEL_BG_COLOR,
    )
    draw.text((x, y), text, fill=LABEL_FG_COLOR, font=font)

    result = Image.alpha_composite(img, overlay)
    result = result.convert('RGB')
    result.save(output_path)
    return output_path


def annotate_steps(image_path, annotations, output_path=None):
    """
    Apply multiple annotations to an image.

    Args:
        image_path: Path to source image
        annotations: List of dicts, each with 'type' key and type-specific params.
            Types: 'callout' (x, y, number, label), 'arrow' (from_xy, to_xy),
                   'label' (x, y, text)
        output_path: Where to save. If None, overwrites the source.

    Returns:
        Path to the annotated image.
    """
    current = Path(image_path)
    target = Path(output_path) if output_path else current

    for ann in annotations:
        ann_type = ann['type']
        if ann_type == 'callout':
            current = add_numbered_callout(
                current, ann['x'], ann['y'], ann['number'],
                label=ann.get('label'), output_path=target,
            )
        elif ann_type == 'arrow':
            current = add_arrow(
                current, ann['from_xy'], ann['to_xy'],
                output_path=target,
            )
        elif ann_type == 'label':
            current = add_label(
                current, ann['x'], ann['y'], ann['text'],
                output_path=target,
            )
        # After first annotation, read from target for subsequent ones
        current = target

    return target
