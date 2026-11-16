"""Review actual source fields and explicit exclusions before one approved create."""
from datetime import datetime, timezone
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QTableView, QMessageBox, QCheckBox)
from innoforia_tally_connector.domain.experiments import ExperimentResult
from innoforia_tally_connector.domain.masters import PartyContent, ConfirmedPartyLink
from innoforia_tally_connector.domain.party_transfer import OPTIONAL_FIELDS, TransferReview, field_availability
from innoforia_tally_connector.ui.models.parties import TableModel
from innoforia_tally_connector.ui.confirmations import confirm_plain


class TransferPage(QWidget):
    def __init__(self, send, link_review):
        super().__init__()
        self.send, self.link_review = send, link_review
        self.record, self.source = None, None
        self.working = self.bound = False
        self.generation = None
        layout = QVBoxLayout(self)
        label = QLabel("Transfer one selected customer or supplier. Preview is read-only; creation requires approval.\n"
                       "Aliases, contact person and notes are outside this release. Exclusions remain in the audit.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 2)
        self.activity = QPushButton("Open Activity history to inspect pending or unresolved work")
        layout.addWidget(self.activity)
        self.fields = QTableWidget(0, 5)
        self.fields.setHorizontalHeaderLabels(["Field", "Source value", "Decision", "Include", "Exclusion reason"])
        self.fields.horizontalHeader().setStretchLastSection(True)
        self.fields.setColumnWidth(1, 300)
        layout.addWidget(self.fields, 2)
        self.candidate_model = TableModel(["Existing candidate", "Type", "ID"])
        self.candidates = QTableView()
        self.candidates.setModel(self.candidate_model)
        self.candidates.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.candidates.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.candidates.selectionModel().selectionChanged.connect(self.show_candidate_difference)
        self.candidates.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.candidates)
        self.existing = QPushButton("Review selected existing link…")
        self.existing.clicked.connect(self.review_existing)
        layout.addWidget(self.existing)
        self.normal_party = QCheckBox("System flag is unavailable. I confirm the selected source is a normal, non-system business party.")
        self.normal_party.setChecked(False)
        self.normal_party.setVisible(False)
        self.normal_party.toggled.connect(lambda *_: self.set_busy(self.working, self.bound))
        layout.addWidget(self.normal_party)
        actions = QHBoxLayout()
        self.reviewer = QLineEdit()
        self.reviewer.setPlaceholderText("Approving reviewer — required")
        self.refresh = QPushButton("Apply exclusions / renew preview")
        self.approve = QPushButton("Approve and transfer…")
        self.cancel = QPushButton("Cancel unattempted preview")
        self.reconcile = QPushButton("Reconcile through reads only")
        for widget in (self.reviewer, self.refresh, self.approve, self.cancel, self.reconcile):
            actions.addWidget(widget)
        layout.addLayout(actions)
        self.refresh.clicked.connect(self.renew)
        self.approve.clicked.connect(self.approve_transfer)
        self.cancel.clicked.connect(lambda: self.send("TRANSFER_CANCEL", experiment_id=self.record.preview.id))
        self.reconcile.clicked.connect(self.reconcile_record)
        self.fields.itemChanged.connect(lambda *_: self.set_busy(self.working, self.bound))
        self.set_busy(False, False)

    def clear(self):
        self.record = self.source = None
        self.report.clear()
        self.fields.setRowCount(0)
        self.candidate_model.replace([])
        self.normal_party.setChecked(False)
        self.normal_party.setVisible(False)
        self.set_busy(self.working, self.bound)

    def exclusions(self):
        return {self.fields.item(row, 0).text(): self.fields.item(row, 4).text().strip()
                for row in range(self.fields.rowCount()) if self.fields.item(row, 3).checkState() == Qt.CheckState.Unchecked}

    def set_busy(self, busy, bound):
        self.working, self.bound = busy, bound
        self.activity.setEnabled(bound and not busy)
        record = self.record
        pending = (isinstance(record, ExperimentResult) and record.preview.kind == "TRANSFER"
                   and record.state == "PENDING" and not record.attempted)
        self.fields.setEnabled(not busy and pending)
        self.normal_party.setEnabled(not busy and pending)
        self.refresh.setEnabled(bound and not busy and pending)
        self.cancel.setEnabled(bound and not busy and isinstance(record, ExperimentResult) and record.state == "PENDING" and not record.attempted)
        self.reconcile.setEnabled(bound and not busy and isinstance(record, ExperimentResult) and record.attempted
                                  and record.target is not None and record.state not in {"SUCCEEDED", "FAILED"})
        fresh = (pending and (self.generation is None or self.generation == record.preview.generation)
                 and record.preview.created_at <= datetime.now(timezone.utc) <= record.preview.expires_at)
        valid = pending and not any(d.status in {"invalid", "unavailable"} for d in record.preview.decisions)
        saved_exclusions = {d.field: d.reason for d in record.preview.decisions if d.status == "excluded"} if pending else {}
        confirmed = pending and (not record.preview.source_confirmation_required or self.normal_party.isChecked())
        self.approve.setEnabled(bound and not busy and fresh and valid and confirmed and self.exclusions() == saved_exclusions)
        target = self.candidate_model.selected(self.candidates)
        self.existing.setEnabled(bound and not busy and self.source is not None and target is not None
                                and target.party_type == self.source.party_type and target.is_active is not False and target.is_system is not True)

    def receive(self, event):
        if event.error:
            self.clear()
            if "blocks another preview" in event.error:
                advice = ("Open Activity history, select the earlier operation and inspect it. "
                    "Cancel it only if it is PENDING with no create attempt. "
                    "Attempted or uncertain work must be reconciled through reads; do not create again.")
            elif event.kind == "TRANSFER_PREPARE":
                advice = ("Preview preparation stopped; this action sent no create request. "
                    "For connection/read failures, Verify connections, reopen the confirmed pair, "
                    "Load / Refresh parties and prepare again. For changed source or field evidence, "
                    "reload and review it. Existing activity is retained; do not cancel unrelated work.")
            else:
                advice = ("Inspect the saved operation in Activity history. "
                    "Attempted or uncertain work requires read-only reconciliation; do not create again.")
            self.report.setPlainText(event.error + "\n\n" + advice)
            return
        result = event.result
        self.clear()
        if isinstance(result, TransferReview):
            self.source = result.source
            self.report.setPlainText(result.message)
            if isinstance(result.record, ConfirmedPartyLink):
                link = result.record
                self.report.append(f"Saved link: {link.id}\nBahi {link.bahi.identity}: {link.bahi.content.name}\n"
                                   f"Tally {link.tally.identity}: {link.tally.content.name}\nReviewer: {link.confirmed_by}")
            self.candidate_model.replace([(r.content.name, r.party_type, r.identity) for r in result.candidates], result.candidates)
            return
        if not isinstance(result, ExperimentResult):
            self.report.setPlainText("No saved activity found")
            return
        self.record, self.source = result, result.preview.source
        preview = result.preview
        context = json.loads(preview.preflight.group_context)
        group = context.get("group", preview.preflight.group_context)
        group_text = f"{group.get('NAME', '')} ({group.get('GUID', '')})" if isinstance(group, dict) else group
        lines = [f"{preview.kind}: {result.state}", f"Record: {preview.id}", f"Direction: {preview.direction.value}",
                 f"Destination: {preview.preflight.destination}", f"Group: {group_text}",
                 f"Name: {preview.party.name}", f"Approval expires: {preview.expires_at.isoformat()}",
                 f"Create attempt: {'recorded' if result.attempted else 'not sent'}", result.message]
        if preview.source:
            lines += [f"Source {preview.source.side} ID: {preview.source.identity}", f"Type: {preview.source.party_type}",
                      f"Source observed: {preview.source.observed_at.isoformat()}"]
            lines.extend(f"Required field {d.field}: {d.status} — {d.reason}" for d in preview.decisions
                         if d.field == "name" and d.status != "included")
        else:
            lines.append("Legacy synthetic experiment: no source identity or cross-system mapping.")
        if result.reviewer:
            lines.append(f"Reviewer: {result.reviewer}")
        if preview.source_confirmation_required:
            lines.append("Source system flag unavailable from API. Named reviewer confirmation of normal non-system status is required.")
            if result.attempted:
                lines.append(f"Recorded source eligibility confirmation: {'confirmed by reviewer' if result.source_normal_party_confirmed else 'not recorded'}")
        self.normal_party.setVisible(preview.source_confirmation_required)
        self.normal_party.setChecked(result.source_normal_party_confirmed)
        if result.target:
            lines.append(f"Destination identity: {result.target.kind} {result.target.identity or '[receipt; GUID resolution pending]'}")
        if result.observation:
            lines.append(f"Destination observed: {result.observation.observed_at.isoformat()}")
            lines.extend(f"Read-back {field}: {value!r}" for field, value in result.observation.content.model_dump(exclude_unset=True).items())
        lines.extend(f"{field}: {'matches' if ok else 'DIFFERS'}" for field, ok in result.comparisons.items())
        lines.append("No automatic retry, update or deletion. Destination field support still requires owner manual read-back verification.")
        self.report.setPlainText("\n".join(lines))
        self.fields.blockSignals(True)
        decisions = [d for d in preview.decisions if d.field in OPTIONAL_FIELDS]
        self.fields.setRowCount(len(decisions))
        for row, decision in enumerate(decisions):
            source = preview.source
            value = self.field_text(source, decision.field)
            for col, text in enumerate((decision.field, value, decision.status + (": " + decision.reason if decision.reason else ""), "", decision.reason if decision.status == "excluded" else "")):
                item = QTableWidgetItem(text)
                if col != 4:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.fields.setItem(row, col, item)
            choice = self.fields.item(row, 3)
            choice.setFlags(choice.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            choice.setCheckState(Qt.CheckState.Unchecked if decision.status == "excluded" else Qt.CheckState.Checked)
        self.fields.blockSignals(False)

    def renew(self):
        exclusions = self.exclusions()
        if any(not reason for reason in exclusions.values()):
            QMessageBox.information(self, "Exclusion reason required", "Give a reason for each unchecked field.")
            return
        self.send("TRANSFER_PREPARE", source=self.source, direction=self.record.preview.direction,
                  experiment_id=self.record.preview.id, exclusions=exclusions)

    def approve_transfer(self):
        self.set_busy(self.working, self.bound)
        if not self.approve.isEnabled():
            return
        reviewer = self.reviewer.text().strip()
        if not reviewer:
            QMessageBox.information(self, "Reviewer required", "Enter the reviewer approving this transfer.")
            return
        included = {field: value for field, value in self.record.preview.party.model_dump(exclude_unset=True).items()}
        summary = self.report.toPlainText() + f"\nIncluded values: {included!r}\nExclusions: {self.exclusions()!r}\nReviewer: {reviewer}\n"
        if self.record.preview.source_confirmation_required:
            summary += "Reviewer explicitly confirms a normal, non-system source despite the unavailable API flag.\n"
        summary += "Create once and save the identity mapping after verification?"
        if confirm_plain(self, "Approve and transfer", summary):
            self.send("TRANSFER_CREATE", experiment_id=self.record.preview.id, direction=self.record.preview.direction,
                      approval_digest=self.record.preview.digest, reviewer=reviewer,
                      source_normal_party_confirmed=self.normal_party.isChecked())

    def reconcile_record(self):
        kind = "EXP_RECONCILE" if self.record.preview.kind == "EXPERIMENT" else "TRANSFER_RECONCILE"
        self.send(kind, experiment_id=self.record.preview.id)

    def review_existing(self):
        target = self.candidate_model.selected(self.candidates)
        if target is not None:
            self.link_review(self.source, target, self.reviewer.text().strip())

    @staticmethod
    def field_text(source, field):
        state = field_availability(source, field)
        return f"[{state}]" if state in {"unavailable", "absent", "null"} else repr(getattr(source.content, field))

    def show_candidate_difference(self, *_):
        target = self.candidate_model.selected(self.candidates)
        if self.source is None or target is None:
            return
        lines = ["Existing candidate — identity review only; no remote write.",
                 f"Source {self.source.side} {self.source.identity}: {self.source.content.name}",
                 f"Candidate {target.side} {target.identity}: {target.content.name}",
                 "Link an existing compatible party or cancel; candidate dismissal cannot enable creation."]
        if self.source.party_type != target.party_type:
            lines.append("Classifications differ; this pair cannot be linked.")
        lines.extend(f"{field}: source {self.field_text(self.source, field)} | candidate {self.field_text(target, field)}"
                     for field in PartyContent.model_fields)
        self.report.setPlainText("\n".join(lines))
        self.set_busy(self.working, self.bound)
