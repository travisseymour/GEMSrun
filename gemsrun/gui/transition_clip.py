"""
Qt-native (C++-backed) transition clips for PySide6.

API:
    make_transition(before: QPixmap, after: QPixmap,
                    transition: str, duration: int) -> TransitionClip

- transition: "dissolve", "wipe-left", "wipe-right"
- duration: milliseconds
- Output: TransitionClip (QObject) that can be played in a window.
          Emits frameChanged(QPixmap) during playback.

Caching:
- LRU cache of the most recent N=10 clips (configurable).
- Keyed by (before.cacheKey, after.cacheKey, transition, duration_ms, fps, target_size, dpr).

Performance notes:
- Uses QPainter compositing/blitting (Qt C++).
- Avoids per-pixel Python loops.
- Converts and scales inputs once; frames are pre-rendered and stored as QPixmap.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap

_SUPPORTED = {"dissolve", "wipe-left", "wipe-right"}


def _ms_per_frame(fps: int) -> int:
    fps = max(1, int(fps))
    return max(1, int(round(1000 / fps)))


def _frame_count(duration_ms: int, fps: int) -> int:
    duration_ms = max(0, int(duration_ms))
    if duration_ms == 0:
        return 1
    step = _ms_per_frame(fps)
    # Include final frame at t=1.0
    return max(2, (duration_ms // step) + 1)


def _choose_target_size(before: QPixmap, after: QPixmap) -> QSize:
    # Reasonable default: prefer 'before' size; if null, use 'after'; else max of both.
    if not before.isNull():
        return before.size()
    if not after.isNull():
        return after.size()
    return QSize(1, 1)


def _pixmap_to_image(pm: QPixmap, target: QSize) -> QImage:
    """
    Convert to QImage in a format suitable for fast composition.
    Scale once to the target size if needed.
    """
    if pm.isNull():
        img = QImage(target, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        return img

    # Ensure it is the right size; smooth scaling keeps results pleasant.
    if pm.size() != target:
        pm = pm.scaled(
            target,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    img = pm.toImage()
    if img.format() != QImage.Format.Format_ARGB32_Premultiplied:
        img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return img


def _render_dissolve(before_img: QImage, after_img: QImage, t: float) -> QImage:
    w, h = before_img.width(), before_img.height()
    out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)

    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    p.setOpacity(1.0)
    p.drawImage(0, 0, before_img)

    p.setOpacity(max(0.0, min(1.0, t)))
    p.drawImage(0, 0, after_img)

    p.end()
    return out


def _render_wipe(
    before_img: QImage, after_img: QImage, t: float, direction: str
) -> QImage:
    """
    direction: "left" means reveal from left edge to right.
               "right" means reveal from right edge to left.
    """
    w, h = before_img.width(), before_img.height()
    out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)

    reveal = int(round(max(0.0, min(1.0, t)) * w))

    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # Base: before
    p.drawImage(0, 0, before_img)

    # Overlay: revealed portion of after
    if reveal > 0:
        if direction == "left":
            # reveal from left
            p.drawImage(0, 0, after_img, 0, 0, reveal, h)
        else:
            # reveal from right
            x = w - reveal
            p.drawImage(x, 0, after_img, x, 0, reveal, h)

    p.end()
    return out


@dataclass(frozen=True)
class _ClipKey:
    before_key: int
    after_key: int
    transition: str
    duration_ms: int
    fps: int
    width: int
    height: int
    dpr: float


class TransitionClip(QObject):
    """
    A small playable object for Qt/PySide6.

    - Call start() to begin playback; stop() to stop.
    - Connect frameChanged(QPixmap) to update a QLabel or custom widget.
    """

    frameChanged = Signal(QPixmap)
    finished = Signal()

    def __init__(
        self,
        frames: list[QPixmap],
        duration_ms: int,
        fps: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._frames = frames
        self._duration_ms = max(0, int(duration_ms))
        self._fps = max(1, int(fps))
        self._i = 0

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._advance)

    @property
    def frames(self) -> list[QPixmap]:
        return self._frames

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def current_frame(self) -> QPixmap:
        if not self._frames:
            return QPixmap()
        return self._frames[min(self._i, len(self._frames) - 1)]

    def start(self, loop: bool = False) -> None:
        """
        Start playback. If loop=True, it loops.
        """
        self._loop = bool(loop)
        self._i = 0
        if self._frames:
            self.frameChanged.emit(self._frames[0])

        # If only one frame, immediately finish unless looping.
        if len(self._frames) <= 1:
            if self._loop:
                return
            self.finished.emit()
            return

        self._timer.start(_ms_per_frame(self._fps))

    def stop(self) -> None:
        self._timer.stop()

    def is_playing(self) -> bool:
        return self._timer.isActive()

    def _advance(self) -> None:
        if not self._frames:
            self.stop()
            self.finished.emit()
            return

        self._i += 1
        if self._i >= len(self._frames):
            if getattr(self, "_loop", False):
                self._i = 0
            else:
                self.stop()
                self.finished.emit()
                return

        self.frameChanged.emit(self._frames[self._i])


class TransitionFactory:
    """
    Creates and caches transition clips (LRU cache of rendered frame lists).
    """

    def __init__(self, cache_size: int = 10, fps: int = 30) -> None:
        self._cache_size = max(1, int(cache_size))
        self._fps = max(1, int(fps))
        self._lru: OrderedDict[_ClipKey, list[QPixmap]] = OrderedDict()

    @property
    def cache_size(self) -> int:
        return self._cache_size

    @property
    def fps(self) -> int:
        return self._fps

    def make_transition(
        self,
        before: QPixmap,
        after: QPixmap,
        transition: str,
        duration_ms: int,
        *,
        fps: int | None = None,
        target_size: QSize | None = None,
        parent: QObject | None = None,
    ) -> TransitionClip:
        transition = (transition or "").strip().lower()
        if transition not in _SUPPORTED:
            raise ValueError(
                f"Unsupported transition '{transition}'. Supported: {sorted(_SUPPORTED)}"
            )

        fps_i = self._fps if fps is None else max(1, int(fps))
        duration_ms = max(0, int(duration_ms))

        size = (
            target_size
            if target_size is not None
            else _choose_target_size(before, after)
        )
        w, h = max(1, size.width()), max(1, size.height())

        # DPR: if either pixmap has DPR, preserve a sensible value (max).
        dpr = float(max(before.devicePixelRatio(), after.devicePixelRatio(), 1.0))

        key = _ClipKey(
            before_key=int(before.cacheKey()) if not before.isNull() else 0,
            after_key=int(after.cacheKey()) if not after.isNull() else 0,
            transition=transition,
            duration_ms=duration_ms,
            fps=fps_i,
            width=w,
            height=h,
            dpr=dpr,
        )

        frames = self._lru_get(key)
        if frames is None:
            frames = self._render_frames(
                before, after, transition, duration_ms, fps_i, QSize(w, h), dpr
            )
            self._lru_put(key, frames)

        # Clip is a lightweight player wrapper around cached frames.
        return TransitionClip(
            frames=frames, duration_ms=duration_ms, fps=fps_i, parent=parent
        )

    def _lru_get(self, key: _ClipKey) -> list[QPixmap] | None:
        frames = self._lru.get(key)
        if frames is None:
            return None
        self._lru.move_to_end(key, last=True)
        return frames

    def _lru_put(self, key: _ClipKey, frames: list[QPixmap]) -> None:
        self._lru[key] = frames
        self._lru.move_to_end(key, last=True)
        while len(self._lru) > self._cache_size:
            self._lru.popitem(last=False)

    def _render_frames(
        self,
        before: QPixmap,
        after: QPixmap,
        transition: str,
        duration_ms: int,
        fps: int,
        target: QSize,
        dpr: float,
    ) -> list[QPixmap]:
        # Convert once (and scale once) into images suitable for composition.
        before_img = _pixmap_to_image(before, target)
        after_img = _pixmap_to_image(after, target)

        n = _frame_count(duration_ms, fps)

        if transition == "dissolve":
            renderer: Callable[[float], QImage] = partial(
                _render_dissolve, before_img, after_img
            )
        elif transition == "wipe-left":
            renderer = partial(_render_wipe, before_img, after_img, direction="left")
        else:  # "wipe-right"
            renderer = partial(_render_wipe, before_img, after_img, direction="right")

        frames: list[QPixmap] = []
        for i in range(n):
            t = 1.0 if n <= 1 else (i / (n - 1))
            img = renderer(t)

            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(dpr)
            frames.append(pm)

        return frames


# A module-level factory matching your requested signature.
_default_factory = TransitionFactory(cache_size=10, fps=30)


def make_transition(
    before: QPixmap, after: QPixmap, transition: str, duration: int
) -> TransitionClip:
    """
    Requested top-level API.
    duration is milliseconds.
    """
    return _default_factory.make_transition(before, after, transition, duration)


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication(sys.argv)

    # Create two simple pixmaps for demonstration
    size = QSize(640, 360)
    before = QPixmap(size)
    before.fill(Qt.GlobalColor.black)
    p = QPainter(before)
    p.setPen(Qt.GlobalColor.white)
    p.setFont(app.font())
    p.drawText(before.rect(), Qt.AlignmentFlag.AlignCenter, "BEFORE")
    p.end()

    after = QPixmap(size)
    after.fill(Qt.GlobalColor.white)
    p = QPainter(after)
    p.setPen(Qt.GlobalColor.black)
    p.setFont(app.font())
    p.drawText(after.rect(), Qt.AlignmentFlag.AlignCenter, "AFTER")
    p.end()

    w = QWidget()
    w.setWindowTitle("TransitionClip Demo")

    layout = QVBoxLayout(w)
    label = QLabel()
    label.setFixedSize(size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    btn_row = QHBoxLayout()
    layout.addLayout(btn_row)

    # def play(name: str) -> None:
    #     clip = make_transition(before, after, name, 1200)
    #     clip.frameChanged.connect(label.setPixmap)
    #     clip.finished.connect(lambda: None)
    #     clip.start(loop=False)

    # def play(name: str) -> None:
    #     # Stop/delete any prior clip if present
    #     old = getattr(w, "_clip", None)
    #     if old is not None:
    #         old.stop()
    #         old.deleteLater()

    #     # Create and store the new clip (this assignment is what keeps it alive)
    #     w._clip = make_transition(before, after, name, 1200)

    #     # Display frames
    #     w._clip.frameChanged.connect(label.setPixmap)

    #     w._clip.start(loop=False)

    clip_holder = {"clip": None}

    def play(name: str) -> None:
        old = clip_holder["clip"]
        if old is not None:
            old.stop()
            old.deleteLater()

        clip = make_transition(before, after, name, 1200)
        clip.frameChanged.connect(label.setPixmap)
        # clip.frameChanged.connect(lambda pm: print("frame", pm.size()))
        clip.start(loop=False)

        clip_holder["clip"] = clip

    b1 = QPushButton("Dissolve")
    b1.clicked.connect(lambda: play("dissolve"))
    btn_row.addWidget(b1)

    b2 = QPushButton("Wipe Left")
    b2.clicked.connect(lambda: play("wipe-left"))
    btn_row.addWidget(b2)

    b3 = QPushButton("Wipe Right")
    b3.clicked.connect(lambda: play("wipe-right"))
    btn_row.addWidget(b3)

    label.setPixmap(before)

    w.show()
    sys.exit(app.exec())
