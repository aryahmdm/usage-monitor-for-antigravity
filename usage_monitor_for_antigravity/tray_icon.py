"""
Tray Icon
==========

Renders the system tray icon.  Font loading and theme detection live in
:mod:`usage_monitor_for_antigravity.platforms`; this module stays purely
about drawing.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .platforms import load_font
from .settings import ICON_DARK, ICON_LIGHT, ICON_STYLE

__all__ = ['create_icon_image', 'create_status_image']

TRANSPARENT = (0, 0, 0, 0)

# Icon canvas and bar geometry (pixels)
ICON_SIZE = 64
BAR_HEIGHT = 9
BAR_GAP = 3
MARKER_WIDTH = 4

# Row height for the 'numbers' icon style - two rows split the canvas evenly.
NUMBER_ROW_HEIGHT = 32


def create_icon_image(
    pct_top: float, pct_bottom: float, light_taskbar: bool = False,
    *, mode_top: str = 'utilization', mode_bottom: str = 'utilization',
    time_pct_top: float | None = None, time_pct_bottom: float | None = None,
    extra_usage_available: bool = False,
) -> Image.Image:
    """Create tray icon: 'A' letter + two usage bars.

    With ``ICON_STYLE`` set to ``'numbers'`` the icon instead shows the two
    utilization percentages as stacked rows without bars; the mode and
    elapsed-time parameters have no effect in that style.
    """
    colors = ICON_DARK if light_taskbar else ICON_LIGHT
    fg, fg_half, fg_warn = colors['fg'], colors['fg_half'], colors['fg_warn']

    S = ICON_SIZE
    img = Image.new('RGBA', (S, S), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    if ICON_STYLE == 'numbers':
        if pct_top >= 100 and pct_bottom >= 100 and not extra_usage_available:
            _draw_centered_text(draw, '\u2715', load_font(36, symbol=True), 2, fg)
        elif pct_top >= 100 and pct_bottom >= 100:
            _draw_centered_text(draw, '$', load_font(42), 2, fg)
        elif pct_top <= 0 and pct_bottom <= 0:
            _draw_centered_text(draw, 'A', load_font(42), 0, fg)
        else:
            _draw_number_row(draw, 0, pct_top, extra_usage_available, fg)
            _draw_number_row(draw, NUMBER_ROW_HEIGHT, pct_bottom, extra_usage_available, fg)
        return img

    stroke_width = 0
    any_exhausted = pct_top >= 100 or pct_bottom >= 100
    if any_exhausted and not extra_usage_available:
        text, font = '\u2715', load_font(36, symbol=True)
        stroke_width = 2
    elif any_exhausted:
        text, font = '$', load_font(42)
        stroke_width = 2
    elif pct_top > 0:
        text, font = f'{min(pct_top, 99):.0f}', load_font(40)
    else:
        text, font = 'A', load_font(42)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    draw.text(((S - tw) / 2 - bbox[0], -bbox[1]), text, fill=fg, font=font, stroke_width=stroke_width, stroke_fill=fg)

    # Progress bars - full width, flush to bottom
    bar2_y = S - BAR_HEIGHT
    bar1_y = bar2_y - BAR_GAP - BAR_HEIGHT

    _draw_usage_bar(draw, bar1_y, pct_top, mode_top, time_pct_top, fg, fg_half, fg_warn)
    _draw_usage_bar(draw, bar2_y, pct_bottom, mode_bottom, time_pct_bottom, fg, fg_half, fg_warn)

    return img


def _draw_centered_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, stroke_width: int, fg: tuple,
        box_top: int = 0, box_height: int = ICON_SIZE) -> None:
    """Draw *text* horizontally centered, vertically centered within the given box."""
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (ICON_SIZE - tw) / 2 - bbox[0]
    y = box_top + (box_height - th) / 2 - bbox[1]
    draw.text((x, y), text, fill=fg, font=font, stroke_width=stroke_width, stroke_fill=fg)


def _draw_number_row(draw: ImageDraw.ImageDraw, row_top: int, pct: float, extra_usage_available: bool, fg: tuple) -> None:
    """Draw one row of the ``'numbers'`` icon style at vertical offset *row_top*."""
    stroke_width = 0
    if pct >= 100 and not extra_usage_available:
        text, font = '\u2715', load_font(34, symbol=True)
        stroke_width = 2
    elif pct >= 100:
        text, font = '$', load_font(32)
        stroke_width = 1
    else:
        text, font = f'{min(pct, 99):.0f}', load_font(40)

    _draw_centered_text(draw, text, font, stroke_width, fg, row_top, NUMBER_ROW_HEIGHT)


def _draw_usage_bar(draw: ImageDraw.ImageDraw, y: int, pct: float, mode: str, time_pct: float | None, fg: tuple, fg_half: tuple, fg_warn: tuple) -> None:
    """Draw one full-width usage bar at vertical offset *y*."""
    draw.rectangle([0, y, ICON_SIZE - 1, y + BAR_HEIGHT - 1], fill=fg_half)

    if mode == 'overage' and time_pct is not None:
        if time_pct >= 100:
            if pct >= 100:
                draw.rectangle([0, y, ICON_SIZE - 1, y + BAR_HEIGHT - 1], fill=fg)
            return

        overage = max(0.0, pct - time_pct)
        fill_ratio = min(1.0, overage / (100 - time_pct))
        fill_w = max(0, int(ICON_SIZE * fill_ratio))
        if fill_w > 0:
            draw.rectangle([0, y, fill_w - 1, y + BAR_HEIGHT - 1], fill=fg)
        return

    fill_w = max(0, min(ICON_SIZE, int(ICON_SIZE * pct / 100)))
    if fill_w > 0:
        warn = mode == 'utilization' and (pct >= 100 or (time_pct is not None and pct > time_pct))
        draw.rectangle([0, y, fill_w - 1, y + BAR_HEIGHT - 1], fill=fg_warn if warn else fg)

    if mode != 'utilization' or time_pct is None:
        return

    marker_x = min(ICON_SIZE - MARKER_WIDTH, max(0, int(ICON_SIZE * time_pct / 100) - MARKER_WIDTH // 2))
    marker_end = marker_x + MARKER_WIDTH - 1
    draw.rectangle([marker_x, y, marker_end, y + BAR_HEIGHT - 1], fill=fg)


def create_status_image(text: str, light_taskbar: bool = False) -> Image.Image:
    """Create monochrome centered-text icon for error/status states."""
    fg_dim = (ICON_DARK if light_taskbar else ICON_LIGHT)['fg_dim']

    S = 64
    img = Image.new('RGBA', (S, S), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    font = load_font(46)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((S - tw) / 2 - bbox[0], (S - th) / 2 - bbox[1]), text, fill=fg_dim, font=font)

    return img
