# src/reporters.py
from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path
from typing import Optional

from tqdm import tqdm


class DownloadTqdm:
    """
    Minimal async progress bar for Playwright downloads.

    Usage:
        bar = DownloadTqdm(desc="file.csv")
        await bar.start(download)
        try:
            await download.save_as(path)
        finally:
            await bar.stop(final_path=path)
    """

    def __init__(
        self,
        *,
        desc: str,
        unit: str = "B",
        unit_scale: bool = True,
        unit_divisor: int = 1024,
        mininterval: float = 0.2,
    ):
        self.desc = desc
        self._bar: Optional[tqdm] = None
        self._task: Optional[asyncio.Task] = None

        self._unit = unit
        self._unit_scale = unit_scale
        self._unit_divisor = unit_divisor
        self._mininterval = mininterval

        self._last_bytes = 0
        self._start_ts = 0.0
        self._done = asyncio.Event()

    async def start(self, download) -> None:
        # total_bytes() may be unknown; that's fine (tqdm total=None)
        try:
            total = await download.total_bytes()
        except Exception:
            total = None

        self._bar = tqdm(
            total=total,
            desc=self.desc,
            unit=self._unit,
            unit_scale=self._unit_scale,
            unit_divisor=self._unit_divisor,
            mininterval=self._mininterval,
            leave=True,
        )

        self._start_ts = time.monotonic()
        self._last_bytes = 0
        self._done.clear()

        async def _poll() -> None:
            while not self._done.is_set():
                try:
                    info = await download.progress()
                    current = int(info.get("bytes", 0) or 0)
                except Exception:
                    current = self._last_bytes

                delta = current - self._last_bytes
                if delta > 0 and self._bar is not None:
                    self._bar.update(delta)
                    self._last_bytes = current

                await asyncio.sleep(self._mininterval)

        self._task = asyncio.create_task(_poll())

    async def stop(self, *, final_path: Optional[str | Path] = None) -> None:
        self._done.set()

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        # IMPORTANT: never do `if self._bar:` because tqdm.__bool__ can raise
        if self._bar is not None:
            # If tqdm knew the total and we didn't reach it, try to finish cleanly
            try:
                total = self._bar.total
                if total is not None and self._last_bytes < total:
                    self._bar.update(total - self._last_bytes)
            except Exception:
                pass

            self._bar.close()
            self._bar = None

        # final_path is kept only to match your call-site signature
        _ = final_path
