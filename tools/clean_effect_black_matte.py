"""Remove opaque black mattes from selected animated weapon and skill effects.

The extracted client frames were authored additively on black.  Their outer
canvas is transparent, but many visible pixels still contain an opaque black
matte.  Convert the black-composited RGB into straight RGBA without changing
canvas size, frame order, frame duration, or loop behavior.

The conversion is idempotent:

    alpha' = alpha * max(R, G, B) / 255
    rgb'   = rgb * 255 / max(R, G, B)

Compositing rgb'/alpha' over black reproduces the original pixel, while dark
matte pixels become transparent and coloured glow edges remain feathered.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence


ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    *(ROOT / "assets/effects/god-weapons").glob("*.webp"),
    *(
        ROOT / "assets/effects/legend-plus6" / name
        for name in (
            "cronos-fear.webp",
            "emperor-blade.webp",
            "gaia-rage.webp",
            "holycrystal-wand.webp",
            "hyperion-despair.webp",
            "redshadow-dual.webp",
            "titan-rage.webp",
            "windblade.webp",
        )
    ),
    ROOT / "assets/effects/triple-ring-client-original.webp",
    ROOT / "assets/effects/class-skills/skill-ab4327434900.webp",
    ROOT / "assets/effects/class-skills/skill-350d28566596.webp",
    ROOT / "assets/effects/class-skills/skill-657e870c8c26.webp",
    ROOT / "assets/icons/skills/ttmi/屠宰者-透明.webp",
    ROOT / "assets/icons/skills/ttmi/衝擊之暈-透明.webp",
]


def webp_frame_durations(path: Path) -> list[int]:
    """Read 24-bit ANMF durations directly; Pillow does not expose them."""
    data = path.read_bytes()
    durations: list[int] = []
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        payload = offset + 8
        if chunk == b"ANMF" and size >= 16:
            durations.append(int.from_bytes(data[payload + 12 : payload + 15], "little"))
        offset = payload + size + (size & 1)
    return durations


def visible_dark_ratio(frame: Image.Image) -> tuple[int, int]:
    rgba = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[:, :, 3]
    visible = alpha >= 16
    luminance = rgba[:, :, :3].astype(np.uint16).sum(axis=2) / 3
    return int(visible.sum()), int((visible & (luminance < 32)).sum())


def screen_rgb_to_straight_alpha(frame: Image.Image) -> Image.Image:
    rgba = np.asarray(frame.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.float32)
    old_alpha = rgba[:, :, 3].astype(np.float32)
    peak = rgb.max(axis=2)
    non_black = peak > 0

    new_alpha = np.rint(old_alpha * peak / 255.0).clip(0, 255).astype(np.uint8)
    straight = np.zeros_like(rgb, dtype=np.float32)
    straight[non_black] = rgb[non_black] * (255.0 / peak[non_black, None])
    rgba[:, :, :3] = np.rint(straight).clip(0, 255).astype(np.uint8)
    rgba[:, :, 3] = new_alpha

    fully_clear = new_alpha < 2
    rgba[fully_clear] = 0
    return Image.fromarray(rgba, "RGBA")


def clean_animation(path: Path, write: bool) -> dict[str, int | str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    before_durations = webp_frame_durations(path)
    with Image.open(path) as source:
        size = source.size
        loop = int(source.info.get("loop", 0))
        source_frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(source)]

    if len(before_durations) != len(source_frames):
        raise ValueError(f"{path}: duration/frame mismatch")

    visible_before = dark_before = 0
    for frame in source_frames:
        visible, dark = visible_dark_ratio(frame)
        visible_before += visible
        dark_before += dark

    cleaned = [screen_rgb_to_straight_alpha(frame) for frame in source_frames]
    visible_after = dark_after = 0
    for frame in cleaned:
        visible, dark = visible_dark_ratio(frame)
        visible_after += visible
        dark_after += dark

    if write:
        temporary = path.with_name(path.name + ".tmp")
        cleaned[0].save(
            temporary,
            format="WEBP",
            save_all=True,
            append_images=cleaned[1:],
            duration=before_durations,
            loop=loop,
            lossless=True,
            method=6,
            background=(0, 0, 0, 0),
            exact=True,
            kmin=1,
            kmax=1,
        )
        with Image.open(temporary) as check:
            if check.size != size or getattr(check, "n_frames", 1) != len(source_frames):
                temporary.unlink(missing_ok=True)
                raise ValueError(f"{path}: encoded animation geometry changed")
            if check.info.get("background") != (0, 0, 0, 0):
                temporary.unlink(missing_ok=True)
                raise ValueError(f"{path}: encoded canvas is not transparent")
        if webp_frame_durations(temporary) != before_durations:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"{path}: encoded frame timing changed")
        os.replace(temporary, path)

    return {
        "path": path.relative_to(ROOT).as_posix(),
        "frames": len(source_frames),
        "dark_before": dark_before,
        "dark_after": dark_after,
        "visible_before": visible_before,
        "visible_after": visible_after,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="replace target WebPs after validation")
    args = parser.parse_args()

    totals = {"files": 0, "frames": 0, "dark_before": 0, "dark_after": 0}
    for target in TARGETS:
        result = clean_animation(target, args.write)
        totals["files"] += 1
        totals["frames"] += int(result["frames"])
        totals["dark_before"] += int(result["dark_before"])
        totals["dark_after"] += int(result["dark_after"])
        ratio = int(result["dark_before"]) / max(1, int(result["visible_before"]))
        print(
            f"{result['path']}: frames={result['frames']} "
            f"dark={ratio:.2%} -> {result['dark_after']}"
        )
    print(
        f"files={totals['files']} frames={totals['frames']} "
        f"dark_before={totals['dark_before']} dark_after={totals['dark_after']} "
        f"write={args.write}"
    )


if __name__ == "__main__":
    main()
