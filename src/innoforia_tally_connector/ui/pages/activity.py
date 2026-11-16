"""Paged history includes legacy experiments and all real transfer outcomes."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QTableView
from innoforia_tally_connector.ui.models.parties import TableModel


class ActivityPage(QWidget):
    def __init__(self, send):
        super().__init__()
        self.send, self.offset, self.more, self.selected_id = send, 0, False, None
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.status, self.kind = QComboBox(), QComboBox()
        self.status.addItem("All statuses", None)
        for state in ("PENDING", "SUCCEEDED", "CANCELLED", "FAILED", "BLOCKED", "OUTCOME_UNKNOWN", "VERIFYING", "RECONCILING", "APPLYING"):
            self.status.addItem(state.title().replace('_', ' '), state)
        self.kind.addItem("Transfers and legacy experiments", None)
        self.kind.addItem("Transfers", "TRANSFER")
        self.kind.addItem("Legacy experiments", "EXPERIMENT")
        self.refresh = QPushButton("Refresh activity")
        self.previous, self.next = QPushButton("Previous"), QPushButton("Next")
        self.inspect = QPushButton("Inspect selected activity")
        for widget in (self.status, self.kind, self.refresh, self.previous, self.next, self.inspect):
            controls.addWidget(widget)
        layout.addLayout(controls)
        self.model = TableModel(["Prepared UTC", "Kind", "Status", "Direction", "Party", "Destination ID", "Reviewer"])
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.view.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.view)
        self.refresh.clicked.connect(lambda: self.load(0))
        self.previous.clicked.connect(lambda: self.load(max(0, self.offset - 50)))
        self.next.clicked.connect(lambda: self.load(self.offset + 50))
        self.inspect.clicked.connect(self.inspect_record)
        self.view.doubleClicked.connect(lambda *_: self.inspect_record())
        self.view.selectionModel().selectionChanged.connect(self.remember_selection)
        self.set_busy(False, False)

    def remember_selection(self, *_):
        record = self.model.selected(self.view)
        if record:
            self.selected_id = record.preview.id

    def load(self, offset):
        self.send("ACTIVITY", offset=offset, status_filter=self.status.currentData(), type_filter=self.kind.currentData())

    def receive(self, page):
        selected = self.selected_id
        self.offset, self.more = page.offset, page.has_more
        self.model.replace([(r.preview.created_at.isoformat(), r.preview.kind, r.state, r.preview.direction,
            r.preview.party.name, r.target.identity if r.target else "", r.reviewer or "") for r in page.records], page.records)
        for row, record in enumerate(page.records):
            if record.preview.id == selected:
                self.view.selectRow(row)
                break

    def inspect_record(self):
        record = self.model.selected(self.view)
        if record:
            self.send("ACTIVITY_DETAIL", experiment_id=record.preview.id)

    def set_busy(self, busy, bound):
        for widget in (self.refresh, self.inspect, self.status, self.kind):
            widget.setEnabled(bound and not busy)
        self.previous.setEnabled(bound and not busy and self.offset > 0)
        self.next.setEnabled(bound and not busy and self.more)
