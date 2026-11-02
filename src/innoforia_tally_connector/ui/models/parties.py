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
