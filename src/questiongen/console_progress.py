from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TextIO

from .batch import BatchProgressCallback, BatchProgressUpdate

SPINNER_FRAMES = ("-", "/", "|", "\\")


def chain_progress_callbacks(*callbacks: BatchProgressCallback | None) -> BatchProgressCallback | None:
    active_callbacks = [callback for callback in callbacks if callback is not None]
    if not active_callbacks:
        return None
    if len(active_callbacks) == 1:
        return active_callbacks[0]

    def chained(update: BatchProgressUpdate) -> None:
        for callback in active_callbacks:
            callback(update)

    return chained


def is_notable_progress_update(update: BatchProgressUpdate) -> bool:
    if update.event in {"started", "completed"}:
        return True
    if update.event == "item_started":
        return False
    return update.status != "validation_passed"


@dataclass
class ConsoleProgressRenderer:
    stream: TextIO = field(default_factory=lambda: sys.stdout)
    heartbeat_interval_seconds: float = 0.2
    live_updates: bool | None = None
    spinner_frames: Sequence[str] = SPINNER_FRAMES
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)
    _stop_requested: bool = field(default=False, init=False, repr=False)
    _last_update: BatchProgressUpdate | None = field(default=None, init=False, repr=False)
    _last_item_update: BatchProgressUpdate | None = field(default=None, init=False, repr=False)
    _last_rendered_width: int = field(default=0, init=False, repr=False)
    _spinner_index: int = field(default=0, init=False, repr=False)
    _heartbeat_thread: threading.Thread | None = field(default=None, init=False, repr=False)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop_requested = False
            self._last_item_update = None
            self._last_rendered_width = 0
            self._spinner_index = 0
            self._last_update = BatchProgressUpdate(
                event="started",
                completed_items=0,
                total_items=0,
                current_row_number="waiting",
                question_subtype_key="pending",
                status="preparing",
                message="Preparing batch run.",
            )
            live_updates = self._resolve_live_updates()
            self.live_updates = live_updates
            if not live_updates:
                return
            heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._heartbeat_thread = heartbeat
            heartbeat.start()

    def stop(self, *, success: bool, message: str | None = None) -> None:
        heartbeat_thread: threading.Thread | None = None
        with self._lock:
            if not self._started:
                return
            self._stop_requested = True
            heartbeat_thread = self._heartbeat_thread
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=max(self.heartbeat_interval_seconds * 4, 0.5))
        with self._lock:
            final_line = self._build_final_line(success=success, message=message)
            if self.live_updates:
                self._clear_line_locked()
            self.stream.write(final_line + "\n")
            self.stream.flush()
            self._started = False
            self._heartbeat_thread = None
            self._last_item_update = None
            self._last_rendered_width = 0

    def callback(self, update: BatchProgressUpdate) -> None:
        notable_message: str | None = None
        with self._lock:
            self._last_update = update
            if update.event in {"item_started", "item_completed"}:
                self._last_item_update = update
            if is_notable_progress_update(update):
                notable_message = self._format_notable_message(update)
            if self.live_updates:
                self._render_line_locked()
        if notable_message is not None:
            self.log_message(notable_message)

    def log_message(self, message: str) -> None:
        with self._lock:
            if self.live_updates:
                self._clear_line_locked()
            self.stream.write(message + "\n")
            if self.live_updates:
                self._render_line_locked()
            self.stream.flush()

    def _resolve_live_updates(self) -> bool:
        if self.live_updates is not None:
            return self.live_updates
        isatty = getattr(self.stream, "isatty", None)
        if callable(isatty) and isatty():
            return True
        if "ipykernel" in sys.modules or "google.colab" in sys.modules:
            return True
        if os.getenv("JPY_PARENT_PID"):
            return True
        return False

    def _heartbeat_loop(self) -> None:
        while True:
            with self._lock:
                if self._stop_requested:
                    return
                self._render_line_locked()
            time.sleep(self.heartbeat_interval_seconds)

    def _render_line_locked(self) -> None:
        line = self._build_live_line_locked()
        padded = line.ljust(self._last_rendered_width)
        self.stream.write("\r" + padded)
        self.stream.flush()
        self._last_rendered_width = len(padded)
        self._spinner_index = (self._spinner_index + 1) % len(self.spinner_frames)

    def _clear_line_locked(self) -> None:
        if self._last_rendered_width == 0:
            self.stream.write("\r")
            return
        self.stream.write("\r" + (" " * self._last_rendered_width) + "\r")

    def _build_live_line_locked(self) -> str:
        update = self._last_update
        spinner = self.spinner_frames[self._spinner_index]
        if update is None:
            return f"0/0 | waiting | pending | preparing {spinner}"
        return (
            f"{update.completed_items}/{max(update.total_items, 1)} | "
            f"{self._row_label(update)} | {self._subtype_label(update)} | "
            f"{self._status_label(update)} {spinner}"
        )

    def _build_final_line(self, *, success: bool, message: str | None) -> str:
        update = self._last_update
        prefix = "done" if success else "failed"
        if update is None:
            suffix = message or ("Batch run completed." if success else "Batch run failed.")
            return f"{prefix} 0/0 | waiting | pending | {suffix}"
        context_update = self._last_item_update or update
        status = message or self._status_label(update)
        return (
            f"{prefix} {update.completed_items}/{max(update.total_items, 1)} | "
            f"{self._row_label(context_update)} | {self._subtype_label(context_update)} | {status}"
        )

    def _format_notable_message(self, update: BatchProgressUpdate) -> str:
        if update.event == "started":
            return update.message or "Batch run started."
        if update.event == "completed":
            return update.message or "Batch run completed."
        message = f" | {update.message}" if update.message else ""
        return (
            f"[{update.completed_items}/{max(update.total_items, 1)}] "
            f"{self._row_label(update)} :: {self._subtype_label(update)} -> "
            f"{update.status or 'unknown'}{message}"
        )

    @staticmethod
    def _row_label(update: BatchProgressUpdate) -> str:
        if update.current_row_number:
            return update.current_row_number
        if update.batch_row_id is not None:
            return f"row {update.batch_row_id}"
        return "waiting"

    @staticmethod
    def _subtype_label(update: BatchProgressUpdate) -> str:
        return update.question_subtype_key or update.question_type_key or "pending"

    @staticmethod
    def _status_label(update: BatchProgressUpdate) -> str:
        return update.status or update.message or ("completed" if update.event == "completed" else "running")
