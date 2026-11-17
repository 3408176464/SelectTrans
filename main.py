# -*- coding: utf-8 -*-
"""划词翻译 —— 选中文字自动弹出翻译（类似有道划词）。

热键：
  Ctrl+Alt+Y  手动翻译当前选中
  Ctrl+Alt+S  开/关 自动划词
  Ctrl+Alt+Q  退出
"""
from __future__ import annotations

import argparse
import ctypes
import gc
import json
import os
import queue
import sys
import tempfile
import threading
import time
import traceback
import winreg
from pathlib import Path

import pyperclip
from pynput import keyboard, mouse
from PySide6.QtCore import QLockFile, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from popup import TranslatePopup
from translator import TranslateError, detect_direction, translate

HOTKEY_MANUAL = "<ctrl>+<alt>+y"
HOTKEY_TOGGLE = "<ctrl>+<alt>+s"
HOTKEY_QUIT = "<ctrl>+<alt>+q"

DRAG_PX = 6          # 超过该像素位移视为拖选
DOUBLE_CLICK_S = 0.45  # 双击/三击选词判定
DEBOUNCE_S = 0.35
MAX_TEXT = 2000
POLL_MS = 100        # 事件泵频率（够用且省 CPU）


def trim_working_set() -> None:
    """把不活跃页换出，压低任务管理器可见的工作集。"""
    try:
        ctypes.windll.kernel32.SetProcessWorkingSetSize(
            ctypes.c_void_p(-1), ctypes.c_size_t(-1), ctypes.c_size_t(-1))
    except Exception:
        pass


def to_logical(x: int, y: int) -> tuple[int, int]:
    """pynput 给物理像素，Qt 是逻辑坐标；高 DPI 下必须换算（否则点击判定/弹窗位置全偏）。"""
    app = QApplication.instance()
    if app is None:
        return x, y
    for s in app.screens():
        dpr = s.devicePixelRatio() or 1.0
        lx, ly = x / dpr, y / dpr
        if s.geometry().contains(int(lx), int(ly)):
            return int(round(lx)), int(round(ly))
    dpr = app.primaryScreen().devicePixelRatio() or 1.0
    return int(round(x / dpr)), int(round(y / dpr))

APP_NAME = "SelectTrans"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


# ---------------- 配置 / 开机自启 ----------------
def config_path() -> Path:
    d = Path(os.environ.get("APPDATA", tempfile.gettempdir())) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d / "config.json"


def load_config() -> dict:
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    try:
        config_path().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def launch_cmd() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    py = sys.executable
    if py.lower().endswith("python.exe"):
        cand = py[:-10] + "pythonw.exe"
        if os.path.exists(cand):
            py = cand
    return f'"{py}" "{os.path.abspath(sys.argv[0])}"'


def autostart_enabled() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE)
        winreg.QueryValueEx(k, APP_NAME)
        return True
    except OSError:
        return False


def autostart_set(on: bool) -> None:
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
    if on:
        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, launch_cmd())
    else:
        try:
            winreg.DeleteValue(k, APP_NAME)
        except OSError:
            pass


def init_autostart() -> bool:
    """首次运行默认开启自启；之后尊重用户开关，exe 移动时刷新路径。返回当前是否开启。"""
    cfg = load_config()
    if "autostart" not in cfg:
        cfg["autostart"] = True
        save_config(cfg)
    if cfg.get("autostart"):
        autostart_set(True)
    return bool(cfg.get("autostart"))


# ---------------- 托盘图标 ----------------
def tray_icon() -> QIcon:
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#2A3145"))
    p.drawRoundedRect(2, 2, size - 4, size - 4, 14, 14)
    f = QFont("Microsoft YaHei UI", 34)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#E9EDF7"))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "译")
    p.end()
    return QIcon(pm)


def grab_selection() -> str:
    """模拟 Ctrl+C 取当前选中文字，并还原原剪贴板。"""
    try:
        old = pyperclip.paste()
        old_valid = True
    except Exception:
        old, old_valid = "", False
    if old_valid:
        try:
            pyperclip.copy("WB_SEL_MARKER")  # 占位，便于判断复制是否生效
        except Exception:
            return ""
    ctrl = keyboard.Controller()
    with ctrl.pressed(keyboard.Key.ctrl):
        ctrl.tap("c")
    time.sleep(0.18)
    try:
        text = pyperclip.paste() or ""
    except Exception:
        text = ""
    if old_valid:
        try:
            pyperclip.copy(old)  # 还原剪贴板
        except Exception:
            pass
    if not old_valid:
        # 原剪贴板非文本（如图片）：能读到文本即认为复制成功
        return text.strip()[:MAX_TEXT]
    if not text or text.strip() == "WB_SEL_MARKER":
        return ""
    return text.strip()[:MAX_TEXT]


class App:
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.popup = TranslatePopup()
        self.auto = True
        self.busy = False
        self.last_text = ""
        self._press_pos = None
        self._press_time = 0.0
        self._last_release = None
        self._last_trigger = 0.0

        self._lock = QLockFile(os.path.join(tempfile.gettempdir(), "select_trans.lock"))
        self._build_tray()

    def _build_tray(self):
        menu = QMenu()
        self.act_auto = QAction("自动划词", menu)
        self.act_auto.setCheckable(True)
        self.act_auto.setChecked(True)
        self.act_boot = QAction("开机自启动", menu)
        self.act_boot.setCheckable(True)
        act_quit = QAction("退出", menu)
        menu.addAction(self.act_auto)
        menu.addAction(self.act_boot)
        menu.addSeparator()
        menu.addAction(act_quit)

        self.tray = QSystemTrayIcon(tray_icon(), self.popup.app)
        self.tray.setToolTip("划词翻译 — 选中文字即翻译")
        self.tray.setContextMenu(menu)

        self.act_auto.triggered.connect(lambda checked: self.set_auto(checked))
        self.act_boot.triggered.connect(self._on_boot_toggle)
        act_quit.triggered.connect(self.quit_app)
        menu.aboutToShow.connect(self._sync_tray)

    def _sync_tray(self):
        self.act_auto.setChecked(self.auto)
        self.act_boot.setChecked(autostart_enabled())

    def _on_boot_toggle(self, checked: bool):
        cfg = load_config()
        cfg["autostart"] = bool(checked)
        save_config(cfg)
        autostart_set(bool(checked))

    # ---------------- 鼠标事件（监听线程） ----------------
    def on_click(self, x, y, button, pressed):
        if button != mouse.Button.left:
            return
        x, y = to_logical(x, y)
        if pressed:
            self._press_pos = (x, y)
            self._press_time = time.time()
            self.q.put(("outside", x, y))
            return
        if not self._press_pos:
            return
        px, py = self._press_pos
        self._press_pos = None
        moved = ((x - px) ** 2 + (y - py) ** 2) ** 0.5 > DRAG_PX
        held = time.time() - self._press_time > 0.04

        triggered = False
        if moved and held:
            triggered = True
            self._last_release = None
        else:
            # 双击/三击选词：短时间、近距离的两次松开
            now = time.time()
            if self._last_release:
                lt, (lx, ly) = self._last_release
                if now - lt < DOUBLE_CLICK_S and ((x - lx) ** 2 + (y - ly) ** 2) ** 0.5 < DRAG_PX:
                    triggered = True
                    self._last_release = None
                else:
                    self._last_release = (now, (x, y))
            else:
                self._last_release = (now, (x, y))
        if triggered:
            self.q.put(("select", x, y))

    # ---------------- 主线程事件分发 ----------------
    def poll(self):
        try:
            while True:
                kind, *args = self.q.get_nowait()
                self._handle(kind, *args)
        except queue.Empty:
            pass
        self._ticks = getattr(self, "_ticks", 0) + 1
        if self._ticks == 30 or self._ticks % 600 == 0:  # 启动 3s 后 + 每分钟
            trim_working_set()
            try:
                import offline_mt
                offline_mt.maybe_unload_idle()  # 离线模型闲置 5 分钟自动卸载
            except Exception:
                pass
        self.popup.after(POLL_MS, self.poll)

    def _handle(self, kind, *args):
        if kind == "outside":
            x, y = args
            if self.popup.visible and not self.popup.contains(x, y):
                self.popup.hide()
                trim_working_set()
        elif kind == "select":
            self.request_translate(*args)
        elif kind == "loading":
            self.popup.show_loading(*args)
        elif kind == "show":
            self.popup.show(*args)
        elif kind == "sync_auto":
            self.act_auto.setChecked(self.auto)
        elif kind == "quit":
            self.tray.hide()
            self.popup.destroy()

    # ---------------- 翻译流程 ----------------
    def request_translate(self, x, y, force=False):
        if self.busy:
            return
        now = time.time()
        if not force and now - self._last_trigger < DEBOUNCE_S:
            return
        self._last_trigger = now
        threading.Thread(target=self._worker, args=(x, y), daemon=True).start()

    def _worker(self, x, y):
        self.busy = True
        try:
            text = grab_selection()
            if not text:
                return
            if text == self.last_text and self.popup.visible:
                return
            self.last_text = text
            direction = detect_direction(text)
            self.q.put(("loading", text, x, y, direction))
            try:
                dst, engine, note = translate(text)
            except TranslateError as e:
                self.q.put(("show", text, f"翻译失败：{e}", "—", x, y, direction, ""))
                return
            self.q.put(("show", text, dst, engine, x, y, direction, note))
        finally:
            self.busy = False

    def set_auto(self, on: bool):
        self.auto = bool(on)
        self.act_auto.setChecked(self.auto)
        print(f"[划词翻译] 自动划词：{'开' if self.auto else '关'}")

    def toggle_auto(self):
        self.set_auto(not self.auto)
        self.q.put(("sync_auto",))

    def quit_app(self):
        print("[划词翻译] 退出")
        try:
            self.mouse_listener.stop()
            self.hotkeys.stop()
        except Exception:
            pass
        self.q.put(("quit",))

    # ---------------- 启动 ----------------
    def start(self):
        if not self._lock.tryLock(0):
            print("[划词翻译] 已有实例在运行")
            self.popup.app.quit()
            return
        boot_on = init_autostart()
        self.act_boot.setChecked(boot_on)
        self.tray.show()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.showMessage("划词翻译", "已最小化到托盘，选中文字即翻译", QSystemTrayIcon.MessageIcon.Information, 3000)

        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.mouse_listener.start()

        def _manual():
            self.request_translate(*to_logical(*mouse.Controller().position), force=True)

        self.hotkeys = keyboard.GlobalHotKeys({
            HOTKEY_MANUAL: _manual,
            HOTKEY_TOGGLE: self.toggle_auto,
            HOTKEY_QUIT: self.quit_app,
        })
        self.hotkeys.start()
        self.poll()
        print("[划词翻译] 已启动（托盘常驻）")
        print("  选中任意文字（拖选/双击）→ 自动弹出翻译")
        print(f"  {HOTKEY_MANUAL} 手动翻译   {HOTKEY_TOGGLE} 自动开关   {HOTKEY_QUIT} 退出")
        self.popup.run()
        self.tray.hide()
        self._lock.unlock()


def selftest():
    print("[1/3] 翻译引擎测试…")
    dst, engine, note = translate("Hello, how are you?")
    print(f"  EN→中 [{engine}]: {dst}")
    dst2, engine2, _ = translate("今天天气不错，我们出去走走吧。")
    print(f"  中→EN [{engine2}]: {dst2}")
    print("[2/3] 弹窗预览 6 秒…")
    app = App()
    app.popup.show("Hello, how are you?", dst, engine, 240, 200, ("EN", "中"))
    app.popup.after(6000, app.popup.destroy)
    app.popup.run()
    print("[3/3] 自检完成 ✓")


def _install_crash_log():
    def hook(t, v, tb):
        try:
            with open(os.path.join(tempfile.gettempdir(), "select_trans_error.log"),
                      "a", encoding="utf-8") as f:
                f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                traceback.print_exception(t, v, tb, file=f)
        except Exception:
            pass
        sys.__excepthook__(t, v, tb)
    sys.excepthook = hook


def main():
    _install_crash_log()
    gc.collect()
    gc.freeze()  # 冻结启动期对象，降低 GC 扫描成本
    ap = argparse.ArgumentParser(description="划词翻译")
    ap.add_argument("--test", action="store_true", help="自检（翻译引擎 + 弹窗预览）后退出")
    args = ap.parse_args()
    if args.test:
        selftest()
    else:
        App().start()


if __name__ == "__main__":
    sys.exit(main())
