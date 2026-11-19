"""One compact approval for the exact ready subset; details remain inspectable."""
from datetime import datetime, timezone
import json
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QSplitter, QTextEdit, QCheckBox, QPushButton)
from innoforia_tally_connector.domain.batches import BatchApproval
from innoforia_tally_connector.ui.models.parties import TableModel

LABELS = {"PENDING": "Queued", "APPLYING": "Transferring", "SUCCEEDED": "Transferred",
    "FAILED": "Failed", "BLOCKED": "Needs review", "VERIFYING": "Verification pending",
    "RECONCILING": "Checking result", "OUTCOME_UNKNOWN": "Outcome uncertain", "CANCELLED": "Not transferred"}


class BatchReview(QDialog):
    def __init__(self, parent, send, link):
        super().__init__(parent)
        self.send, self.link = send, link
        self.batch = None
        self.awaiting = False
        self.generation = None
        self.setWindowTitle("Review party transfers")
        self.resize(1050, 720)
        self.setMinimumSize(750, 500)
        layout = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        split = QSplitter(Qt.Orientation.Vertical)
        self.model = TableModel(["Party", "Type", "Status", "Details / omissions"])
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.view.setColumnWidth(0, 260)
        self.view.setColumnWidth(2, 130)
        self.view.horizontalHeader().setStretchLastSection(True)
        split.addWidget(self.view)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        split.addWidget(self.details)
        split.setSizes([360, 180])
        layout.addWidget(split, 1)
        self.candidates = QTableView()
        self.candidate_model = TableModel(["Existing destination party", "Type", "Identity"])
        self.candidates.setModel(self.candidate_model)
        self.candidates.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.candidates.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.candidates.setMaximumHeight(130)
        self.candidates.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.candidates)
        self.link_button = QPushButton("Review selected existing link")
        layout.addWidget(self.link_button)
        self.normal = QCheckBox("I confirm all Ready sources with unavailable system flags are normal, non-system business parties.")
        layout.addWidget(self.normal)
        actions = QHBoxLayout()
        self.confirm = QPushButton("Confirm transfer")
        self.cancel = QPushButton("Stop unsent transfers")
        self.close_button = QPushButton("Close")
        self.activity = QPushButton("Open Activity")
        for widget in (self.confirm, self.cancel, self.activity, self.close_button): actions.addWidget(widget)
        layout.addLayout(actions)
        self.view.selectionModel().selectionChanged.connect(self.inspect)
        self.candidates.selectionModel().selectionChanged.connect(self.inspect_candidate)
        self.link_button.clicked.connect(self.link_selected)
        self.normal.toggled.connect(self.update_actions)
        self.confirm.clicked.connect(self.approve)
        self.cancel.clicked.connect(lambda: self.send("BATCH_CANCEL", batch_id=self.batch.id))
        self.close_button.clicked.connect(self.close)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_actions)
        self.timer.start(1000)

    def receive(self, batch, generation):
        self.awaiting = False
        self.error.hide()
        previous = self.model.selected(self.view)
        self.batch, self.generation = batch, generation
        self.normal.setChecked(False)
        ready = [i for i in batch.items if i.status == "Ready"]
        self.normal.setVisible(any(i.preview.source_confirmation_required for i in ready))
        totals = {status: sum(i.status == status for i in batch.items) for status in {i.status for i in batch.items}}
        self.summary.setText(f"{batch.direction.value.replace('_', ' ')} · Operator: {batch.policy.operator} · Policy v{batch.policy.version}\n"
            f"{batch.state}: " + "; ".join(f"{count} {status}" for status, count in sorted(totals.items())) +
            "\nOnly Ready records are approved. All applicable supported fields are included; any omissions have specific reasons. Select a row to inspect exact fields and destination.")
        rows = []
        for item in batch.items:
            omissions = ", ".join(d.field for d in item.preview.decisions if d.status == "excluded") if item.preview else ""
            rows.append((item.source.content.name, item.source.party_type, LABELS.get(item.status, item.status),
                item.message or ("Omitted: " + omissions if omissions else "")))
        self.model.replace(rows, batch.items)
        self.candidates.hide()
        self.link_button.hide()
        if batch.items:
            row = next((n for n, i in enumerate(batch.items) if previous and i.source.identity == previous.source.identity), 0)
            self.view.selectRow(row)
        self.update_actions()

    def fresh(self):
        return self.batch and self.batch.generation == self.generation and all(
            i.preview.created_at <= datetime.now(timezone.utc) <= i.preview.expires_at
            for i in self.batch.items if i.status == "Ready")

    def update_actions(self, *_):
        batch = self.batch
        pending = batch is not None and batch.state == "PENDING"
        ready = [i for i in batch.items if i.status == "Ready"] if batch else []
        fresh = self.fresh()
        required = any(i.preview.source_confirmation_required for i in ready)
        self.confirm.setText("Confirm transfer" if fresh else "Refresh summary for review")
        self.confirm.setEnabled(bool(not self.awaiting and pending and ready and (not fresh or not required or self.normal.isChecked())))
        self.cancel.setEnabled(bool(batch and batch.state in {"PENDING", "APPLYING"}))

    def approve(self):
        self.update_actions()
        if not self.confirm.isEnabled(): return
        self.awaiting = True
        if not self.fresh():
            sources = tuple(i.source for i in self.batch.items if not i.result or not i.result.attempted)
            self.send("BATCH_PREPARE", sources=sources, direction=self.batch.direction)
        else:
            approval = BatchApproval(batch_id=self.batch.id, digest=self.batch.digest,
                ready_ids=tuple(i.preview.id for i in self.batch.items if i.status == "Ready"),
                normal_confirmed=self.normal.isChecked())
            self.send("BATCH_APPROVE", approval=approval)
        self.confirm.setEnabled(False)

    def inspect(self, *_):
        item = self.model.selected(self.view)
        if item is None: return
        lines = [f"Source {item.source.side} {item.source.identity}: {item.source.content.name}", item.message]
        if item.preview:
            p = item.preview
            lines += [f"Destination: {p.preflight.destination}", f"Group: {p.preflight.group_context}",
                f"Exact included fields: {p.party.model_dump(exclude_unset=True)!r}", f"Approval expiry: {p.expires_at.isoformat()}"]
            context = json.loads(p.preflight.group_context)
            if context.get('gst_applicable_from'):
                lines.append(f"Initial GST applicability: {context['gst_applicable_from']} (destination company Books From; included in this approval)")
            lines += [f"{d.field}: {d.status} — {d.reason}" for d in p.decisions]
        if item.result:
            lines += [f"Create attempt: {'recorded' if item.result.attempted else 'not sent'}",
                f"Destination identity: {item.result.target}", f"Read-back comparisons: {item.result.comparisons}",
                f"Reviewer: {item.result.reviewer}; confirmed normal source despite unavailable system flag: {item.result.source_normal_party_confirmed}"]
        self.details.setPlainText("\n".join(lines))
        self.candidate_model.replace([(r.content.name, r.party_type, r.identity) for r in item.candidates], item.candidates)
        self.candidates.setVisible(bool(item.candidates))
        self.link_button.setVisible(bool(item.candidates))
        self.link_button.setEnabled(False)

    def inspect_candidate(self, *_):
        item, target = self.model.selected(self.view), self.candidate_model.selected(self.candidates)
        if not item or not target: return
        self.details.setPlainText(f"Source: {item.source.content.model_dump(exclude_unset=True)!r}\n"
            f"Destination: {target.content.model_dump(exclude_unset=True)!r}\nIdentity link only; no field updates.")
        self.link_button.setEnabled(item.source.party_type == target.party_type and target.is_active is not False
            and target.is_system is not True and self.batch.state == "PENDING")

    def link_selected(self):
        item, target = self.model.selected(self.view), self.candidate_model.selected(self.candidates)
        if item and target: self.link(item.source, target)
