# -*- coding: utf-8 -*-
"""无边框置顶翻译卡片（Qt 自绘：圆角、阴影、渐入动效）。"""
from __future__ import annotations

import sys

import pyperclip
from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QApplication, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
                               QWidget)

FONT = "Microsoft YaHei UI"

C_BG_TOP = QColor("#252A38")
C_BG_BOT = QColor("#181B25")
C_BORDER = QColor(255, 255, 255, 18)
C_ACCENT = QColor("#7FB0FF")
C_TEXT = QColor("#E9EDF7")
C_SUB = QColor("#8B93A8")
C_MUTED = QColor("#6C7488")
C_HAIR = QColor(255, 255, 255, 16)
C_PILL = QColor(255, 255, 255, 20)
C_PILL_HOVER = QColor(255, 255, 255, 38)
C_PILL_PRESS = QColor(255, 255, 255, 10)
C_ERR = QColor("#F09080")
C_DOT = QColor("#7FB0FF")
C_HINT = QColor("#5E667A")

CARD_W = 384
MIN_INNER = 190       # 卡片内容区最小宽度
PAD = 16          # 卡片内边距（左右）
SHADOW = 26       # 阴影留白


def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(FONT, size)
    f.setWeight(weight)
    return f


class PillButton(QWidget):
    clicked = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self._hover = False
        self._press = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(_font(9, QFont.Weight.DemiBold))
        w = self.fontMetrics().horizontalAdvance(text) + 34
        self.setFixedSize(max(w, 96), 32)

    def enterEvent(self, _e):
        self._hover = True
        self.update()

    def leaveEvent(self, _e):
        self._hover = self._press = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = True
            self.update()

    def mouseReleaseEvent(self, e):
        if self._press and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        self._press = False
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = C_PILL_PRESS if self._press else (C_PILL_HOVER if self._hover else C_PILL)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 11, 11)
        p.setFont(self.font())
        p.setPen(C_TEXT)
        p.drawText(r.toRect(), Qt.AlignmentFlag.AlignCenter, self._text)


class CloseButton(QLabel):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("✕", parent)
        self.setFont(_font(11))
        self.setStyleSheet("color: #7A8299; background: transparent;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(24, 24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def enterEvent(self, _e):
        self.setStyleSheet("color: #FF8B7B; background: transparent;")

    def leaveEvent(self, _e):
        self.setStyleSheet("color: #7A8299; background: transparent;")

    def mouseReleaseEvent(self, e):
        if self.rect().contains(e.position().toPoint()):
            self.clicked.emit()


class CardWindow(QWidget):
    """整卡窗口：透明底 + 阴影 + 圆角渐变卡片。"""

    def __init__(self):
        super().__init__(None, (Qt.WindowType.FramelessWindowHint
                                | Qt.WindowType.WindowStaysOnTopHint
                                | Qt.WindowType.Tool))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(CARD_W + SHADOW * 2)

        self._drag_offset = None

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 118))

        self.card = QWidget()
        self.card.setObjectName("card")
        self.card.setGraphicsEffect(shadow)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(SHADOW, SHADOW, SHADOW, SHADOW)
        lay.addWidget(self.card)

        # ---- 内容 ----
        body = QVBoxLayout(self.card)
        body.setContentsMargins(PAD, 15, PAD, 14)
        body.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self._head_lay = head
        self.dir_lbl = QLabel("EN → 中")
        self.dir_lbl.setFont(_font(10.5, QFont.Weight.DemiBold))
        self.dir_lbl.setStyleSheet(f"color: {C_ACCENT.name()}; background: transparent;")
        self.dot = QLabel("●")
        self.dot.setFont(_font(7))
        self.dot.setStyleSheet(f"color: {C_DOT.name()}; background: transparent;")
        self.close_btn = CloseButton()
        head.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(self.dir_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch(1)
        head.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        body.addLayout(head)

        self.src_lbl = QLabel("")
        self.src_lbl.setFont(_font(10))
        self.src_lbl.setStyleSheet(f"color: {C_SUB.name()}; background: transparent;")
        self.src_lbl.setWordWrap(True)
        self.src_lbl.setFixedWidth(CARD_W - PAD * 2)
        body.addWidget(self.src_lbl)

        hair = QWidget()
        hair.setFixedHeight(1)
        hair.setStyleSheet(f"background: rgba(255,255,255,10); border: none;")
        body.addWidget(hair)

        self.dst_lbl = QLabel("")
        self.dst_lbl.setFont(_font(13, QFont.Weight.Medium))
        self.dst_lbl.setStyleSheet(f"color: {C_TEXT.name()}; background: transparent;")
        self.dst_lbl.setWordWrap(True)
        self.dst_lbl.setFixedWidth(CARD_W - PAD * 2)
        body.addWidget(self.dst_lbl)

        self.note_lbl = QLabel("")
        self.note_lbl.setFont(_font(9.5))
        self.note_lbl.setStyleSheet(f"color: {C_MUTED.name()}; background: transparent;")
        self.note_lbl.setWordWrap(True)
        self.note_lbl.setFixedWidth(CARD_W - PAD * 2)
        self.note_lbl.hide()
        body.addWidget(self.note_lbl)

        foot = QHBoxLayout()
        foot.setContentsMargins(0, 4, 0, 0)
        self._foot_lay = foot
        self.copy_btn = PillButton("复制译文")
        self.hint_lbl = QLabel("点外部关闭")
        self.hint_lbl.setFont(_font(8.5))
        self.hint_lbl.setStyleSheet(f"color: {C_HINT.name()}; background: transparent;")
        foot.addWidget(self.copy_btn)
        foot.addStretch(1)
        foot.addWidget(self.hint_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        body.addLayout(foot)

        self.copy_btn.clicked.connect(self._copy)
        self.close_btn.clicked.connect(self.hide)

        self._dots = 0
        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(260)
        self._dot_timer.timeout.connect(self._tick_dots)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(130)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ---------- 绘制 ----------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.card.geometry()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        g.setColorAt(0.0, C_BG_TOP)
        g.setColorAt(1.0, C_BG_BOT)
        p.fillPath(path, g)
        p.setPen(QPen(C_BORDER, 1))
        p.drawPath(path)

    # ---------- 拖拽 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _e):
        self._drag_offset = None

    # ---------- 内容 ----------
    def _copy(self):
        if self.dst_lbl.text():
            pyperclip.copy(self.dst_lbl.text())
            self.hint_lbl.setText("已复制")
            QTimer.singleShot(1200, lambda: self.hint_lbl.setText("点外部关闭"))

    def _tick_dots(self):
        self._dots = (self._dots + 1) % 4
        self.dst_lbl.setText("翻译中" + "·" * self._dots)

    @staticmethod
    def _text_w(text: str, font: QFont) -> int:
        if not text:
            return 0
        fm = QFontMetrics(font)
        return max(fm.horizontalAdvance(line) for line in text.splitlines())

    def _fit(self):
        """按内容自适应宽高：短句收窄，长文封顶换行。"""
        src = self.src_lbl.text()
        dst_on = self.dst_lbl.isVisibleTo(self.card)
        note_on = self.note_lbl.isVisibleTo(self.card)

        inner = max(
            MIN_INNER,
            self._text_w(src, self.src_lbl.font()),
            self._text_w(self.dst_lbl.text(), self.dst_lbl.font()) if dst_on else 0,
            self._text_w(self.note_lbl.text(), self.note_lbl.font()) if note_on else 0,
            self.dir_lbl.fontMetrics().horizontalAdvance(self.dir_lbl.text()) + 70,
            self.copy_btn.width()
            + self.hint_lbl.fontMetrics().horizontalAdvance(self.hint_lbl.text()) + 28,
        )
        inner = min(int(inner), CARD_W - PAD * 2)

        self.src_lbl.setFixedWidth(inner)
        self.dst_lbl.setFixedWidth(inner)
        self.note_lbl.setFixedWidth(inner)

        gaps = 8
        h = 15 + 14  # 卡片上下内边距
        h += self._head_lay.sizeHint().height()
        h += self.src_lbl.heightForWidth(inner) if src else 0
        h += 1  # 发丝线
        if dst_on:
            h += self.dst_lbl.heightForWidth(inner)
        if note_on:
            h += self.note_lbl.heightForWidth(inner)
        h += self._foot_lay.sizeHint().height()
        h += 4 * gaps  # 5 个条目之间的间距
        self.setFixedSize(inner + PAD * 2 + SHADOW * 2, int(h) + SHADOW * 2)

    def _place(self, x: int, y: int):
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        w, h = self.width(), self.height()
        px = max(area.left() + 4, min(x + 14, area.right() - w - 6))
        py = max(area.top() + 4, min(y + 14, area.bottom() - h - 6))
        self.move(px, py)

    def _paint_src(self, src: str):
        text = " ".join(src.split())
        self.src_lbl.setText(text if len(text) <= 110 else text[:110] + "…")

    def present_loading(self, src: str, x: int, y: int, direction):
        self._paint_src(src)
        self.dir_lbl.setText(f"{direction[0]} → {direction[1]}")
        self.note_lbl.hide()
        self.dst_lbl.show()
        self.dst_lbl.setStyleSheet(f"color: {C_SUB.name()}; background: transparent;")
        self.dst_lbl.setText("翻译中")
        self._dots = 0
        self._dot_timer.start()
        self._fit()
        self._place(x, y)
        self._fade.stop()
        self._fade.start()
        self.show()
        self.raise_()

    def present(self, src: str, dst: str, engine: str, x: int, y: int, direction,
                note: str = ""):
        self._dot_timer.stop()
        self._paint_src(src)
        self.dir_lbl.setText(f"{direction[0]} → {direction[1]}")

        body = (dst or "").strip()
        if body.startswith("翻译失败"):
            self.dst_lbl.show()
            self.dst_lbl.setStyleSheet(f"color: {C_ERR.name()}; background: transparent;")
            self.dst_lbl.setText(body)
            self.note_lbl.hide()
            self._fit()
            self._place(x, y)
            self._fade.stop()
            self._fade.start()
            self.show()
            self.raise_()
            return

        self.dst_lbl.show()
        self.dst_lbl.setStyleSheet(f"color: {C_TEXT.name()}; background: transparent;")
        self.dst_lbl.setText(body)
        if note:
            self.note_lbl.setText(note)
            self.note_lbl.show()
        elif body == " ".join((src or "").split()) and body:
            self.note_lbl.setText("译文与原文一致 · 代码/术语/专有名词通常保留原文")
            self.note_lbl.show()
        else:
            self.note_lbl.hide()

        self._fit()
        self._place(x, y)
        self._fade.stop()
        self._fade.start()
        self.show()
        self.raise_()

    def hide(self):  # noqa: A003
        self._dot_timer.stop()
        QWidget.hide(self)


class TranslatePopup:
    """对 main.py 暴露的门面：show_loading / show / hide / contains / after / destroy / run。"""

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv[:1])
        self.app.setQuitOnLastWindowClosed(False)  # 弹窗关闭 ≠ 退出程序（Alt+F4 不能杀死托盘）
        self.win = CardWindow()
        self.win.hide()

    # -- 事件循环 --
    def run(self):
        self.app.exec()

    def after(self, ms: int, fn):
        QTimer.singleShot(ms, fn)

    def destroy(self):
        self.win.close()
        self.app.quit()

    # -- 展示 --
    def show_loading(self, src, x, y, direction):
        self.win.present_loading(src, x, y, direction)

    def show(self, src, dst, engine, x, y, direction, note=""):
        self.win.present(src, dst, engine, x, y, direction, note)

    def hide(self):
        self.win.hide()

    @property
    def visible(self) -> bool:
        return self.win.isVisible()

    def contains(self, x: int, y: int) -> bool:
        return self.win.isVisible() and self.win.geometry().contains(x, y)
