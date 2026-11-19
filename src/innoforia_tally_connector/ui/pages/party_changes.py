"""Linked-party field review, approval and durable results."""
from collections import Counter
from datetime import datetime, timezone
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableView, QTextEdit, QPushButton, QHeaderView, QLineEdit, QCheckBox, QScrollArea, QWidget
from innoforia_tally_connector.ui.models.parties import TableModel
from innoforia_tally_connector.domain.experiments import Direction
from innoforia_tally_connector.domain.party_changes import PARTY_UPDATE_FIELDS, GST_UPDATE_FIELDS


class UpdateFieldsModel(TableModel):
    def __init__(self, headers, automatic=False):
        super().__init__(headers)
        self.automatic = automatic
        self.checked = set()
        self.reverse = False

    def replace(self, rows, objects=()):
        super().replace(rows, objects)
        self.checked = {f.field for f in self.objects if f.status == ('Tally changed' if self.reverse else 'Bahi changed') and f.field in PARTY_UPDATE_FIELDS and f.field not in {'pan', *GST_UPDATE_FIELDS}}
        if self.automatic:
            self.checked = {f.field for f in self.objects if f.field in PARTY_UPDATE_FIELDS and f.field not in GST_UPDATE_FIELDS
                and (f.current_tally if self.reverse else f.current_bahi).availability=='present' and f.status in {('Tally changed' if self.reverse else 'Bahi changed'),'Fill missing destination'}}
            tax = [f for f in self.objects if f.field in GST_UPDATE_FIELDS]
            if self.reverse:
                self.checked.update(f.field for f in tax if f.current_tally.availability == 'present'
                    and f.status in {'Tally changed', 'Fill missing destination'})
                companion = next((f for f in tax if f.field == 'gst_reg_type'), None)
                if 'gstin' in self.checked:
                    if companion and companion.current_tally.availability == 'present' and companion.status in {'Tally changed', 'Fill missing destination', 'Already matches'}:
                        self.checked.add('gst_reg_type')
                    else:
                        self.checked.discard('gstin')
            elif len(tax)==2 and all(f.current_bahi.availability=='present' and f.status in {'Bahi changed','Fill missing destination','Already matches'} for f in tax) and any(f.status!='Already matches' for f in tax):
                self.checked.update(GST_UPDATE_FIELDS)

    def flags(self,index):
        result = super().flags(index)
        if self.automatic: return result
        if index.isValid() and index.column()==0 and self.objects[index.row()].field in GST_UPDATE_FIELDS:
            tax = [f for f in self.objects if f.field in GST_UPDATE_FIELDS]
            if len(tax)==2 and all((f.current_tally if self.reverse else f.current_bahi).availability=='present' and f.status in {('Tally changed' if self.reverse else 'Bahi changed'),'Fill missing destination','Already matches'} for f in tax) and any(f.status != 'Already matches' for f in tax):
                result |= Qt.ItemFlag.ItemIsUserCheckable
            return result
        if index.isValid() and index.column()==0 and self.objects[index.row()].field in PARTY_UPDATE_FIELDS and self.objects[index.row()].status in {('Tally changed' if self.reverse else 'Bahi changed'),'Fill missing destination'}:
            result |= Qt.ItemFlag.ItemIsUserCheckable
        return result

    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if self.automatic and role==Qt.ItemDataRole.CheckStateRole: return None
        if index.isValid() and index.column()==0 and role==Qt.ItemDataRole.CheckStateRole and self.objects[index.row()].field in PARTY_UPDATE_FIELDS:
            return Qt.CheckState.Checked if self.objects[index.row()].field in self.checked else Qt.CheckState.Unchecked
        return super().data(index,role)

    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if role!=Qt.ItemDataRole.CheckStateRole or not (self.flags(index)&Qt.ItemFlag.ItemIsUserCheckable): return False
        field = self.objects[index.row()].field
        fields = set(GST_UPDATE_FIELDS) if field in GST_UPDATE_FIELDS else {field}
        if value in (Qt.CheckState.Checked,Qt.CheckState.Checked.value): self.checked.update(fields)
        else: self.checked.difference_update(fields)
        self.dataChanged.emit(self.index(0,0),self.index(self.rowCount()-1,0),[role]); return True


def display(value):
    if value.availability != "present":
        return f"[{value.availability}]"
    return value.value


class PartyChangesDialog(QDialog):
    def __init__(self, parent, send=lambda *_args, **_kwargs: None, *, automatic=True):
        super().__init__(parent)
        self.send, self.review, self.record = send, None, None
        self.busy = False
        self.automatic = automatic
        self.direction = Direction.TO_TALLY
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
        self.note = note = QLabel("Supported eligible Bahi changes are included automatically, including PAN and paired GST fields. Review once and confirm the update. "
            "GST needs both source values (Regular or Composition) and an effective date. Earlier entries are preserved. "
            "Conflicts, clears and rename cannot be overwritten.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.model = UpdateFieldsModel(["Field", "Bahi now", "Tally now", "Review"], automatic=automatic)
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
        self.effective_date = QLineEdit()
        self.effective_date.setPlaceholderText('Effective date for first mailing entry: YYYY-MM-DD (leave blank to preserve existing details)')
        layout.addWidget(self.effective_date)
        self.gst_date = QLineEdit()
        self.gst_date.setPlaceholderText('GST registration effective date: YYYY-MM-DD (required for GST; earlier history is preserved)')
        layout.addWidget(self.gst_date)
        self.accept_missing = QCheckBox('I approve filling the selected blank destination fields that differed before this update.')
        self.accept_missing.toggled.connect(self.actions)
        layout.addWidget(self.accept_missing)
        self.accept_missing.setVisible(not automatic)
        self.prepare = QPushButton("Review all eligible changes…")
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
        self.approve = QPushButton("Confirm update")
        self.approve.clicked.connect(self.approve_update)
        outer.addWidget(self.approve)
        self.reconcile = QPushButton("Verify saved update (reads only)")
        self.reconcile.clicked.connect(lambda: self.submit("UPDATE_RECONCILE"))
        self.cancel = QPushButton("Cancel unsent update")
        self.cancel.clicked.connect(lambda: self.submit("UPDATE_CANCEL"))
        self.restore = QPushButton("Load latest party update")
        self.restore.clicked.connect(self.load_latest)
        for button in (self.reconcile, self.cancel, self.restore): layout.addWidget(button)
        self.close_failed = QPushButton('Close unchanged failed update (reads only)')
        self.close_failed.clicked.connect(self.close_failed_update)
        layout.addWidget(self.close_failed)
        self.refresh = QPushButton("Refresh changes")
        self.refresh.clicked.connect(self.refresh_changes)
        layout.addWidget(self.refresh)
        self.normal.toggled.connect(self.actions)
        self.reviewer.textChanged.connect(self.actions)
        self.effective_date.textChanged.connect(self.actions)
        self.gst_date.textChanged.connect(self.actions)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        outer.addWidget(close)
        self.view.selectionModel().selectionChanged.connect(self.inspect)
        self.model.dataChanged.connect(self.actions)

    def clear(self):
        self.hide()
        self.model.replace([])
        self.details.clear()
        self.identity.clear(); self.summary.clear()
        self.review = self.record = None
        self.result.clear(); self.normal.setChecked(False)
        self.accept_missing.setChecked(self.automatic)
        self.effective_date.clear()
        self.gst_date.clear()
        self.actions()

    @property
    def source_identity(self):
        if self.review:
            return self.review.tally.identity if self.direction == Direction.TO_BAHI else self.review.bahi.identity
        return self.record.preview.source.identity if self.record else None

    def receive(self, review):
        self.direction = Direction(review.direction)
        reverse = self.direction == Direction.TO_BAHI
        self.model.reverse = reverse
        self.setWindowTitle('Review linked Tally → Bahi changes' if reverse else 'Review linked Bahi → Tally changes')
        self.effective_date.setVisible(not reverse)
        self.gst_date.setVisible(not reverse)
        self.close_failed.setVisible(not reverse)
        self.note.setText('Supported eligible changes are included automatically. Review exact old/new values and confirm once. '
            + ('Bahi receives current scalar values; Tally tax and mailing histories are not copied. ' if reverse else 'Tally GST changes require an effective date. ')
            + 'Conflicts, invalid values, clears and rename remain excluded.')
        if self.review is None or self.review.bahi.identity != review.bahi.identity:
            self.effective_date.clear()
            self.gst_date.clear()
        self.review, self.record = review, None
        self.result.clear(); self.normal.setChecked(False)
        self.accept_missing.setChecked(self.automatic)
        origin, target = (review.tally, review.bahi) if reverse else (review.bahi, review.tally)
        self.identity.setText(f"{origin.side.title()} {origin.identity}: {origin.content.name} → "
            f"{target.side.title()} {target.identity}: {target.content.name}\n"
            f"Observed Bahi {review.bahi.observed_at.isoformat()} | Tally {review.tally.observed_at.isoformat()}\n"
            "Each field uses its last verified update when available; otherwise its original linking observation.")
        self.summary.setText(" | ".join(f"{count} {status}" for status, count in Counter(f.status for f in review.fields).items()) +
            ("\n" + "; ".join(review.blockers) if review.blockers else ""))
        self.model.replace([(f.field, display(f.current_bahi), display(f.current_tally), f.status) for f in review.fields], review.fields)
        self.details.clear()
        if self.model.rowCount(): self.view.selectRow(0)
        self.actions()
        self.load_latest()

    def actions(self, *_):
        selected = self.model.checked
        needs_missing = any(f.field in selected and f.status=='Fill missing destination' for f in self.model.objects)
        candidate = self.review and not self.review.blockers and bool(selected) and (not needs_missing or self.accept_missing.isChecked())
        unresolved = self.record and self.record.state not in {"SUCCEEDED", "FAILED", "CANCELLED"} and self.record.attempted
        self.prepare.setEnabled(bool(candidate) and not unresolved and not self.busy)
        pending = self.record and self.record.state == "PENDING" and not self.record.attempted
        current = pending and self.record.preview.generation == self.generation
        has_mailing = self.direction == Direction.TO_TALLY and bool(selected & {'address','state','country','pincode'})
        has_tax = self.direction == Direction.TO_TALLY and bool(selected & set(GST_UPDATE_FIELDS))
        self.effective_date.setEnabled(has_mailing and not self.busy)
        self.gst_date.setEnabled(has_tax and not self.busy)
        same_date = bool(self.record) and ((self.effective_date.text().strip().replace('-', '') or None) if has_mailing else None) == self.record.preview.update.mailing_effective_date
        same_fields = bool(self.record) and selected==set(self.record.preview.update.fields)
        same_tax_date = bool(self.record) and ((self.gst_date.text().strip().replace('-','') or None) if has_tax else None) == self.record.preview.update.gst_effective_date
        self.approve.setEnabled(bool(current) and same_date and same_tax_date and same_fields and (not needs_missing or self.accept_missing.isChecked()) and self.normal.isChecked() and bool(self.reviewer.text().strip()) and not self.busy)
        self.cancel.setEnabled(bool(pending) and not self.busy)
        self.reconcile.setEnabled(bool(self.record and self.record.attempted and self.record.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}) and not self.busy)
        self.restore.setEnabled(not self.busy)
        self.refresh.setEnabled(bool(self.review) and not self.busy)
        self.close_failed.setEnabled(bool(self.record and self.record.state == 'BLOCKED' and self.record.attempted
            and self.record.comparisons.get('state') is False and self.record.preview.update.mailing_effective_date is None)
            and self.record.preview.update.fields == ('state',)
            and self.normal.isChecked() and bool(self.reviewer.text().strip()) and not self.busy)

    def load_latest(self):
        self.send("UPDATE_STATUS", party_identity=self.source_identity, direction=self.direction)

    def refresh_changes(self):
        if self.review: self.send("PARTY_CHANGES", party_identity=self.source_identity, direction=self.direction)

    def prepare_update(self):
        if self.review:
            chosen = (self.effective_date.text().strip().replace('-', '') or None) if self.effective_date.isEnabled() else None
            if chosen:
                try: datetime.strptime(chosen, '%Y%m%d')
                except ValueError:
                    self.result.setText('Enter a valid effective date as YYYY-MM-DD. No update sent.')
                    return
            self.normal.setChecked(False)
            fields = tuple(f.field for f in self.model.objects if f.field in self.model.checked)
            tax_date = (self.gst_date.text().strip().replace('-','') or None) if self.gst_date.isEnabled() else None
            if self.gst_date.isEnabled():
                try: datetime.strptime(tax_date or '', '%Y%m%d')
                except ValueError:
                    self.result.setText('Enter a valid GST effective date as YYYY-MM-DD. No update sent.')
                    return
            self.send("UPDATE_PREPARE", party_identity=self.source_identity, direction=self.direction, mailing_effective_date=chosen,
                update_fields=fields,accept_missing_fields=self.accept_missing.isChecked(),gst_effective_date=tax_date)

    def close_failed_update(self):
        if not self.close_failed.isEnabled(): return
        from innoforia_tally_connector.ui.confirmations import confirm_plain
        if confirm_plain(self, 'Close unchanged failed update',
            'Read the known ledger twice and close this failed empty-mailing attempt only if its original contents are unchanged. '
            'This sends no import, retains all evidence and never resends the old attempt. '
            'Confirm no competing editor or pending remote import. A new dated request needs a new approval.'):
            self.send('UPDATE_CLOSE_FAILED', experiment_id=self.record.preview.id, reviewer=self.reviewer.text().strip(), source_normal_party_confirmed=True)

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
        if not confirm_plain(self, "Confirm selected party updates", self.result.text() +
            f"\nReviewer: {self.reviewer.text().strip()}\nSend once? Retain the record; no automatic retry."): return
        self.send("UPDATE_APPLY", experiment_id=p.id, direction=p.direction,
            approval_digest=p.digest, reviewer=self.reviewer.text().strip(), source_normal_party_confirmed=self.normal.isChecked())

    def show_update(self, record, operator=""):
        if record and self.review and (record.preview.source.identity != self.source_identity or record.preview.direction != self.direction):
            self.review = None
            self.model.replace([]); self.details.clear(); self.identity.clear(); self.summary.clear()
        self.record = record
        if record:
            self.direction = record.preview.direction
            reverse = self.direction == Direction.TO_BAHI
            self.model.reverse = reverse
            self.setWindowTitle('Review linked Tally → Bahi changes' if reverse else 'Review linked Bahi → Tally changes')
            self.effective_date.setVisible(not reverse); self.gst_date.setVisible(not reverse)
            self.close_failed.setVisible(not reverse)
        self.normal.setChecked(False)
        if record is None:
            self.result.setText("No saved update for this party" if self.review else "No saved party update in this connection")
        else:
            p = record.preview
            self.effective_date.setText((p.update.mailing_effective_date or '') if record.state == 'PENDING' else '')
            self.gst_date.setText((p.update.gst_effective_date or '') if record.state == 'PENDING' else '')
            before = p.update.before.content
            changes = '\n'.join(f'{f}: {getattr(before,f)!r} → {getattr(p.party,f)!r}' for f in p.update.fields)
            self.result.setText(f"Party update: {record.state}\nRecord {p.id}\n"
                f"Destination: {p.preflight.destination}\n{before.name} | ID {p.update.before.identity}\n"
                f"Source: {p.source.side} party {p.source.identity}\n"
                f"Selected changes:\n{changes}\nExplicit blank-field fills: {', '.join(p.update.accepted_missing_fields) or 'None'}\n" +
                (f"Add GST registration effective {p.update.gst_effective_date}; GST State {p.update.gst_state}. Earlier tax history is preserved.\n"
                    if p.update.gst_effective_date else '') +
                (f"Create first mailing entry with approved effective date {p.update.mailing_effective_date}; only selected fields are supplied.\n"
                    if p.update.mailing_effective_date else ('Preserve unrelated Bahi values; no Tally history dates are sent.\n' if p.direction == Direction.TO_BAHI else 'Preserve existing mailing details and date when present; no date added.\n')) +
                f"Expires {p.expires_at.isoformat()}\n"
                f"Attempt recorded: {record.attempted}. {record.message}\nComparisons: {record.comparisons}")
            self.reviewer.setText(record.reviewer or operator)
        self.actions()

    def inspect(self, *_):
        row = self.model.selected(self.view)
        if row is None: return
        ack = self.review.state_acknowledgement
        baseline = "last verified field update" if ack and (row.field in ack.field_baselines or (row.field=='state' and not ack.field_baselines)) else "linking"
        self.details.setPlainText(f"{row.field}: {row.status}\n{row.reason}\n\n"
            f"Bahi at {baseline}: {display(row.saved_bahi)}\nBahi now: {display(row.current_bahi)}\n"
            f"Tally at {baseline}: {display(row.saved_tally)}\nTally now: {display(row.current_tally)}")
