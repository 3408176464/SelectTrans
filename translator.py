# -*- coding: utf-8 -*-
"""翻译引擎：有道 webfanyi（主） + MyMemory（备），中英自动方向。

有道接口为网页版逆向（webtranslate + AES 解密），仅供个人学习使用。
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time

import requests
from Crypto.Cipher import AES

import glossary
import offline_mt

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Referer": "https://fanyi.youdao.com/"})


class TranslateError(Exception):
    pass


def is_chinese(text: str) -> bool:
    return bool(_CJK.search(text))


def detect_direction(text: str):
    """返回 (from, to) 标签用于展示。"""
    return ("中", "EN") if is_chinese(text) else ("EN", "中")


# ---------------------------------------------------------------- 有道 webfanyi
_youdao_state = {"session": None, "secret": None, "aes_key": None, "aes_iv": None, "ts": 0.0}


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _sign(key: str, timestamp: int) -> str:
    return _md5(f"client=fanyideskweb&mysticTime={timestamp}&product=webfanyi&key={key}")


def _base_payload(keyid: str, key: str, timestamp: int, **extra) -> dict:
    payload = {
        "keyid": keyid,
        "mysticTime": str(timestamp),
        "sign": _sign(key, timestamp),
        "client": "fanyideskweb",
        "product": "webfanyi",
        "appVersion": "12.0.0",
        "vendor": "web",
        "keyfrom": "fanyi.web",
        "pointParam": "client,mysticTime,product",
        "yduuid": "abcdefg",
        "mid": "1",
        "screen": "1",
        "model": "1",
        "network": "wifi",
        "abtest": "0",
    }
    payload.update(extra)
    return payload


def _aes_decrypt(cipher_b64: str, key_str: str, iv_str: str) -> dict:
    key = hashlib.md5(key_str.encode("utf-8")).digest()[:16]
    iv = hashlib.md5(iv_str.encode("utf-8")).digest()[:16]
    raw = cipher_b64.encode("utf-8")
    raw += b"=" * (-len(raw) % 4)  # 补齐 base64 padding
    data = base64.urlsafe_b64decode(raw)
    plain = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
    plain = plain[: -plain[-1]]  # 去 PKCS7 填充
    text = plain.decode("utf-8").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 兜底：去掉可能的 JS 风格尾部
        return json.loads(re.sub(r";\s*$", "", text))


def _youdao_bootstrap(force: bool = False) -> None:
    st = _youdao_state
    if st["session"] and st["secret"] and not force and time.time() - st["ts"] < 1500:
        return
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://fanyi.youdao.com/"})
    host_html = s.get("https://fanyi.youdao.com", timeout=3).text
    s.get("https://dict.youdao.com/login/acc/query/accountinfo", timeout=3)
    m = re.search(r"https://shared\.ydstatic\.com/dict/translation-website/[^/]+/js/app\.[^\.]+\.js", host_html)
    if not m:
        raise TranslateError("有道页面结构变化，未找到 JS")
    js_html = s.get(m.group(), timeout=3).text
    mk = re.search(r'decodeKey:"(.*?)",', js_html)
    mi = re.search(r'decodeIv:"(.*?)",', js_html)
    md = re.search(r'="webfanyi-key-getter-2025",(\w+)="(\w+)";', js_html)
    if not (mk and mi and md):
        raise TranslateError("有道 JS 结构变化，未提取到密钥")
    decode_key, decode_iv, default_key = mk.group(1), mi.group(1), md.group(2)
    ts = int(time.time() * 1000)
    params = _base_payload("webfanyi-key-getter-2025", default_key, ts)
    kr = s.get("https://dict.youdao.com/webtranslate/key", params=params, timeout=3)
    kr.raise_for_status()
    keys = kr.json().get("data") or {}
    st.update({
        "session": s,
        "secret": keys.get("secretKey") or default_key,
        "aes_key": keys.get("aesKey") or decode_key,
        "aes_iv": keys.get("aesIv") or decode_iv,
        "ts": time.time(),
    })


def _ec_gloss(data: dict) -> str:
    """从 dictResult.ec 提取词典释义（仅英文单词有效）。"""
    try:
        word = data["dictResult"]["ec"]["word"]
        if isinstance(word, list):
            word = word[0]
        parts = []
        for tr in word.get("trs") or []:
            pos = (tr.get("pos") or "").strip()
            tran = (tr.get("tran") or "").strip()
            if tran:
                parts.append(f"{pos} {tran}".strip())
        return "；".join(parts)
    except Exception:
        return ""


def _trim(s: str, limit: int = 180) -> str:
    return s if len(s) <= limit else s[:limit].rstrip("；, ") + "…"


def translate_youdao(text: str):
    """返回 (译文, 附注)。英文单词优先给词典释义。"""
    _youdao_bootstrap()
    st = _youdao_state
    ts = int(time.time() * 1000)
    form = {"i": text, "from": "auto", "to": "", "dictResult": "true", "useTerm": "false"}
    payload = _base_payload("webfanyi", st["secret"], ts, **form)
    r = st["session"].post("https://dict.youdao.com/webtranslate", data=payload, timeout=3)
    r.raise_for_status()
    try:
        data = _aes_decrypt(r.text, st["aes_key"], st["aes_iv"])
    except Exception:
        # 未加密的错误响应（如风控/参数失效），重试一次后抛出
        _youdao_bootstrap(force=True)
        st = _youdao_state
        ts = int(time.time() * 1000)
        payload = _base_payload("webfanyi", st["secret"], ts, **form)
        r = st["session"].post("https://dict.youdao.com/webtranslate", data=payload, timeout=3)
        r.raise_for_status()
        try:
            data = _aes_decrypt(r.text, st["aes_key"], st["aes_iv"])
        except Exception:
            raise TranslateError(f"有道返回无法解密: {r.text[:80]}")
    parts = []
    for seg in data.get("translateResult") or []:
        for it in seg:
            if isinstance(it, dict) and it.get("tgt"):
                parts.append(it["tgt"])
    out = "".join(parts)
    gloss = _ec_gloss(data)
    single = len(text.split()) == 1 and len(text) <= 24
    if single and gloss and not is_chinese(text):
        return _trim(gloss), "词典释义"
    if not out:
        raise TranslateError("有道未返回译文")
    return out, ""


# ---------------------------------------------------------------- MyMemory
def translate_mymemory(text: str):
    """返回 (译文, 附注)。"""
    pair = "zh|en" if is_chinese(text) else "en|zh"
    r = _session.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text[:480], "langpair": pair},
        timeout=3,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("responseStatus") != 200:
        raise TranslateError(f"MyMemory: {data.get('responseDetails') or data.get('responseStatus')}")
    out = (data.get("responseData") or {}).get("translatedText", "")
    if not out:
        raise TranslateError("MyMemory 未返回译文")
    return out, ""


def translate_offline(text: str):
    """离线兜底（仅英译中）。返回 (译文, 附注)。"""
    if is_chinese(text):
        raise TranslateError("离线模型仅支持英译中")
    try:
        return offline_mt.translate_en_zh(text), "离线翻译（本地模型）"
    except RuntimeError as e:
        raise TranslateError(str(e))


ENGINES = (
    ("有道", translate_youdao),
    ("MyMemory", translate_mymemory),
    ("离线", translate_offline),
)

MAX_LEN = 2000

# 网络保险丝：在线引擎出现网络故障后 45 秒内直接走离线，
# 避免「半死不活」的网络每次都让两个在线引擎各超时一遍（体感 5 秒+）。
_NET = {"down_until": 0.0}
NET_COOLDOWN_S = 45.0


def _net_dead() -> bool:
    return time.time() < _NET["down_until"]


def _net_down() -> None:
    _NET["down_until"] = time.time() + NET_COOLDOWN_S


def _net_ok() -> None:
    _NET["down_until"] = 0.0


def translate(text: str):
    """翻译文本，返回 (译文, 引擎名, 附注)。

    顺序：术语词库 → 有道（单词走词典释义）→ MyMemory。
    全部引擎失败抛 TranslateError。
    """
    text = (text or "").strip()
    if not text:
        raise TranslateError("文本为空")
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN]

    g = glossary.lookup(text)
    if g and len(text.split()) > 1:
        # 多词短语：术语词库优先（机器翻译常译不准术语）
        return g, "术语词库", "来自术语词库 · glossary.json 可自行扩充"

    errors = []
    net_fail = 0
    attempted = 0
    for name, fn in ENGINES:
        if name != "离线" and _net_dead():
            continue  # 保险丝生效：跳过在线引擎
        attempted += 1
        try:
            dst, note = fn(text)
            if name != "离线":
                # 在线成功 → 本地模型立即卸载（联网即卸载策略）
                offline_mt.unload()
                _net_ok()
            if g and " ".join(dst.split()).casefold() == " ".join(text.split()).casefold():
                # 单词引擎原样返回 → 词库兜底（noconsole 这类）
                return g, "术语词库", "来自术语词库 · glossary.json 可自行扩充"
            return dst, name, note
        except TranslateError as e:
            errors.append(f"{name}: {e}")
        except (requests.ConnectionError, requests.Timeout, OSError) as e:
            net_fail += 1
            errors.append(f"{name}: 网络不可用")
            if name != "离线":
                _net_down()  # 网络挂了，后面的在线引擎不必再试
        except Exception as e:  # 其他异常
            errors.append(f"{name}: {type(e).__name__}: {e}")
    if net_fail and net_fail == attempted:
        raise TranslateError("离线中：整句翻译需联网，术语短语可查本地词库")
    raise TranslateError("；".join(errors))
