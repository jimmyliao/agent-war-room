#!/usr/bin/env python3
"""Render the checked-in public incident events as a compact terminal GIF."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
EVENTS_PATH = ROOT / "sample-run" / "events.jsonl"
OUTPUT_PATH = ROOT / "sample-run" / "demo.gif"

WIDTH, HEIGHT = 900, 470
BACKGROUND = "#14161a"
FOREGROUND = "#c9d1d9"
MUTED = "#7d8590"
RED = "#ff6b6b"
GREEN = "#56d364"

ICONS = {
    "incident.started": ("🚨", "[!]"),
    "agent.delegated": ("📨", "[>]"),
    "investigation.progress": ("🔎", "[search]"),
    "evidence.found": ("🧾", "[doc]"),
    "review.accepted": ("✅", "[OK]"),
    "review.rejected": ("❌", "[X]"),
    "incident.resolved": ("🏁", "[done]"),
}


def first_existing(paths: list[str]) -> str | None:
    return next((path for path in paths if Path(path).exists()), None)


def load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont | None]:
    text_path = first_existing(
        [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "C:/Windows/Fonts/consola.ttf",
        ]
    )
    if text_path is None:
        raise RuntimeError("No usable terminal/CJK font was found")
    text_font = ImageFont.truetype(text_path, 16)

    emoji_path = first_existing(
        [
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/local/share/fonts/NotoColorEmoji.ttf",
            "/Library/Fonts/Apple Color Emoji.ttc",
            "C:/Windows/Fonts/seguiemj.ttf",
        ]
    )
    if emoji_path is None:
        return text_font, None
    try:
        # Color emoji fonts often expose only fixed bitmap sizes.
        return text_font, ImageFont.truetype(emoji_path, 109)
    except OSError:
        return text_font, None


def read_events() -> list[dict]:
    with EVENTS_PATH.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def fit_summary(draw: ImageDraw.ImageDraw, prefix: str, summary: str, font: ImageFont.FreeTypeFont) -> str:
    summary = summary.replace("\n", " ").strip()
    if len(summary) > 60:
        summary = summary[:59].rstrip() + "…"
    # Leave room for the icon and the terminal's right-hand padding.
    while summary and draw.textlength(prefix + summary, font=font) > WIDTH - 96:
        summary = summary[:-2].rstrip("… ") + "…"
    return summary


def event_color(event_type: str) -> str:
    if event_type == "review.rejected":
        return RED
    if event_type in {"review.accepted", "incident.resolved"}:
        return GREEN
    return FOREGROUND


def render_frame(
    lines: list[tuple[str, str, str]],
    active_chars: int | None,
    text_font: ImageFont.FreeTypeFont,
    emoji_font: ImageFont.FreeTypeFont | None,
) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 14, WIDTH - 16, HEIGHT - 14), radius=12, outline="#30363d", width=2)
    draw.ellipse((35, 31, 47, 43), fill="#ff5f56")
    draw.ellipse((55, 31, 67, 43), fill="#ffbd2e")
    draw.ellipse((75, 31, 87, 43), fill="#27c93f")
    draw.text((108, 28), "agent-war-room · critique loop", font=text_font, fill=MUTED)
    draw.line((34, 57, WIDTH - 34, 57), fill="#30363d", width=1)

    for index, (icon, line, color) in enumerate(lines):
        y = 70 + index * 29
        shown = line if index < len(lines) - 1 or active_chars is None else line[:active_chars]
        if emoji_font is not None:
            # Draw the large fixed-size glyph into a small layer, then scale it down.
            glyph = Image.new("RGBA", (136, 136), (0, 0, 0, 0))
            try:
                ImageDraw.Draw(glyph).text((8, 2), icon, font=emoji_font, embedded_color=True)
                glyph.thumbnail((20, 20), Image.Resampling.LANCZOS)
                image.paste(glyph, (34, y), glyph)
                x = 61
            except (OSError, ValueError):
                draw.text((34, y), icon, font=text_font, fill=color)
                x = 34 + int(draw.textlength(icon + " ", font=text_font))
        else:
            draw.text((34, y), icon, font=text_font, fill=color)
            x = 34 + int(draw.textlength(icon + " ", font=text_font))
        draw.text((x, y), shown, font=text_font, fill=color)
    return image


def main() -> None:
    events = read_events()
    text_font, emoji_font = load_fonts()
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    use_emoji = emoji_font is not None
    lines: list[tuple[str, str, str]] = []
    frames: list[Image.Image] = []
    durations: list[int] = []

    for event in events:
        event_type = event["type"]
        icon = ICONS.get(event_type, ("•", "[*]"))[0 if use_emoji else 1]
        prefix = f"[{event['progress']:>3}%] {event['agent']} · {event_type} · "
        summary = fit_summary(probe, prefix, event["summary"], text_font)
        line = prefix + summary
        color = event_color(event_type)
        lines.append((icon, line, color))

        # A few progressive snapshots per event give a readable typewriter effect
        # without making the GIF unnecessarily large.
        stops = sorted({max(1, len(line) // 3), max(1, len(line) * 2 // 3), len(line)})
        for stop in stops:
            frames.append(render_frame(lines, stop, text_font, emoji_font))
            durations.append(65 if stop != len(line) else 230)

    durations[-1] = 2000
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    print(f"Wrote {OUTPUT_PATH} ({WIDTH}x{HEIGHT}, {len(frames)} frames)")


if __name__ == "__main__":
    main()
