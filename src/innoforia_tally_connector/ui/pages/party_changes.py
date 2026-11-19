"""Linked changes and approved supplier State updates with durable results."""
from collections import Counter
from datetime import datetime, timezone
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableView, QTextEdit, QPushButton, QHeaderView, QLineEdit, QCheckBox, QScrollArea, QWidget
from innoforia_tally_connector.ui.models.parties import TableModel
from innoforia_tally_connector.domain.experiments import Direction


def display(value):
    if value.availability != "present":
        return f"[{value.availability}]"
    return value.value


class PartyChangesDialog(QDialog):
    def __init__(self, parent, send=lambda *_args, **_kwargs: None):
        super().__init__(parent)
        self.send, self.review, self.record = send, None, None
        self.busy = False
        self.generation = None
        self.setWindowTitle("Review linked Bahi → Tally changes")
        self.resize(1100, 650)
        self.setMinimumSize(550, 350)
        outer = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll, 1)
        self.identity, self.summary = QLabel(), QLabel()
        self.identity.setWordWrap(True); self.summary.setWordWrap(True)
        layout.addWidget(self.identity)
        layout.addWidget(self.summary)
        note = QLabel("Review and approve supplier State changes from Bahi to Tally. Other fields are shown for review. "
            "Tally edits require review; no update is sent automatically.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.model = TableModel(["Field", "Bahi now", "Tally now", "Review"])
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.view.setWordWrap(False)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.view, 1)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(180)
        layout.addWidget(self.details)
        self.prepare = QPushButton("Review State update…")
        self.prepare.clicked.connect(self.prepare_update)
        layout.addWidget(self.prepare)
        self.result = QLabel()
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        self.reviewer = QLineEdit()
        self.reviewer.setPlaceholderText("Approving operator")
        layout.addWidget(self.reviewer)
        self.normal = QCheckBox("I confirm these are normal business parties and no other editor will change this ledger during the update.")
        layout.addWidget(self.normal)
        self.approve = QPushButton("Confirm State update")
        self.approve.clicked.connect(self.approve_update)
        outer.addWidget(self.approve)
        self.reconcile = QPushButton("Verify saved update (reads only)")
        self.reconcile.clicked.connect(lambda: self.submit("UPDATE_RECONCILE"))
        self.cancel = QPushButton("Cancel unsent update")
        self.cancel.clicked.connect(lambda: self.submit("UPDATE_CANCEL"))
        self.restore = QPushButton("Load latest State update")
        self.restore.clicked.connect(self.load_latest)
        for button in (self.reconcile, self.cancel, self.restore): layout.addWidget(button)
        self.refresh = QPushButton("Refresh changes")
        self.refresh.clicked.connect(self.refresh_changes)
        layout.addWidget(self.refresh)
        self.normal.toggled.connect(self.actions)
        self.reviewer.textChanged.connect(self.actions)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        outer.addWidget(close)
        self.view.selectionModel().selectionChanged.connect(self.inspect)

    def clear(self):
        self.hide()
        self.model.replace([])
        self.details.clear()
        self.identity.clear(); self.summary.clear()
        self.review = self.record = None
        self.result.clear(); self.normal.setChecked(False)
        self.actions()

    def receive(self, review):
        self.review, self.record = review, None
        self.result.clear(); self.normal.setChecked(False)
        self.identity.setText(f"Bahi {review.bahi.identity}: {review.bahi.content.name} → "
            f"Tally {review.tally.identity}: {review.tally.content.name}\n"
            f"Observed Bahi {review.bahi.observed_at.isoformat()} | Tally {review.tally.observed_at.isoformat()}\n"
            "State uses the last verified update when available; other saved values remain the original linking observations.")
        self.summary.setText(" | ".join(f"{count} {status}" for status, count in Counter(f.status for f in review.fields).items()) +
            ("\n" + "; ".join(review.blockers) if review.blockers else ""))
        self.model.replace([(f.field, display(f.current_bahi), display(f.current_tally), f.status) for f in review.fields], review.fields)
        self.details.clear()
        if self.model.rowCount(): self.view.selectRow(0)
        self.actions()
        self.load_latest()

    def actions(self, *_):
        candidate = self.review and not self.review.blockers and self.review.bahi.party_type.value == "SUPPLIER" and any(f.field == "state" and f.status == "Bahi changed" for f in self.review.fields)
        unresolved = self.record and self.record.state not in {"SUCCEEDED", "FAILED", "CANCELLED"} and self.record.attempted
        self.prepare.setEnabled(bool(candidate) and not unresolved and not self.busy)
        pending = self.record and self.record.state == "PENDING" and not self.record.attempted
        current = pending and self.record.preview.generation == self.generation
        self.approve.setEnabled(bool(current) and self.normal.isChecked() and bool(self.reviewer.text().strip()) and not self.busy)
        self.cancel.setEnabled(bool(pending) and not self.busy)
        self.reconcile.setEnabled(bool(self.record and self.record.attempted and self.record.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}) and not self.busy)
        self.restore.setEnabled(not self.busy)
        self.refresh.setEnabled(bool(self.review) and not self.busy)

    def load_latest(self):
        identity = self.review.bahi.identity if self.review else self.record.preview.source.identity if self.record else None
        self.send("UPDATE_STATUS", party_identity=identity)

    def refresh_changes(self):
        if self.review: self.send("PARTY_CHANGES", party_identity=self.review.bahi.identity)

    def prepare_update(self):
        if self.review:
            self.normal.setChecked(False)
            self.send("UPDATE_PREPARE", party_identity=self.review.bahi.identity)

    def submit(self, kind):
        if self.record: self.send(kind, experiment_id=self.record.preview.id)

    def approve_update(self):
        if not self.record or not self.approve.isEnabled(): return
        p = self.record.preview
        if datetime.now(timezone.utc) > p.expires_at:
            self.result.setText("Preview expired. Prepare again and renew approval; no update sent.")
            self.normal.setChecked(False)
            return
        from innoforia_tally_connector.ui.confirmations import confirm_plain
        if not confirm_plain(self, "Confirm State update", self.result.text() +
            f"\nReviewer: {self.reviewer.text().strip()}\nSend once? Retain the record; no automatic retry."): return
        self.send("UPDATE_APPLY", experiment_id=p.id, direction=Direction.TO_TALLY,
            approval_digest=p.digest, reviewer=self.reviewer.text().strip(), source_normal_party_confirmed=self.normal.isChecked())

    def show_update(self, record, operator=""):
        if record and self.review and record.preview.source.identity != self.review.bahi.identity:
            self.review = None
            self.model.replace([]); self.details.clear(); self.identity.clear(); self.summary.clear()
        self.record = record
        self.normal.setChecked(False)
        if record is None:
            self.result.setText("No saved State update for this party" if self.review else "No saved State update in this connection")
        else:
            p = record.preview
            before = p.update.before.content
            old = repr(before.state) if "state" in before.model_fields_set else "[absent]"
            self.result.setText(f"State update: {record.state}\nRecord {p.id}\n"
                f"Destination: {p.preflight.destination}\n{before.name} | GUID {p.update.before.identity}\n"
                f"Source: Bahi business {p.binding.business_id}, party {p.source.identity}\n"
                f"State: {old} → {p.party.state!r}\n"
                f"Expected preservation: existing mailing entry/date and all other native fields. Expires {p.expires_at.isoformat()}\n"
                f"Attempt recorded: {record.attempted}. {record.message}\nComparisons: {record.comparisons}")
            self.reviewer.setText(record.reviewer or operator)
        self.actions()

    def inspect(self, *_):
        row = self.model.selected(self.view)
        if row is None: return
        baseline = "last verified State update" if row.field == "state" and self.review.state_acknowledgement else "linking"
        self.details.setPlainText(f"{row.field}: {row.status}\n{row.reason}\n\n"
            f"Bahi at {baseline}: {display(row.saved_bahi)}\nBahi now: {display(row.current_bahi)}\n"
            f"Tally at {baseline}: {display(row.saved_tally)}\nTally now: {display(row.current_tally)}")
