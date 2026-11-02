from PySide6.QtCore import QObject, Signal


class Bridge(QObject):
    event = Signal(object)
