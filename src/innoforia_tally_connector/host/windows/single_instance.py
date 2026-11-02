from PySide6.QtCore import QLockFile


def acquire(directory):
    lock = QLockFile(str(directory / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise ValueError("Connector is already running or its runtime directory is unavailable")
    return lock
