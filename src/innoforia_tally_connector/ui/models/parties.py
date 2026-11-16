from PySide6.QtCore import QAbstractTableModel, Qt


class TableModel(QAbstractTableModel):
    def __init__(self, headers):
        super().__init__()
        self.headers, self.rows, self.objects = headers, [], []

    def replace(self, rows, objects=()):
        self.beginResetModel()
        self.rows, self.objects = list(rows), list(objects)
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return str(self.rows[index.row()][index.column()])

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]

    def selected(self, view):
        indices = view.selectionModel().selectedRows()
        return self.objects[indices[0].row()] if len(indices) == 1 and self.objects else None


class PartyTableModel(TableModel):
    """Allow Qt to initiate our internal row drag; never edit or move rows."""

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and index.row() < len(self.objects):
            flags |= Qt.ItemFlag.ItemIsDragEnabled
            if index.column() == 0:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction
    def __init__(self, headers):
        super().__init__(headers)
        self.checked = set()

    def replace(self, rows, objects=()):
        self.checked.clear()
        super().replace(rows, objects)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole and index.row() < len(self.objects):
            return Qt.CheckState.Checked if self.objects[index.row()].identity in self.checked else Qt.CheckState.Unchecked
        return super().data(index, role)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole and index.row() < len(self.objects):
            identity = self.objects[index.row()].identity
            if value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value): self.checked.add(identity)
            else: self.checked.discard(identity)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def selected_many(self, view):
        if self.checked:
            return tuple(r for r in self.objects if r.identity in self.checked)
        return tuple(self.objects[i.row()] for i in sorted(view.selectionModel().selectedRows(), key=lambda i: i.row()))
