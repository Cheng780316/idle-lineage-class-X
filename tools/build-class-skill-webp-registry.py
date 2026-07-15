from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageSequence

from clean_effect_black_matte import clean_animation


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "client-animation-extract" / "all-class-skill-effects"
OUTPUT = ROOT / "assets" / "effects" / "class-skills"
REGISTRY = ROOT / "js" / "class-skill-anim.js"

ASSET_VERSION = "20260716-class-vfx-fix1"

TARGET_WORDS = (
    "目標", "命中", "爆發", "落雷", "衝擊", "地面", "傷害", "擊中", "爆裂",
    "落下", "打擊", "攻擊", "斬擊", "雷擊", "隕石", "裂擊", "射擊",
)
CASTER_WORDS = (
    "角色", "施法", "自身", "治療", "光環", "護盾", "強化", "保護", "身軀",
    "發動特效", "本體", "增益",
)
TRAVEL_WORDS = ("起手", "飛行", "投射", "方向")


def animation_label(anim: dict) -> str:
    output = anim.get("outputs", {}).get("webp", "")
    return " ".join(
        str(value or "")
        for value in (
            anim.get("sprite_name"),
            anim.get("action_name"),
            anim.get("prefix"),
            output,
        )
    )


def score_animation(anim: dict, skill_type: str) -> int:
    label = animation_label(anim)
    score = min(30, int(anim.get("frames") or 0))
    directional = bool(anim.get("directional"))
    if directional:
        score -= 80
        if int(anim.get("direction") or 0) != 0:
            score -= 20
    if skill_type == "atk":
        score += sum(45 for word in TARGET_WORDS if word in label)
        score -= sum(55 for word in CASTER_WORDS if word in label)
        score -= sum(45 for word in TRAVEL_WORDS if word in label)
    else:
        score += sum(40 for word in CASTER_WORDS if word in label)
        score -= sum(35 for word in TARGET_WORDS if word in label)
        score -= sum(35 for word in TRAVEL_WORDS if word in label)
    if anim.get("source") == "client_sprite_archive":
        score += 15
    return score


def candidate_from_manifest(manifest_path: Path) -> tuple[str, dict] | None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    skill = str(data.get("skill") or "").strip()
    skill_type = str(data.get("type") or "").strip()
    animations = data.get("animations")
    if not skill or data.get("status") != "extracted" or not isinstance(animations, list):
        return None

    usable: list[dict] = []
    for anim in animations:
        output_value = anim.get("outputs", {}).get("webp")
        if not output_value:
            continue
        source_path = ROOT / Path(output_value.replace("\\", "/"))
        if not source_path.is_file():
            continue
        # 多方向的 assets/fx 已由遊戲現有的方向選擇器精確播放；改成單張 WebP
        # 反而會讓光箭、冰箭等固定朝向，因此這類序列保留現有系統。
        if anim.get("source") == "assets/fx" and len(animations) > 1:
            continue
        if anim.get("directional"):
            continue
        candidate = dict(anim)
        candidate["_source_path"] = source_path
        candidate["_score"] = score_animation(anim, skill_type)
        usable.append(candidate)
    if not usable:
        return None
    best = max(usable, key=lambda item: (item["_score"], int(item.get("frames") or 0)))
    best["_skill_type"] = skill_type
    return skill, best


def visible_focus(path: Path) -> tuple[float, float]:
    """Return the union alpha-content center in normalized canvas coordinates."""
    with Image.open(path) as source:
        width, height = source.size
        left, top, right, bottom = width, height, 0, 0
        for frame in ImageSequence.Iterator(source):
            alpha = frame.convert("RGBA").getchannel("A")
            bbox = alpha.point(lambda value: 255 if value >= 8 else 0).getbbox()
            if not bbox:
                continue
            left = min(left, bbox[0])
            top = min(top, bbox[1])
            right = max(right, bbox[2])
            bottom = max(bottom, bbox[3])
    if right <= left or bottom <= top:
        return 0.5, 0.5
    return (left + right) / (2 * width), (top + bottom) / (2 * height)


def build() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"Missing source folder: {SOURCE}")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    selected: dict[str, dict] = {}
    for manifest_path in sorted(SOURCE.rglob("skill_manifest.json")):
        result = candidate_from_manifest(manifest_path)
        if not result:
            continue
        skill, candidate = result
        previous = selected.get(skill)
        if previous is None or candidate["_score"] > previous["_score"]:
            selected[skill] = candidate

    wanted_names: set[str] = set()
    registry: dict[str, dict] = {}
    for skill in sorted(selected):
        anim = selected[skill]
        source_path: Path = anim["_source_path"]
        digest = hashlib.sha1(str(source_path.relative_to(ROOT)).encode("utf-8")).hexdigest()[:12]
        filename = f"skill-{digest}.webp"
        wanted_names.add(filename)
        output_path = OUTPUT / filename
        shutil.copy2(source_path, output_path)
        # 客戶端技能圖是以黑底加亮方式製作；全部轉為 straight-alpha，
        # 否則 screen 混合仍會留下不透明深黑輪廓或整塊黑底。
        clean_animation(output_path, write=True)
        focus_x, focus_y = visible_focus(output_path)
        canvas = anim.get("canvas") or [128, 128]
        durations = anim.get("durations_ms") or []
        duration = max(120, sum(int(value or 0) for value in durations))
        if duration <= 120:
            duration = max(420, int(anim.get("frames") or 1) * 90)
        registry[skill] = {
            "src": f"assets/effects/class-skills/{filename}?v={ASSET_VERSION}",
            "width": max(1, int(canvas[0] or 1)),
            "height": max(1, int(canvas[1] or 1)),
            "duration": duration,
            "placement": "target" if anim.get("_skill_type") == "atk" else "caster",
            "focusX": round(focus_x, 4),
            "focusY": round(focus_y, 4),
        }

    for old_file in OUTPUT.glob("skill-*.webp"):
        if old_file.name not in wanted_names:
            old_file.unlink()

    payload = json.dumps(registry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    REGISTRY.write_text(
        "// 由 tools/build-class-skill-webp-registry.py 從客戶端抽取結果產生。\n"
        f"// 共 {len(registry)} 個可安全定位的全職業魔法動圖；方向型技能保留逐方向幀系統。\n"
        f"const CLIENT_SKILL_ANIM_FX=Object.freeze({payload});\n",
        encoding="utf-8",
    )
    total_bytes = sum((OUTPUT / name).stat().st_size for name in wanted_names)
    print(f"skills={len(registry)} assets={len(wanted_names)} bytes={total_bytes}")


if __name__ == "__main__":
    build()
