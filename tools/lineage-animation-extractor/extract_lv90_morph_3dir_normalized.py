#!/usr/bin/env python3
"""Export the five Lv.90 morphs on one stable three-direction canvas.

Every action and direction keeps the SPX world origin at the same pixel.  The
browser can therefore anchor the sprite once instead of guessing the feet from
each rendered frame (which is unreliable when a weapon trail reaches below the
actor).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from statistics import median

from PIL import Image


DIRECTIONS = ((2, ""), (0, "F"), (6, "2"))  # target right / above / left


def body_foot(frame, canvas_left: int, canvas_top: int, padding: int) -> tuple[float, float]:
    """Return a stable foot point from the opaque body layer only."""
    image = frame.image.convert("RGBA")
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    if box is None:
        return (frame.x_offset - canvas_left + padding,
                frame.y_offset - canvas_top + padding)
    x0, y0, x1, y1 = box
    visible_height = y1 - y0
    # First find the dense torso centre.  A spear tip or a long sword is thin,
    # so it contributes far less than the body in this middle-height band.
    torso_y0 = y0 + round(visible_height * 0.25)
    torso_y1 = y0 + round(visible_height * 0.68)
    torso_histogram = [0] * image.width
    torso_total = 0
    pixels = alpha.load()
    for y in range(torso_y0, torso_y1):
        for x in range(x0, x1):
            value = pixels[x, y]
            if value <= 96:
                continue
            torso_histogram[x] += value
            torso_total += value
    torso_x = (x0 + x1) / 2
    if torso_total:
        accumulated = 0
        for x, weight in enumerate(torso_histogram):
            accumulated += weight
            if accumulated >= torso_total / 2:
                torso_x = x + 0.5
                break

    # Search for the lowest opaque body pixel only near the torso.  This keeps
    # diagonal polearms, bows and ground-reaching weapon trails out of the foot
    # anchor without imposing a class-specific hand-tuned coordinate.
    radius = max(10, round(visible_height * 0.22))
    search_x0 = max(x0, round(torso_x - radius))
    search_x1 = min(x1, round(torso_x + radius))
    body_bottom = y0
    for y in range(y0 + round(visible_height * 0.55), y1):
        if any(pixels[x, y] > 48 for x in range(search_x0, search_x1)):
            body_bottom = y + 1

    foot_y0 = max(y0, body_bottom - max(3, round(visible_height * 0.08)))
    histogram = [0] * image.width
    total = 0
    for y in range(foot_y0, body_bottom):
        for x in range(search_x0, search_x1):
            value = pixels[x, y]
            if value <= 48:
                continue
            weight = value * value
            histogram[x] += weight
            total += weight
    foot_x = (x0 + x1) / 2
    if total:
        accumulated = 0
        for x, weight in enumerate(histogram):
            accumulated += weight
            if accumulated >= total / 2:
                foot_x = x + 0.5
                break
    return (
        frame.x_offset - canvas_left + padding + foot_x,
        frame.y_offset - canvas_top + padding + body_bottom,
    )


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--spx-module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = load_module(
        "lv90_source",
        Path(__file__).with_name("extract_lv100_morph_drafts_spx.py"),
    )
    spx = load_module("lineage_spx_normalized", args.spx_module)
    archives, inventory = spx.build_index(args.client)
    args.output.mkdir(parents=True, exist_ok=True)
    raw_root = args.output / "_source"
    raw_root.mkdir(exist_ok=True)
    decoded_cache: dict[tuple[int, int], tuple[list, dict]] = {}

    def decode(sprite_id: int, variant: int):
        key = (sprite_id, variant)
        if key in decoded_cache:
            return decoded_cache[key]
        archive_name = f"{sprite_id}-{variant}.spx"
        entries = archives.get(archive_name.lower())
        if not entries:
            raise FileNotFoundError(archive_name)
        raw = raw_root / archive_name
        spx.extract_entry(args.cli, entries[0], raw)
        frames, _mask, _blocks = spx.decode_spx(raw.read_bytes())
        decoded_cache[key] = (
            frames,
            {"archive": entries[0].archive.name, "name": archive_name},
        )
        return decoded_cache[key]

    manifest_morphs: list[dict] = []
    for morph in source.MORPHS:
        records: list[dict] = []
        left = top = None
        right = bottom = None

        for direction, suffix in DIRECTIONS:
            for action, group in morph.groups.items():
                variant = group + direction
                included_effects = morph.effects[:1]
                layer_defs = (
                    ("body", morph.body),
                    *((f"effect{index + 1}", value)
                      for index, value in enumerate(included_effects)),
                )
                layers = []
                for layer_name, sprite_id in layer_defs:
                    frames, source_info = decode(sprite_id, variant)
                    layers.append((layer_name, sprite_id, frames, source_info))
                    for frame in frames:
                        frame_right = frame.x_offset + frame.image.width
                        frame_bottom = frame.y_offset + frame.image.height
                        left = frame.x_offset if left is None else min(left, frame.x_offset)
                        top = frame.y_offset if top is None else min(top, frame.y_offset)
                        right = frame_right if right is None else max(right, frame_right)
                        bottom = frame_bottom if bottom is None else max(bottom, frame_bottom)
                counts = {len(layer[2]) for layer in layers}
                if len(counts) != 1:
                    raise ValueError(
                        f"Layer frame mismatch: {morph.name} {action} d{direction}"
                    )
                records.append({
                    "direction": direction,
                    "suffix": suffix,
                    "action": action,
                    "group": group,
                    "variant": variant,
                    "layers": layers,
                    "frame_count": counts.pop(),
                })

        assert None not in (left, top, right, bottom)
        padding = 8
        width = right - left + padding * 2
        height = bottom - top + padding * 2
        origin_x = -left + padding
        origin_y = -top + padding
        action_manifest = []
        anchors: dict[str, list[float]] = {}

        for record in records:
            game_dir = args.output / f"{morph.name}{record['suffix']}"
            game_dir.mkdir(parents=True, exist_ok=True)
            prefix = record["action"]
            for frame_index in range(record["frame_count"]):
                canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                for layer_name, _sprite_id, frames, _source_info in record["layers"]:
                    frame = frames[frame_index]
                    layer = (source.key_screen_layer(frame.image)
                             if layer_name.startswith("effect") else frame.image)
                    canvas.alpha_composite(
                        layer,
                        (frame.x_offset - left + padding,
                         frame.y_offset - top + padding),
                    )
                canvas.save(game_dir / f"{prefix}_{frame_index}.png")

            if record["action"] == "idle":
                body_frames = record["layers"][0][2]
                feet = [body_foot(frame, left, top, padding) for frame in body_frames]
                face = "R" if record["suffix"] == "" else ("F" if record["suffix"] == "F" else "L")
                anchors[face] = [round(median(value[0] for value in feet), 2),
                                 round(median(value[1] for value in feet), 2)]

            action_manifest.append({
                "direction": record["direction"],
                "folder": f"{morph.name}{record['suffix']}",
                "action": record["action"],
                "variant": record["variant"],
                "frames": record["frame_count"],
                "layers": [
                    {
                        "name": layer_name,
                        "sprite_id": sprite_id,
                        "archive": source_info["archive"],
                    }
                    for layer_name, sprite_id, _frames, source_info in record["layers"]
                ],
            })

        morph_record = {
            "morph_id": morph.morph_id,
            "name": morph.name,
            "role": morph.role,
            "canvas": [width, height],
            "world_bounds": [left, top, right, bottom],
            "origin": [origin_x, origin_y],
            "body_foot_anchors": anchors,
            "directions": {"R": 2, "F": 0, "L": 6},
            "actions": action_manifest,
        }
        (args.output / f"{morph.name}.json").write_text(
            json.dumps(morph_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest_morphs.append(morph_record)
        print(
            f"OK {morph.name}: {width}x{height}, origin=({origin_x},{origin_y})",
            flush=True,
        )

    (args.output / "manifest.json").write_text(
        json.dumps({
            "status": "three-direction-normalized",
            "client": str(args.client),
            "source_policy": "read-only",
            "morphs": manifest_morphs,
            "archive_inventory": inventory,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shutil.rmtree(raw_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
