from pathlib import Path
from PIL import Image
import numpy as np

from to_bin import convert_to_bin  # 既存
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

TARGET_W = 240
TARGET_H = 416

# パレット（float32のままでOK）
PAL_BW = np.array([
    [0, 0, 0],
    [255, 255, 255],
], dtype=np.float32)

PAL_BW_Y = np.array([
    [0,0,0],
    [255,255,255],
    [255,255,0]
], dtype=np.float32)

PAL_FULL = np.array([
    [0, 0, 0],
    [255, 255, 255],
    [255, 0, 0],
    [255, 255, 0],
], dtype=np.float32)

PAL_BW_R = np.array([
    [0, 0, 0],
    [255, 255, 255],
    [255, 0, 0],
], dtype=np.float32)


def nearest_from_palette(pixel: np.ndarray, pal: np.ndarray) -> np.ndarray:
    # pixel: shape (3,)
    # pal: shape (N,3)
    d = np.sum((pal - pixel) ** 2, axis=1)
    return pal[np.argmin(d)]


def is_colorful(pixel: np.ndarray, sat_threshold: float = 45.0) -> bool:
    """
    彩度っぽい指標（max-min）で、色が強い領域だけ赤/黄を許可する。
    人物（肌）は彩度が低めなので、赤/黄の汚れが減る。
    """
    r, g, b = float(pixel[0]), float(pixel[1]), float(pixel[2])
    return (max(r, g, b) - min(r, g, b)) >= sat_threshold

def allow_red(pixel, diff=16):
    r,g,b = pixel
    return (r - max(g,b)) >= diff

def looks_like_skin(pixel):
    r,g,b = pixel
    bright = (r+g+b)/3
    warm = (r > 70 and g > 55 and b < 170 and (r-g) < 90)
    return bright > 55 and warm

def quantize_pixel(pixel, sat_threshold=55, red_diff=28):
    if is_colorful(pixel, sat_threshold):
        if allow_red(pixel, diff=red_diff):
            # 赤を狙うなら黄を混ぜない（赤が黄に負けるのを防ぐ）
            return nearest_from_palette(pixel, PAL_BW_R)
        else:
            return nearest_from_palette(pixel, PAL_BW_Y)
    else:
        if looks_like_skin(pixel):
            return nearest_from_palette(pixel, PAL_BW_Y)
        return nearest_from_palette(pixel, PAL_BW)


def atkinson_diffuse(data: np.ndarray, x: int, y: int, err: np.ndarray) -> None:
    """
    Atkinson dithering:
          x  1  1
       1  1  1
          1
    すべて 1/8。粒が柔らかく人物向き。
    """
    h, w, _ = data.shape
    wgt = 1.0 / 8.0
    for dx, dy in [(1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            data[ny, nx] += err * wgt


def convert_to_epd_bin(input_image: Path, output_bin: Path) -> None:
    input_image = Path(input_image)
    output_bin = Path(output_bin)

    # 画像読み込み
    img = Image.open(input_image).convert("RGB")

    # 横画像だったら回転
    if img.width > img.height:
        img = img.rotate(90, expand=True)

    # アスペクト比維持リサイズ
    img.thumbnail((TARGET_W, TARGET_H), Image.LANCZOS)

    # 白背景キャンバス作成
    canvas = Image.new("RGB", (TARGET_W, TARGET_H), (255, 255, 255))

    # 中央配置
    x_offset = (TARGET_W - img.width) // 2
    y_offset = (TARGET_H - img.height) // 2
    canvas.paste(img, (x_offset, y_offset))

    # --- 前処理：軽いオートコントラスト + ほんの少しシャープ ---
    # cutoff: 黒点/白点の両端を何%捨てるか。小さめが安全（0.5〜2）
    canvas = ImageOps.autocontrast(canvas, cutoff=0.5)

    # 彩度を少し上げる（赤・黄が出やすくなる）
    canvas = ImageEnhance.Color(canvas).enhance(1.25)
    # 1.0 = 元
    # 1.15〜1.35 が安全圏

    # シャープはやりすぎると粒が硬くなるので 1.1〜1.3 くらいが無難
    canvas = ImageEnhance.Sharpness(canvas).enhance(1.1)

    # （任意）ほんの少しだけコントラストを上げたい場合
    canvas = ImageEnhance.Contrast(canvas).enhance(1.05)

    # float32で誤差拡散
    data = np.array(canvas, dtype=np.float32)
    height, width, _ = data.shape

    # Atkinson 4色ディザリング（人物向け）
    for y in range(height):
        for x in range(width):
            old_pixel = data[y, x].copy()

            # 重要：拡散で値がはみ出してるので、量子化前にクリップして安定化
            old_pixel = np.clip(old_pixel, 0, 255)

            new_pixel = quantize_pixel(old_pixel)
            data[y, x] = new_pixel

            err = old_pixel - new_pixel
            atkinson_diffuse(data, x, y, err)

    data = np.clip(data, 0, 255).astype("uint8")

    # 中間PNGは一時ファイルにする（bin生成後に削除）
    tmp_png = output_bin.parent / "._tmp_color_dither_fixed.png"
    Image.fromarray(data).save(tmp_png)

    # bin生成
    output_bin.parent.mkdir(parents=True, exist_ok=True)
    convert_to_bin(str(tmp_png), str(output_bin))

    # 後片付け
    try:
        tmp_png.unlink()
    except:
        pass
