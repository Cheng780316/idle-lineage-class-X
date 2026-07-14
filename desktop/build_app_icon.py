from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "app-icon-transparent.png"
PNG_OUT = ROOT / "assets" / "app-icon.png"
ICO_OUT = ROOT / "assets" / "app-icon.ico"


def main() -> None:
    image = Image.open(SOURCE).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        raise RuntimeError("Icon source has no visible pixels")

    logo = image.crop(bbox)
    canvas_size = 1024
    padding = 24
    max_side = canvas_size - padding * 2
    scale = min(max_side / logo.width, max_side / logo.height)
    new_size = (
        max(1, round(logo.width * scale)),
        max(1, round(logo.height * scale)),
    )
    logo = logo.resize(new_size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    position = (
        (canvas_size - logo.width) // 2,
        (canvas_size - logo.height) // 2,
    )
    canvas.alpha_composite(logo, position)
    canvas.save(PNG_OUT, "PNG", optimize=True)
    canvas.save(
        ICO_OUT,
        "ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    alpha = canvas.getchannel("A")
    if alpha.getpixel((0, 0)) != 0 or alpha.getpixel((canvas_size - 1, canvas_size - 1)) != 0:
        raise RuntimeError("Icon corners must remain transparent")

    print(f"PNG: {PNG_OUT}")
    print(f"ICO: {ICO_OUT}")
    print(f"Visible bounds: {alpha.getbbox()}")


if __name__ == "__main__":
    main()
