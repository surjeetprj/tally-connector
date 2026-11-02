"""Source launch: python -m innoforia_tally_connector. No local web server."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QStyle, QSystemTrayIcon

from innoforia_tally_connector.bootstrap.dependencies import build
from innoforia_tally_connector.config.paths import runtime_directory
from innoforia_tally_connector.diagnostics.log_setup import configure
from innoforia_tally_connector.host.windows.single_instance import acquire
from innoforia_tally_connector.ui.bridge import Bridge
from innoforia_tally_connector.ui.controllers.discovery import Controller
from innoforia_tally_connector.ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, help="Explicit isolated runtime directory for verification")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setFont(QFont("Segoe UI", 10))
    app.setApplicationName("InnoforaiTallySync")
    try:
        directory = args.runtime_dir.resolve() if args.runtime_dir else runtime_directory()
        directory.mkdir(parents=True, exist_ok=True)
        lock = acquire(directory)
        log_handler = configure(directory)
    except (OSError, ValueError):
        QMessageBox.warning(None, "Connector unavailable", "Connector may already be running, or its runtime directory is unavailable.")
        return 1
    bridge, window = Bridge(), MainWindow()
    window.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    app.setQuitOnLastWindowClosed(False)
    runtime, cleanup, closing, startup_failed = None, None, False, False
    startup = ThreadPoolExecutor(max_workers=1, thread_name_prefix="connector-startup")
    future = startup.submit(build, directory, bridge.event.emit)

    def quit_connector():
        nonlocal closing
        if closing:
            return
        closing = True
        window.status.setText("Stopping new work; waiting for bounded background reads…")
        window.setEnabled(False)
        if runtime:
            runtime.shutdown(cleanup)
        elif startup_failed:
            app.quit()

    window.request_quit = quit_connector
    tray = QSystemTrayIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), window)
    menu = QMenu()
    open_action, quit_action = QAction("Open party discovery"), QAction("Quit connector")
    open_action.triggered.connect(lambda: (window.showNormal(), window.raise_(), window.activateWindow()))
    quit_action.triggered.connect(quit_connector)
    window.menuBar().addAction(quit_action)
    menu.addAction(open_action)
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    if window.tray_available:
        tray.show()
    window.show()

    def poll():
        nonlocal runtime, cleanup, startup_failed
        if runtime is None and future.done() and not startup_failed:
            try:
                runtime, cleanup = future.result()
                startup.shutdown(wait=False)
                if closing:
                    runtime.shutdown(cleanup)
                else:
                    runtime.start()
                    window.attach(Controller(runtime, bridge))
            except Exception:
                startup_failed = True
                window.status.setText("Startup failed. Metadata is preserved; inspect redacted diagnostics and recover from backup if needed.")
                startup.shutdown(wait=False)
                if closing:
                    app.quit()
                return
        if closing and runtime and runtime.closed.is_set():
            window.quitting = True
            tray.hide()
            app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(50)
    result = app.exec()
    lock.unlock()
    log_handler.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
