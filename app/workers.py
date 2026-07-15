"""
AIDA Desktop — fon oqimlari
===========================
Og'ir yoki tarmoqqa bog'liq ishlarni alohida QThread'da bajarib,
interfeys muzlab qolmasligini ta'minlaydi.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal


class Worker(QObject):
    """Bitta funksiyani fonda bajaradi."""

    finished = Signal(object)   # natija
    failed = Signal(str)        # xato matni

    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:  # noqa: BLE001 — foydalanuvchiga ko'rsatamiz
            self.failed.emit(str(e))


class TaskRunner:
    """Funksiyani fonda ishga tushirib, natijani callback'ga qaytaradi.

    Ishlatish:
        self._runner = TaskRunner()
        self._runner.run(heavy_fn, arg1, on_done=..., on_error=...)

    MUHIM: TaskRunner obyektini widget'da saqlash kerak (masalan self._runner),
    aks holda garbage collector oqimni to'xtatib yuboradi.
    """

    def __init__(self):
        self._thread: QThread | None = None
        self._worker: Worker | None = None

    def run(self, fn, *args, on_done=None, on_error=None, **kwargs):
        # oldingi oqim tugaganini kutamiz (oddiy holat uchun yetarli)
        self._thread = QThread()
        self._worker = Worker(fn, *args, **kwargs)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        if on_done:
            self._worker.finished.connect(on_done)
        if on_error:
            self._worker.failed.connect(on_error)

        # tozalash
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def is_running(self) -> bool:
        try:
            return self._thread is not None and self._thread.isRunning()
        except RuntimeError:  # C++ obyekt allaqachon o'chirilgan
            return False

    def wait(self, ms: int = 3000):
        """Oqim tugashini (yoki timeout'ni) kutadi — toza yopilish uchun."""
        try:
            if self._thread is not None and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(ms)
        except RuntimeError:  # allaqachon tugagan/o'chirilgan
            pass
