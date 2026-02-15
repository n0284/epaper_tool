from pathlib import Path
from PIL import Image
import numpy as np

from to_bin import convert_to_bin  # 既存

TARGET_W = 240
TARGET_H = 416

palette = np.array([
    [0, 0, 0],
    [255, 255, 255],
    [255, 0, 0],
    [255, 255, 0]
], dtype=np.float32)

def nearest_color(pixel):
    distances = np.sum((palette - pixel) ** 2, axis=1)
    return palette[np.argmin(distances)]

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

    data = np.array(canvas, dtype=np.float32)
    height, width, _ = data.shape

    # 4色ディザリング
    for y in range(height):
        for x in range(width):
            old_pixel = data[y, x].copy()
            new_pixel = nearest_color(old_pixel)
            data[y, x] = new_pixel
            error = old_pixel - new_pixel

            if x + 1 < width:
                data[y, x + 1] += error * 7 / 16
            if y + 1 < height and x - 1 >= 0:
                data[y + 1, x - 1] += error * 3 / 16
            if y + 1 < height:
                data[y + 1, x] += error * 5 / 16
            if y + 1 < height and x + 1 < width:
                data[y + 1, x + 1] += error * 1 / 16

    data = np.clip(data, 0, 255)

    # 中間PNGは一時ファイルにする（bin生成後に削除）
    tmp_png = output_bin.parent / "._tmp_color_dither_fixed.png"
    out = Image.fromarray(data.astype("uint8"))
    out.save(tmp_png)

    # bin生成（出力先は固定名でもOK：image.bin）
    output_bin.parent.mkdir(parents=True, exist_ok=True)
    convert_to_bin(str(tmp_png), str(output_bin))

    # 後片付け
    try:
        tmp_png.unlink()
    except:
        pass
