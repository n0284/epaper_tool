from PIL import Image
import numpy as np

WIDTH = 240
HEIGHT = 416

color_map = {
    (0, 0, 0): 0b00,
    (255, 255, 255): 0b01,
    (255, 255, 0): 0b10,
    (255, 0, 0): 0b11
}

def convert_to_bin(input_path, output_path):
    img = Image.open(input_path).convert("RGB")
    data = np.array(img)

    packed_bytes = bytearray()

    for y in range(HEIGHT):
        for x in range(0, WIDTH, 4):
            byte = 0
            for i in range(4):
                pixel = tuple(data[y, x+i])
                val = color_map.get(pixel, 0b01)
                byte |= (val << (6 - 2*i))
            packed_bytes.append(byte)

    with open(output_path, "wb") as f:
        f.write(packed_bytes)

    print("bin generated:", len(packed_bytes))


# 単体実行も可能にしておく
if __name__ == "__main__":
    convert_to_bin("color_dither_fixed.png", "image.bin")
