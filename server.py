# server.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path
from datetime import datetime
import shutil
import os
import time

from color_dither import convert_to_epd_bin  # 変換関数

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
IN_DIR = BASE_DIR / "inbox"
OUT_DIR = BASE_DIR / "server_files"

IN_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

BIN_NAME = "image.bin"
BIN_PATH = OUT_DIR / BIN_NAME


# =========================
# 画像アップロード → 変換
# =========================
@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="image file only")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # 保存先（衝突しない名前）
    saved_path = IN_DIR / "latest.jpg"

    # 受信して保存
    with saved_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # latest.jpg以外を消す
    for p in IN_DIR.glob("*"):
        if p.name != "latest.jpg":
            p.unlink()

    # bin生成：一旦 temp に出してから置換（安全）
    tmp_bin = OUT_DIR / f".{BIN_NAME}.{ts}.tmp"

    try:
        convert_to_epd_bin(saved_path, tmp_bin)
        os.replace(tmp_bin, BIN_PATH)  # atomic update
    except Exception as e:
        if tmp_bin.exists():
            tmp_bin.unlink()
        raise HTTPException(status_code=500, detail=f"convert failed: {e}")

    return JSONResponse({"ok": True, "bin": BIN_NAME})


# =========================
# ヘルスチェック
# =========================
@app.get("/health")
def health():
    return {"ok": True, "status": "running"}


# =========================
# 最終更新情報（デバッグ用）
# =========================
@app.get("/meta")
def meta():
    if not BIN_PATH.exists():
        return {
            "exists": False,
            "message": "image.bin not generated yet"
        }

    stat = BIN_PATH.stat()
    return {
        "exists": True,
        "filename": BIN_NAME,
        "size_bytes": stat.st_size,
        "last_updated_unix": stat.st_mtime,
        "last_updated_readable": time.ctime(stat.st_mtime)
    }


# =========================
# ESP32用：image.bin を直接配信
# =========================
app.mount(
    "/",
    StaticFiles(directory=OUT_DIR, html=False),
    name="static"
)
