"""Internal, single-row drag references. A drop dispatches review, never a write."""
from uuid import uuid4
from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QLabel, QTableView, QAbstractItemView

MIME = "application/x-innoforia-party-reference"


class DragSession:
    def __init__(self):
        self.references = {}
        self.binding = None
        self.generation = None

    def reset(self, binding, generation):
        self.references.clear()
        self.binding, self.generation = binding, generation

    def issue(self, view, source):
        sources = source if isinstance(source, tuple) else (source,)
        if not 1 <= len(sources) <= 100 or any(s.binding != self.binding or s.is_active is False or s.is_system is True for s in sources):
            raise ValueError("Party is not eligible for transfer")
        token = uuid4().hex
        self.references[token] = (view, source, self.generation)
        mime = QMimeData()
        mime.setData(MIME, token.encode())
        return mime

    def resolve(self, mime, origin, destination_side):
        if not mime.hasFormat(MIME):
            return None
        item = self.references.get(bytes(mime.data(MIME)).decode("ascii", errors="replace"))
        if not item:
            return None
        view, source, generation = item
        sources = source if isinstance(source, tuple) else (source,)
        if view is not origin or generation != self.generation or any(s.binding != self.binding or s.side == destination_side for s in sources):
            return None
        if any(s not in view.model().objects for s in sources):
            return None
        return source


class PartyView(QTableView):
    review = Signal(object, object)

    def __init__(self, side, session):
        super().__init__()
        self.side, self.session = side, session
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def startDrag(self, actions):
        sources = self.model().selected_many(self)
        if not 1 <= len(sources) <= 100:
            return
        source = sources[0] if len(sources) == 1 else sources
        try:
            mime = self.session.issue(self, source)
        except ValueError:
            return
        token = bytes(mime.data(MIME)).decode()
        drag = QDrag(self)
        drag.setMimeData(mime)
        try:
            drag.exec(Qt.DropAction.CopyAction)
        finally:
            self.session.references.pop(token, None)

    def dragEnterEvent(self, event):
        if self.session.resolve(event.mimeData(), event.source(), self.side):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        source = self.session.resolve(event.mimeData(), event.source(), self.side)
        index = self.indexAt(event.position().toPoint())
        if source and not isinstance(source, tuple) and index.isValid():
            target = self.model().objects[index.row()]
            if source.party_type == target.party_type and target.is_active is not False and target.is_system is not True:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
                self.review.emit(source, target)
                return
        event.ignore()


class CreateDropArea(QLabel):
    review = Signal(object, object)

    def __init__(self, side, session):
        super().__init__(f"Drop here to prepare a NEW party in {side.title()} — approval required")
        self.side, self.session = side, session
        self.setAcceptDrops(True)
        self.setMargin(10)
        self.setStyleSheet("QLabel { border: 1px dashed #777; }")
        self.setWordWrap(True)

    def dragEnterEvent(self, event):
        if self.session.resolve(event.mimeData(), event.source(), self.side):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        source = self.session.resolve(event.mimeData(), event.source(), self.side)
        if source:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.review.emit(source, None)
        else:
            event.ignore()
