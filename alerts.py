"""
Desktop, sound, screenshot, and Telegram alerts for actionable signals.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from config import ALERT_SOUND_PATH, CONFIG, SCREENSHOTS_DIR
from signals import TradeSignal
from utils import get_logger, utc_now

logger = get_logger()


class AlertManager:
    """Fire-and-forget notifications (never blocks the GUI thread long)."""

    def __init__(self) -> None:
        self._last_fingerprint: str | None = None
        self._window: Any = None  # QMainWindow / QWidget

    def bind_window(self, window: Any) -> None:
        """Attach the dashboard window so signal screenshots can grab it."""
        self._window = window

    def maybe_alert(self, signal: TradeSignal) -> None:
        if not signal.is_actionable:
            return
        fp = f"{signal.mode}:{signal.direction.value}:{signal.price:.1f}:{signal.confidence:.0f}"
        if fp == self._last_fingerprint:
            return
        self._last_fingerprint = fp
        # Grab on the GUI thread (caller), then notify in background.
        shot = self._capture_screenshot(signal)
        threading.Thread(target=self._dispatch, args=(signal, shot), daemon=True).start()

    def _capture_screenshot(self, signal: TradeSignal) -> Path | None:
        if not CONFIG.ui.screenshot_on_signal:
            return None
        try:
            from PySide6.QtWidgets import QApplication

            window = self._window
            if window is None:
                logger.debug("Screenshot skipped — no window bound")
                return None

            QApplication.processEvents()
            pixmap = window.grab()
            if pixmap.isNull():
                logger.warning("Screenshot grab returned empty pixmap")
                return None

            ts = utc_now().strftime("%Y%m%d_%H%M%S")
            symbol = CONFIG.primary_symbol or signal.timeframe or "SIGNAL"
            if CONFIG.data_source.value == "binance":
                symbol = CONFIG.binance.symbol or symbol
            mode = (signal.mode or CONFIG.trading_mode.value or "mode").upper()
            name = f"{ts}_{mode}_{symbol}_{signal.direction.value}_{int(signal.confidence)}.png"
            path = SCREENSHOTS_DIR / name
            if not pixmap.save(str(path), "PNG"):
                logger.warning("Failed to save screenshot to %s", path)
                return None
            logger.info("Signal screenshot saved: %s", path)
            return path
        except Exception as exc:  # noqa: BLE001
            logger.warning("Screenshot capture failed: %s", exc)
            return None

    def _dispatch(self, signal: TradeSignal, screenshot: Path | None = None) -> None:
        mode = (signal.mode or CONFIG.trading_mode.value).upper()
        sym = CONFIG.binance.symbol if CONFIG.data_source.value == "binance" else CONFIG.primary_symbol
        title = f"[{mode}] {sym} {signal.direction.value}"
        body = (
            f"Mode: {mode}\n"
            f"Confidence: {signal.confidence:.0f}%\n"
            f"Entry: {signal.risk.entry if signal.risk else signal.price}\n"
            f"SL: {signal.risk.stop_loss if signal.risk else '-'}\n"
            f"TP1: {signal.risk.take_profit_1 if signal.risk else '-'}"
        )
        if screenshot:
            body = f"{body}\nShot: {screenshot.name}"
        self._desktop(title, body)
        self._sound()
        self._telegram(title, body, signal, screenshot)

    def _desktop(self, title: str, body: str) -> None:
        try:
            from plyer import notification

            notification.notify(title=title, message=body, app_name="XAUUSD Analyzer", timeout=8)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Desktop notification failed: %s", exc)
            # Windows fallback
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(0, body, title, 0x40)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                logger.info("ALERT: %s — %s", title, body.replace("\n", " | "))

    def _sound(self) -> None:
        try:
            import winsound

            if ALERT_SOUND_PATH.exists():
                winsound.PlaySound(str(ALERT_SOUND_PATH), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Sound alert failed: %s", exc)

    def _telegram(
        self,
        title: str,
        body: str,
        signal: TradeSignal,
        screenshot: Path | None = None,
    ) -> None:
        tg = CONFIG.telegram
        if not tg.enabled or not tg.bot_token or not tg.chat_id:
            return
        try:
            import requests

            reasons = "\n".join(f"[OK] {r}" for r in signal.reasons[:10])
            text = f"*{title}*\n{body}\n\n{reasons}"
            base = f"https://api.telegram.org/bot{tg.bot_token}"
            if screenshot and screenshot.exists():
                with screenshot.open("rb") as fh:
                    requests.post(
                        f"{base}/sendPhoto",
                        data={"chat_id": tg.chat_id, "caption": text[:1024]},
                        files={"photo": fh},
                        timeout=20,
                    )
            else:
                requests.post(
                    f"{base}/sendMessage",
                    json={"chat_id": tg.chat_id, "text": text, "parse_mode": "Markdown"},
                    timeout=10,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram alert failed: %s", exc)
