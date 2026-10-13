"""PyQt5 desktop interface for the trade scraper."""

from __future__ import annotations

import sys
from typing import Sequence

from PyQt5 import QtCore, QtWidgets

from .scraper import DEFAULT_ITEMS, ScraperError, TradeScraper


class ScrapeWorker(QtCore.QObject):
    """Runs a scrape on a background thread so the window stays responsive."""

    finished = QtCore.pyqtSignal(list)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, username: str, items: Sequence[str], headless: bool) -> None:
        super().__init__()
        self.username = username
        self.items = list(items)
        self.headless = headless

    @QtCore.pyqtSlot()
    def run(self) -> None:
        try:
            with TradeScraper(headless=self.headless) as scraper:
                results = scraper.scrape(self.username, self.items)
        except (ScraperError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface anything unexpected
            self.failed.emit(f"Unexpected error: {exc}")
        else:
            self.finished.emit(results)


class MainWindow(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread = None
        self._worker = None
        self._build_ui()

    # -- layout ------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle("Rocket League Trade Scraper")
        self.resize(560, 480)

        self.username_input = QtWidgets.QLineEdit()
        self.username_input.setPlaceholderText("rocket-league.com username")

        self.mode_popular = QtWidgets.QRadioButton("Popular items")
        self.mode_custom = QtWidgets.QRadioButton("Custom item")
        self.mode_popular.setChecked(True)
        self.mode_popular.toggled.connect(self._update_mode)

        self.color_input = QtWidgets.QLineEdit()
        self.color_input.setPlaceholderText("e.g. Titanium White (leave empty for default)")
        self.item_input = QtWidgets.QLineEdit()
        self.item_input.setPlaceholderText("e.g. Octane")

        self.custom_box = QtWidgets.QGroupBox("Custom item")
        custom_form = QtWidgets.QFormLayout(self.custom_box)
        custom_form.addRow("Color:", self.color_input)
        custom_form.addRow("Item name:", self.item_input)

        self.headless_check = QtWidgets.QCheckBox("Run browser in background")
        self.headless_check.setChecked(True)

        self.search_button = QtWidgets.QPushButton("Search")
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.search_button.clicked.connect(self._start_search)
        self.clear_button.clicked.connect(self._clear)
        self.username_input.returnPressed.connect(self._start_search)
        self.item_input.returnPressed.connect(self._start_search)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.status = QtWidgets.QLabel("Ready.")

        form = QtWidgets.QFormLayout()
        form.addRow("Username:", self.username_input)

        modes = QtWidgets.QHBoxLayout()
        modes.addWidget(self.mode_popular)
        modes.addWidget(self.mode_custom)
        modes.addStretch()

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.headless_check)
        buttons.addStretch()
        buttons.addWidget(self.clear_button)
        buttons.addWidget(self.search_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(modes)
        layout.addWidget(self.custom_box)
        layout.addLayout(buttons)
        layout.addWidget(self.output, stretch=1)
        layout.addWidget(self.status)

        self._update_mode()

    def _update_mode(self) -> None:
        self.custom_box.setVisible(self.mode_custom.isChecked())

    # -- actions -----------------------------------------------------------

    def _selected_items(self) -> list:
        if self.mode_popular.isChecked():
            return list(DEFAULT_ITEMS)
        color = self.color_input.text().strip()
        name = self.item_input.text().strip()
        if not name:
            return []
        return [f"{color} {name}".strip()]

    def _start_search(self) -> None:
        if self._thread is not None:
            return  # A search is already running.

        username = self.username_input.text().strip()
        if not username:
            self._warn("Please enter a username.")
            return
        items = self._selected_items()
        if not items:
            self._warn("Please enter an item name.")
            return

        self.output.clear()
        self._set_busy(True, f"Fetching trades for {username}…")

        self._thread = QtCore.QThread(self)
        self._worker = ScrapeWorker(username, items, self.headless_check.isChecked())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._show_results)
        self._worker.failed.connect(self._show_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _show_results(self, results: list) -> None:
        found = [r for r in results if r.has_offers]
        if found:
            self.output.setPlainText("\n\n".join(r.summary() for r in found))
            self._set_busy(False, f"Done. Offers found for {len(found)} of {len(results)} item(s).")
        else:
            self.output.setPlainText("No offers found for the selected item(s).")
            self._set_busy(False, "Done.")

    def _show_error(self, message: str) -> None:
        self._set_busy(False, "Failed.")
        QtWidgets.QMessageBox.critical(self, "Error", message)

    def _cleanup_thread(self) -> None:
        self._worker.deleteLater()
        self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def _clear(self) -> None:
        for field in (self.username_input, self.color_input, self.item_input):
            field.clear()
        self.output.clear()
        self.status.setText("Ready.")

    def _set_busy(self, busy: bool, message: str) -> None:
        self.search_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.status.setText(message)

    def _warn(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "Missing input", message)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()
