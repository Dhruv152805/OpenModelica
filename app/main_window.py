"""
main_window.py
==============
Defines :class:`MainWindow` — the top-level PyQt6 widget that provides the
full user interface for the OpenModelica Model Runner application.

UI layout (top → bottom)
------------------------
1. Executable selector row  (QLineEdit + "Browse…" button)
2. Time inputs row          (QSpinBox × 2)
3. "Run Simulation" button
4. Read-only output console  (QPlainTextEdit)
5. Status bar               (QStatusBar)

All business logic — subprocess launching, parameter validation — is
delegated to :class:`~app.simulation_runner.SimulationRunner`.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QFrame,
    QSizePolicy,
    QApplication,
)

from app.simulation_runner import SimulationResult, SimulationRunner


# ---------------------------------------------------------------------------
# Background worker — keeps the UI responsive while the simulation runs
# ---------------------------------------------------------------------------


class _SimWorker(QThread):
    """
    Runs :meth:`SimulationRunner.run` in a background thread so the GUI
    event-loop stays responsive.

    Signals
    -------
    finished(SimulationResult)
        Emitted when the simulation completes (success **or** failure).
    error(str)
        Emitted when an exception prevents the simulation from starting
        (e.g. ``FileNotFoundError``, ``ValueError``).
    """

    finished: pyqtSignal = pyqtSignal(object)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(self, runner: SimulationRunner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runner = runner

    def run(self) -> None:  # noqa: D102
        try:
            result: SimulationResult = self._runner.run()
            self.finished.emit(result)
        except Exception as exc:  # pylint: disable=broad-except
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """
    Top-level application window for the FOSSEE OpenModelica Model Runner.

    Responsibilities
    ----------------
    * Build and manage the complete PyQt6 user interface.
    * Validate user inputs before handing off to :class:`SimulationRunner`.
    * Launch simulations on a background :class:`_SimWorker` thread and
      stream results into the output console.
    * Enable / disable the Run button to prevent concurrent runs.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OpenModelica Model Runner — FOSSEE Screening Task")
        self.setMinimumSize(700, 560)
        self._worker: _SimWorker | None = None
        self._build_ui()
        self._apply_stylesheet()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct and arrange all child widgets."""
        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 16)

        # ── Header ──────────────────────────────────────────────────────
        header = QLabel("OpenModelica Model Runner")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(header)

        subtitle = QLabel("FOSSEE Screening Task 2 · TwoConnectedTanks")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addWidget(self._make_separator())

        # ── Executable selector ─────────────────────────────────────────
        root.addWidget(self._make_section_label("① Model Executable"))
        exe_row = QHBoxLayout()
        exe_row.setSpacing(8)

        self.exe_edit = QLineEdit()
        self.exe_edit.setObjectName("exe_edit")
        self.exe_edit.setPlaceholderText("Path to compiled model executable …")
        self.exe_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        exe_row.addWidget(self.exe_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("browse_btn")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse)
        exe_row.addWidget(browse_btn)
        root.addLayout(exe_row)

        root.addWidget(self._make_separator())

        # ── Time inputs ─────────────────────────────────────────────────
        root.addWidget(self._make_section_label("② Simulation Time Range  (0 ≤ start < stop < 5)"))
        time_row = QHBoxLayout()
        time_row.setSpacing(16)

        self.start_spin = QSpinBox()
        self.start_spin.setObjectName("start_spin")
        self.start_spin.setRange(0, 3)
        self.start_spin.setValue(0)
        self.start_spin.setSuffix("  s")
        self.start_spin.setFixedWidth(90)

        self.stop_spin = QSpinBox()
        self.stop_spin.setObjectName("stop_spin")
        self.stop_spin.setRange(1, 4)
        self.stop_spin.setValue(3)
        self.stop_spin.setSuffix("  s")
        self.stop_spin.setFixedWidth(90)

        time_row.addWidget(QLabel("Start time:"))
        time_row.addWidget(self.start_spin)
        time_row.addSpacing(24)
        time_row.addWidget(QLabel("Stop time:"))
        time_row.addWidget(self.stop_spin)
        time_row.addStretch()
        root.addLayout(time_row)

        root.addWidget(self._make_separator())

        # ── Run button ──────────────────────────────────────────────────
        self.run_btn = QPushButton("▶  Run Simulation")
        self.run_btn.setObjectName("run_btn")
        self.run_btn.setFixedHeight(44)
        self.run_btn.clicked.connect(self._on_run)
        root.addWidget(self.run_btn)

        # ── Output console ──────────────────────────────────────────────
        root.addWidget(self._make_section_label("③ Output Console"))
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Simulation output will appear here …")
        self.log.setFont(QFont("Consolas", 9))
        root.addWidget(self.log)

        # ── Clear button (small, bottom-right) ─────────────────────────
        clear_btn = QPushButton("Clear Log")
        clear_btn.setObjectName("clear_btn")
        clear_btn.setFixedWidth(100)
        clear_btn.clicked.connect(self.log.clear)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(clear_btn)
        root.addLayout(btn_row)

        # ── Status bar ──────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _apply_stylesheet(self) -> None:
        """Apply a dark, professional stylesheet to the entire window."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1d27;
                color: #e0e4f0;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
            }

            QLabel#header {
                font-size: 22px;
                font-weight: 700;
                color: #7eb8f7;
                letter-spacing: 0.5px;
                padding: 4px 0;
            }

            QLabel#subtitle {
                font-size: 11px;
                color: #6b7280;
                padding-bottom: 4px;
            }

            QLabel[objectName^="section"] {
                font-size: 11px;
                font-weight: 600;
                color: #7eb8f7;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }

            QLineEdit, QSpinBox, QPlainTextEdit {
                background-color: #242737;
                border: 1px solid #3a3f55;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e0e4f0;
                selection-background-color: #3d5a9e;
            }

            QLineEdit:focus, QSpinBox:focus {
                border-color: #7eb8f7;
            }

            QSpinBox::up-button, QSpinBox::down-button {
                width: 18px;
                border-left: 1px solid #3a3f55;
                background: #2e3248;
                border-radius: 0 4px 4px 0;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #3d5a9e;
            }

            QPushButton {
                background-color: #2e3248;
                border: 1px solid #3a3f55;
                border-radius: 6px;
                padding: 6px 14px;
                color: #e0e4f0;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3d5a9e;
                border-color: #7eb8f7;
            }
            QPushButton:pressed {
                background-color: #2a3d7a;
            }
            QPushButton:disabled {
                background-color: #1f2235;
                color: #4a4f6a;
                border-color: #2a2f45;
            }

            QPushButton#run_btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #1d4ed8);
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 700;
                color: #ffffff;
                letter-spacing: 0.5px;
            }
            QPushButton#run_btn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #2563eb);
            }
            QPushButton#run_btn:disabled {
                background: #1a2a5e;
                color: #5a6fa8;
            }

            QPlainTextEdit#log {
                background-color: #0f1117;
                border: 1px solid #2a2f45;
                border-radius: 6px;
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 11px;
                color: #a8d8a8;
                padding: 8px;
            }

            QStatusBar {
                background-color: #12141f;
                color: #6b7280;
                border-top: 1px solid #2a2f45;
                font-size: 11px;
            }

            QFrame#separator {
                background-color: #2a2f45;
                max-height: 1px;
            }
        """)

    # ------------------------------------------------------------------
    # Helper widgets
    # ------------------------------------------------------------------

    @staticmethod
    def _make_separator() -> QFrame:
        """Return a thin horizontal rule used as a visual section divider."""
        line = QFrame()
        line.setObjectName("separator")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    @staticmethod
    def _make_section_label(text: str) -> QLabel:
        """Return a styled section-header label."""
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        return lbl

    # ------------------------------------------------------------------
    # Slots / event handlers
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        """
        Open a :class:`QFileDialog` to let the user select the compiled model
        executable, then populate :attr:`exe_edit`.
        """
        start_dir = os.path.dirname(self.exe_edit.text()) or os.getcwd()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select compiled OpenModelica executable",
            start_dir,
            "Executables (*.exe *.out *);;All files (*)",
        )
        if path:
            self.exe_edit.setText(path)
            self.status_bar.showMessage(f"Executable selected: {path}")

    def _on_run(self) -> None:
        """
        Validate inputs, then launch the simulation on a background thread.

        Guards
        ------
        * Shows a :class:`QMessageBox` warning if no executable is entered.
        * Shows a :class:`QMessageBox` warning if ``start >= stop``.
        """
        exe_path = self.exe_edit.text().strip()
        if not exe_path:
            QMessageBox.warning(self, "Missing executable", "Please select a model executable first.")
            return

        start = self.start_spin.value()
        stop = self.stop_spin.value()

        if start >= stop:
            QMessageBox.warning(
                self,
                "Invalid time range",
                f"Start time ({start}) must be strictly less than stop time ({stop}).",
            )
            return

        runner = SimulationRunner(exe_path, start, stop)
        self._start_worker(runner)

    def _start_worker(self, runner: SimulationRunner) -> None:
        """Spin up a background :class:`_SimWorker` for *runner*."""
        self.run_btn.setEnabled(False)
        self.status_bar.showMessage("Running simulation …")
        cmd_display = " ".join(runner.build_command())
        self.log.appendPlainText(f"$ {cmd_display}\n")

        self._worker = _SimWorker(runner, parent=self)
        self._worker.finished.connect(self._on_simulation_finished)
        self._worker.error.connect(self._on_simulation_error)
        self._worker.start()

    def _on_simulation_finished(self, result: SimulationResult) -> None:
        """
        Handle a completed simulation (whether successful or not).

        Parameters
        ----------
        result : SimulationResult
            The outcome from :meth:`SimulationRunner.run`.
        """
        if result.output.strip():
            self.log.appendPlainText(result.output)

        if result.success:
            self.log.appendPlainText("✅  Simulation completed successfully.\n")
            self.status_bar.showMessage(f"Done — exit code {result.return_code}.")
        else:
            self.log.appendPlainText(
                f"❌  Simulation failed (exit code {result.return_code}).\n"
            )
            if result.error_message:
                self.log.appendPlainText(f"    {result.error_message}\n")
            self.status_bar.showMessage(f"Failed — exit code {result.return_code}.")
            QMessageBox.warning(
                self,
                "Simulation Failed",
                result.error_message or f"Process exited with code {result.return_code}.",
            )

        self.run_btn.setEnabled(True)

    def _on_simulation_error(self, message: str) -> None:
        """
        Handle a pre-launch exception (e.g. file not found, validation error).

        Parameters
        ----------
        message : str
            Human-readable description of the exception.
        """
        self.log.appendPlainText(f"❌  Error: {message}\n")
        self.status_bar.showMessage("Error — see output console.")
        QMessageBox.critical(self, "Error", message)
        self.run_btn.setEnabled(True)
