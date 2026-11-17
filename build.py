# -*- coding: utf-8 -*-
"""打包脚本：生成图标 + PyInstaller 单文件 exe。用法：python build.py"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def make_icon() -> None:
    from PIL import Image, ImageDraw, ImageFont

    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, s - 8, s - 8], radius=56, fill=(42, 49, 69, 255))
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 150)
    except OSError:
        font = ImageFont.load_default()
    text = "译"
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((s - w) / 2 - bbox[0], (s - h) / 2 - bbox[1]), text,
           font=font, fill=(233, 237, 247, 255))
    img.save(HERE / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    print("[icon] icon.ico ok")


def build() -> None:
    make_icon()
    import shutil
    import zipfile
    import glossary
    gj = HERE / "glossary.json"
    if not gj.exists():  # 已有合并词库则保留，勿用内置表覆盖
        glossary.dump_default_json(gj)
    print("[glossary] glossary.json ok")

    # 离线模型：从 .argosmodel 解包（若尚未解包）
    mt_dir = HERE / "offline_models" / "en_zh"
    if not (mt_dir / "model" / "model.bin").exists():
        src = HERE / "offline_models" / "translate-en_zh.argosmodel"
        if not src.exists():
            raise SystemExit(f"缺少离线模型：{src}（可从 HF shethjenil/argostranslate 下载 translate-en_zh.argosmodel）")
        tmp = HERE / "offline_models" / "_tmp"
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        (tmp / "translate-en_zh-1_9").rename(mt_dir)
        shutil.rmtree(tmp, ignore_errors=True)
    print("[offline-mt] en_zh model ok")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole", "--onedir", "-y",
        "--name", "SelectTrans",
        "--icon", str(HERE / "icon.ico"),
        "--distpath", str(HERE / "dist"),
        "--workpath", str(HERE / "build_tmp"),
        "--specpath", str(HERE / "build_tmp"),
        "--add-data", f"{mt_dir};offline_models/en_zh",
        "--exclude-module", "torch",
        "--exclude-module", "spacy",
        "--exclude-module", "stanza",
        "--exclude-module", "argostranslate",
        str(HERE / "main.py"),
    ]
    print("[build]", " ".join(cmd))
    subprocess.run(cmd, check=True)
    out = HERE / "dist" / "SelectTrans" / "SelectTrans.exe"
    shutil.copyfile(gj, HERE / "dist" / "SelectTrans" / "glossary.json")  # exe 旁可编辑
    folder = HERE / "dist" / "SelectTrans"
    total = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    print(f"[build] done -> {folder}  (共 {total / 1e6:.1f} MB)")


if __name__ == "__main__":
    build()
