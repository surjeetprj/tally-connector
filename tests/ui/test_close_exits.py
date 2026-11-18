"""Exercise the real source entry point in a child process with fake services."""
import os
import subprocess
import sys
import textwrap
import pytest


@pytest.mark.parametrize("tray,delay", [(True, 0), (True, .3), (False, 0), (True, "failure"), (True, "delayed-failure")])
def test_window_x_exits_process_through_shutdown(tmp_path, tray, delay):
    script = textwrap.dedent('''
        import sys, time, threading
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon
        import innoforia_tally_connector.__main__ as entry
        class Runtime:
            def __init__(self): self.closed = threading.Event()
            def start(self): print("worker-started", flush=True)
            def submit(self, *args, **kwargs): return "read-only-startup"
            def shutdown(self, cleanup):
                print("graceful-shutdown", flush=True)
                cleanup()
                QTimer.singleShot(30, self.closed.set)
        runtime_dir, tray, delay = sys.argv[1:]
        # Preserve test flags separately; argparse sees only the real app options.
        def fake_build(*args):
            if "failure" in delay:
                if delay.startswith("delayed"): time.sleep(.3)
                raise RuntimeError("Synthetic startup failure")
            time.sleep(float(delay))
            return Runtime(), lambda: print("resources-closed", flush=True)
        entry.build = fake_build
        QSystemTrayIcon.isSystemTrayAvailable = staticmethod(lambda: tray == "True")
        sys.argv = ["connector", "--runtime-dir", runtime_dir]
        def close_window():
            window = next(w for w in QApplication.topLevelWidgets() if isinstance(w, entry.Workspace))
            print("window-x", flush=True)
            window.close()
        def make_app(*args):
            app = QApplication(*args)
            QTimer.singleShot(100, close_window)
            return app
        entry.QApplication = make_app
        result = entry.main()
        print("process-returned", flush=True)
        sys.exit(result)
    ''')
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path), str(tray), str(delay)],
        env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "window-x" in result.stdout and "process-returned" in result.stdout
    if "failure" not in str(delay):
        assert "graceful-shutdown" in result.stdout and "resources-closed" in result.stdout
