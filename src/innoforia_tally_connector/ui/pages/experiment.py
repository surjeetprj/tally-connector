"""Explicit direction, immutable generated preview, one approval and read-only results."""
from datetime import datetime, timezone
import json

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from innoforia_tally_connector.domain.experiments import Direction


class ExperimentPage(QWidget):
    def __init__(self, send, parent=None):
        super().__init__(parent)
        self.send, self.record, self.bound, self.working = send, None, False, False
        layout = QVBoxLayout(self)
        label = QLabel("ONE SYNTHETIC SUPPLIER · Destination-only test · No source ID or mapping is created.\n"
                       "Creation requires approval of the exact record. Existing parties and invoice 69 are not changed.")
        label.setWordWrap(True)
        layout.addWidget(label)
        controls = QHBoxLayout()
        self.direction = QComboBox()
        self.direction.addItem("Select direction — no default", None)
        self.direction.addItem("Bahi → Tally — destination test in SIS Dummy", Direction.TO_TALLY)
        self.direction.addItem("Tally → Bahi — destination test in business 52", Direction.TO_BAHI)
        self.prepare = QPushButton("Prepare preview (reads only)")
        self.inspect = QPushButton("Inspect last experiment")
        controls.addWidget(self.direction, 1)
        controls.addWidget(self.prepare)
        controls.addWidget(self.inspect)
        layout.addLayout(controls)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)
        action = QHBoxLayout()
        self.reviewer = QLineEdit()
        self.reviewer.setPlaceholderText("Creation reviewer — required")
        self.approve = QPushButton("Approve and create this test supplier…")
        self.reconcile = QPushButton("Read-only reconciliation")
        for widget in (self.reviewer, self.approve, self.reconcile):
            action.addWidget(widget)
        layout.addLayout(action)
        self.direction.currentIndexChanged.connect(self.direction_changed)
        self.prepare.clicked.connect(self.prepare_preview)
        self.inspect.clicked.connect(lambda: self.send("EXP_STATUS"))
        self.approve.clicked.connect(self.approve_create)
        self.reconcile.clicked.connect(self.read_only_reconcile)
        self.set_busy(False, False)

    def set_busy(self, busy, bound):
        self.working, self.bound = busy, bound
        self.direction.setEnabled(bound and not busy)
        self.prepare.setEnabled(bound and not busy and self.direction.currentData() is not None)
        self.inspect.setEnabled(bound and not busy)
        current = self.record
        fresh = current is not None and current.preview.created_at <= datetime.now(timezone.utc) <= current.preview.expires_at
        self.approve.setEnabled(bound and not busy and fresh and current.state == "PENDING" and not current.attempted
                                and current.preview.direction == self.direction.currentData())
        self.reconcile.setEnabled(bound and not busy and current is not None and current.attempted and current.target is not None)

    def direction_changed(self):
        self.record = None
        self.report.setPlainText("Direction changed. Prepare and review a new preview; no creation has been approved.")
        self.set_busy(self.working, self.bound)

    def prepare_preview(self):
        if self.direction.currentData() is None:
            return
        self.send("EXP_PREPARE", direction=Direction(self.direction.currentData()))

    def receive(self, event):
        if event.error:
            self.record = None
            self.report.setPlainText(event.error + "\nInspect the last experiment before preparing another creation.")
            return
        self.record = event.result
        if self.record is None:
            self.report.setPlainText("No experiment is stored for this binding. Choose a direction and prepare a preview.")
            return
        record, preview = self.record, self.record.preview
        states = {"PENDING": "Prepared — awaiting explicit approval", "SUCCEEDED": "Verified",
            "OUTCOME_UNKNOWN": "Outcome unknown — do not create again", "VERIFYING": "Verification pending — reads only",
            "BLOCKED": "Needs review — no correction/recreation enabled", "FAILED": "Creation refused"}
        context = json.loads(preview.preflight.group_context)
        group = context.get("group")
        group_text = f"{group['NAME']} ({group['GUID']})" if isinstance(group, dict) else str(group)
        lines = [states.get(record.state, "Execution / reconciliation in progress"),
            f"Experiment: {preview.id}", f"Direction: {preview.direction.value.replace('_', ' ')} (synthetic input only)",
            f"Destination: {preview.preflight.destination}", f"Group: {group_text}", "Type: SUPPLIER",
            f"Name: {preview.party.name}", f"Email: {preview.party.email}",
            "Omitted: phone, address, GST/PAN, opening balances and accounting values.",
            f"Approval expires: {preview.expires_at.isoformat()}",
            f"Create attempt already recorded: {'Yes' if record.attempted else 'No'}"]
        if record.reviewer:
            lines.append(f"Creation reviewer: {record.reviewer}")
        if record.target:
            lines.append(f"Saved destination identity/receipt: {record.target.identity or 'Positive create receipt; exact new GUID export pending'}")
        if record.comparisons:
            lines.extend(f"{field.replace('_', ' ').title()}: {'matches' if match else 'DIFFERS'}" for field, match in record.comparisons.items())
        if record.observation:
            lines += [f"Read-back name: {record.observation.content.name}", f"Read-back email: {record.observation.content.email}"]
        lines += [record.message, "No automatic retry or remote cleanup is enabled."]
        self.report.setPlainText("\n".join(lines))

    def approve_create(self):
        record = self.record
        if record is None or record.attempted:
            return
        reviewer = self.reviewer.text().strip()
        if not reviewer:
            QMessageBox.information(self, "Reviewer required", "Enter the reviewer approving this exact remote creation.")
            return
        answer = QMessageBox.question(self, "Approve one remote supplier creation", self.report.toPlainText()
            + f"\n\nReviewer: {reviewer}\nCreate exactly this supplier once in the shown destination?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.send("EXP_CREATE", experiment_id=record.preview.id, direction=Direction(self.direction.currentData()),
                      approval_digest=record.preview.digest, reviewer=reviewer)

    def read_only_reconcile(self):
        if self.record and self.record.attempted and self.record.target:
            self.send("EXP_RECONCILE", experiment_id=self.record.preview.id)
