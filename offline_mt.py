# -*- coding: utf-8 -*-
"""轻量离线翻译（en→zh）：直接加载 CTranslate2 模型 + SentencePiece。

刻意不依赖 argostranslate（其新版拖入 torch/spacy/stanza 会把安装包吹到 250MB+）。
断句用简单正则（划词场景多为 1~3 句，足够）。
"""
from __future__ import annotations

import gc
import re
import sys
import threading
import time
from pathlib import Path

_state = {"tr": None, "sp": None, "last_used": 0.0}
_lock = threading.Lock()

IDLE_UNLOAD_S = 300  # 闲置 5 分钟自动卸载

_SPLIT = re.compile(r"(?<=[.!?;。！？；])\s+|\n+")


def model_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "offline_models" / "en_zh"


def available() -> bool:
    return (model_dir() / "model" / "model.bin").exists()


def loaded() -> bool:
    return _state["tr"] is not None


def load() -> bool:
    """惰性加载模型（首次约 1~3 秒），成功返回 True。"""
    with _lock:
        if _state["tr"] is not None:
            return True
        d = model_dir()
        if not (d / "model" / "model.bin").exists():
            return False
        try:
            # 必须在 import numpy/ctranslate2 之前限线程：
            # OpenBLAS 默认按 CPU 核数预分配缓冲，核多的机器私有内存会虚高 700MB+。
            import os
            os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
            os.environ.setdefault("OMP_NUM_THREADS", "4")
            os.environ.setdefault("MKL_NUM_THREADS", "4")
            import ctranslate2
            import sentencepiece as spm
            # 注意：sentencepiece 的 C++ 接口读不了中文路径（窄字符坑），
            # 必须用 Python 读字节再以 model_proto 方式加载。
            proto = (d / "sentencepiece.model").read_bytes()
            _state["sp"] = spm.SentencePieceProcessor(model_proto=proto)
            # 限线程：CT2 默认按 CPU 核数开线程缓冲，核多的机器私有内存会飙到近 1GB。
            # 划词是单句翻译，4 线程足够，省内存。
            _state["tr"] = ctranslate2.Translator(
                str(d / "model"), device="cpu", compute_type="int8",
                inter_threads=1, intra_threads=4)
            return True
        except Exception as e:
            _state["tr"] = _state["sp"] = None
            _state["err"] = f"{type(e).__name__}: {e}"
            return False


def unload() -> None:
    """释放模型内存并压缩工作集。"""
    with _lock:
        if _state["tr"] is None:
            return
        _state["tr"] = None
        _state["sp"] = None
    gc.collect()
    try:
        import ctypes
        ctypes.windll.kernel32.SetProcessWorkingSetSize(
            ctypes.c_void_p(-1), ctypes.c_size_t(-1), ctypes.c_size_t(-1))
    except Exception:
        pass


def maybe_unload_idle(idle_s: float = IDLE_UNLOAD_S) -> None:
    if loaded() and time.time() - _state["last_used"] > idle_s:
        unload()


def _post(s: str) -> str:
    s = s.replace("▁", "")                       # sentencepiece 空格标记残留
    s = re.sub(r"\s+([。，！？；：、）】」》])", r"\1", s)
    s = re.sub(r"([（【「《])\s+", r"\1", s)
    s = re.sub(r"(?<=[一-鿿]),", "，", s)
    s = re.sub(r"(?<=[一-鿿])\?", "？", s)
    s = re.sub(r"(?<=[一-鿿])!", "！", s)
    return s.strip()


def translate_en_zh(text: str) -> str:
    """英文 → 简体中文（离线）。调用前请 ensure；失败抛 RuntimeError。"""
    if not load():
        raise RuntimeError("离线模型缺失")
    _state["last_used"] = time.time()
    sp, tr = _state["sp"], _state["tr"]
    chunks = [c.strip() for c in _SPLIT.split(text) if c.strip()] or [text.strip()]
    outs = []
    for c in chunks:
        toks = sp.encode(c, out_type=str)
        if not toks:
            continue
        res = tr.translate_batch([toks], beam_size=2, max_decoding_length=256)
        outs.append(_post(sp.decode(res[0].hypotheses[0])))
    return _post(" ".join(o for o in outs if o))
