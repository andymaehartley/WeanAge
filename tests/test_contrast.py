"""Checks the app's colours are readable for people with low contrast sensitivity (WCAG 2)."""

import re
from pathlib import Path

import pytest

WEB = Path(__file__).parents[1] / "src" / "weanage" / "web"


def luminance(hex_colour):
    channels = [int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted([luminance(a), luminance(b)], reverse=True)
    return (high + 0.05) / (low + 0.05)


def theme_tokens(name):
    css = (WEB / "styles.css").read_text()
    block = re.search(rf'\[data-theme="{name}"\] \{{(.*?)\}}', css, re.S).group(1)
    return dict(re.findall(r"--([\w-]+): (#[0-9a-fA-F]{6})", block))


def palette(name):
    js = (WEB / "util.js").read_text()
    block = re.search(rf"{name}: \{{(.*?)\}}", js).group(1)
    return re.findall(r"#[0-9a-fA-F]{6}", block)


@pytest.mark.parametrize("name", ["dark", "light"])
def test_theme_contrast(name):
    t = theme_tokens(name)
    for background in ("bg", "card"):
        for text in ("text", "muted", "accent", "ok", "error", "warn"):
            assert contrast(t[text], t[background]) >= 7, (name, text, background)  # WCAG AAA text
        assert contrast(t["border"], t[background]) >= 3, (name, background)  # WCAG non-text
    assert contrast(t["tbd-ink"], t["tbd-bg"]) >= 7
    assert contrast(t["accent-ink"], t["accent"]) >= 7  # text on filled buttons
    for colour in palette(name):  # model curves
        assert contrast(colour, t["card"]) >= 4.5, (name, colour)
