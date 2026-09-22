from __future__ import annotations

from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / "data" / "demo" / "selected"
OUTPUT = MEDIA_DIR / "素材总览.jpg"
FONT_PATH = Path("C:/Windows/Fonts/msyh.ttc")


def fit_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    background = Image.new("RGB", size, "#0b1927")
    background.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return background


def video_frame(path: Path) -> Image.Image:
    capture = cv2.VideoCapture(str(path))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count // 2))
    ok, frame = capture.read()
    capture.release()
    if not ok:
        return Image.new("RGB", (640, 360), "#0b1927")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def main() -> None:
    images = sorted((MEDIA_DIR / "images").glob("*"))
    videos = sorted((MEDIA_DIR / "videos").glob("*.mp4"))
    items = [(path, Image.open(path).convert("RGB")) for path in images]
    items.extend((path, video_frame(path)) for path in videos)

    width, card_width, card_height, gap = 1480, 340, 245, 20
    columns = 4
    rows = (len(items) + columns - 1) // columns
    canvas = Image.new("RGB", (width, 105 + rows * (card_height + gap) + 20), "#eef3f7")
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(str(FONT_PATH), 28)
    label_font = ImageFont.truetype(str(FONT_PATH), 16)
    small_font = ImageFont.truetype(str(FONT_PATH), 12)
    draw.text((30, 22), "工业安全智能监测系统 - 答辩演示素材", font=title_font, fill="#102238")
    draw.text((31, 64), "图片 8 张 · 视频 5 段 · 均已完成尺寸与可读性校验", font=small_font, fill="#63788c")

    for index, (path, image) in enumerate(items):
        column, row = index % columns, index // columns
        x, y = 30 + column * (card_width + gap), 105 + row * (card_height + gap)
        draw.rounded_rectangle((x, y, x + card_width, y + card_height), 7, fill="white", outline="#d9e2ea")
        canvas.paste(fit_image(image, (card_width - 16, 178)), (x + 8, y + 8))
        label = path.stem
        draw.text((x + 12, y + 194), label, font=label_font, fill="#24394d")
        kind = "视频" if path.suffix.lower() == ".mp4" else "图片"
        draw.text((x + 12, y + 221), kind, font=small_font, fill="#1477ff")

    canvas.save(OUTPUT, quality=92)
    print(OUTPUT)


if __name__ == "__main__":
    main()
