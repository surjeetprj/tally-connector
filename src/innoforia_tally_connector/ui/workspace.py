"""Everyday party workspace. Network, persistence and execution stay in controllers."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTabWidget, QTableView, QSplitter, QCheckBox,
    QGroupBox, QTextEdit, QScrollArea)
from innoforia_tally_connector.domain.masters import Side, Classification
from innoforia_tally_connector.domain.experiments import Direction
from innoforia_tally_connector.domain.batches import TransferPolicy, CONTACT_FIELDS, TransferBatch
from innoforia_tally_connector.ui.models.parties import TableModel, PartyTableModel
from innoforia_tally_connector.ui.party_drag import PartyView, DragSession, CreateDropArea
from innoforia_tally_connector.ui.pages.batch_review import BatchReview
from innoforia_tally_connector.ui.pages.activity import ActivityPage
from innoforia_tally_connector.ui.pages.transfer import TransferPage
from innoforia_tally_connector.ui.confirmations import confirm_plain


class Workspace(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Innoforia — Party connector")
        self.resize(1250, 850)
        self.controller = self.discovery = self.policy = self.current_batch = None
        self.quitting = False
        self.drag_session = DragSession()
        self.linked = set()
        self.row_states = {}
        self.recovery_pending = False
        self.recovery_links_pending = False
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        self.identity = QLabel("Connecting to your saved Bahi / Tally pair…")
        self.identity.setWordWrap(True)
        layout.addWidget(self.identity)
        self.tabs = QTabWidget()
        self.page_scrolls = []
        layout.addWidget(self.tabs, 1)
        self.parties = QWidget()
        parties = QVBoxLayout(self.parties)
        toolbar = QHBoxLayout()
        self.refresh = QPushButton("Refresh parties")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search names or GSTINs")
        self.filter = QComboBox()
        self.filter.addItems(["All parties", "Customers", "Suppliers"])
        for w in (self.refresh, self.search, self.filter): toolbar.addWidget(w)
        parties.addLayout(toolbar)
        self.setup_notice = QWidget()
        setup_row = QHBoxLayout(self.setup_notice)
        setup_row.setContentsMargins(0, 0, 0, 0)
        self.setup_message = QLabel("Transfers need one-time setup: enter your name and save the transfer policy in Settings.")
        self.setup_message.setWordWrap(True)
        self.finish_setup = QPushButton("Finish transfer setup")
        self.finish_setup.clicked.connect(self.open_transfer_setup)
        setup_row.addWidget(self.setup_message, 1)
        setup_row.addWidget(self.finish_setup)
        parties.addWidget(self.setup_notice)
        self.coverage = QLabel("No observations loaded")
        self.coverage.setWordWrap(True)
        parties.addWidget(self.coverage)
        split = QSplitter()
        self.models, self.views, self.transfer_buttons = {}, {}, {}
        for side in (Side.BAHI, Side.TALLY):
            panel = QWidget()
            column = QVBoxLayout(panel)
            column.addWidget(QLabel(side.title()))
            model = PartyTableModel(["Party", "Type", "Status", "Identity"])
            view = PartyView(side, self.drag_session)
            view.setModel(model)
            view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
            view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
            view.setColumnWidth(0, 260)
            view.horizontalHeader().setStretchLastSection(True)
            button = QPushButton("Transfer selected to " + ("Tally…" if side == Side.BAHI else "Bahi…"))
            button.clicked.connect(lambda checked=False, s=side: self.prepare(self.models[s].selected_many(self.views[s])))
            drop = CreateDropArea(side, self.drag_session)
            drop.review.connect(self.drop)
            view.review.connect(self.drop)
            column.addWidget(view, 1)
            column.addWidget(button)
            column.addWidget(drop)
            split.addWidget(panel)
            self.models[side], self.views[side], self.transfer_buttons[side] = model, view, button
        parties.addWidget(split, 1)
        self.add_page(self.parties, "Parties")
        self.activity_page = QWidget()
        activity = QVBoxLayout(self.activity_page)
        controls = QHBoxLayout()
        self.refresh_activity = QPushButton("Refresh activity")
        self.recover = QPushButton("Check unresolved results (reads only)")
        self.resume = QPushButton("Review remaining parties")
        for w in (self.refresh_activity, self.recover, self.resume): controls.addWidget(w)
        activity.addLayout(controls)
        self.batch_model = TableModel(["Prepared", "Direction", "Status", "Parties", "Batch ID"])
        self.batch_view = QTableView()
        self.batch_view.setModel(self.batch_model)
        self.batch_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.batch_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.batch_view.horizontalHeader().setStretchLastSection(True)
        self.batch_view.doubleClicked.connect(self.inspect_batch)
        activity.addWidget(self.batch_view, 1)
        batch_paging = QHBoxLayout()
        self.batch_previous, self.batch_next = QPushButton("Previous batches"), QPushButton("Next batches")
        self.batch_offset, self.batch_more = 0, False
        self.batch_previous.clicked.connect(lambda: self.send("BATCH_LIST", offset=max(0, self.batch_offset - 50)))
        self.batch_next.clicked.connect(lambda: self.send("BATCH_LIST", offset=self.batch_offset + 50))
        batch_paging.addWidget(self.batch_previous); batch_paging.addWidget(self.batch_next)
        activity.addLayout(batch_paging)
        self.saved_model = TableModel(["Bahi", "Bahi ID", "Tally", "Tally GUID", "Reviewer"])
        self.saved_view = QTableView()
        self.saved_view.setModel(self.saved_model)
        self.saved_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.saved_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.saved_view.horizontalHeader().setStretchLastSection(True)
        activity.addWidget(QLabel("Saved identity links"))
        activity.addWidget(self.saved_view, 1)
        link_paging = QHBoxLayout()
        self.links_previous, self.links_next = QPushButton("Previous links"), QPushButton("Next links")
        self.links_offset = 0
        self.links_more = False
        self.links_previous.clicked.connect(lambda: self.send("SAVED", offset=max(0, self.links_offset - 200)))
        self.links_next.clicked.connect(lambda: self.send("SAVED", offset=self.links_offset + 200))
        link_paging.addWidget(self.links_previous)
        link_paging.addWidget(self.links_next)
        activity.addLayout(link_paging)
        self.saved_details = QTextEdit()
        self.saved_details.setReadOnly(True)
        self.saved_details.setMaximumHeight(110)
        activity.addWidget(self.saved_details)
        self.saved_view.selectionModel().selectionChanged.connect(self.inspect_link)
        self.advanced = QGroupBox("Advanced: legacy history and recovery")
        self.advanced.setCheckable(True)
        self.advanced.setChecked(False)
        advanced_layout = QVBoxLayout(self.advanced)
        self.legacy = ActivityPage(self.send)
        self.technical = TransferPage(self.send, self.review_pair)
        self.technical.activity.clicked.connect(lambda: self.legacy.load(0))
        self.advanced_tabs = QTabWidget()
        self.advanced_tabs.addTab(self.legacy, "Legacy / per-party records")
        self.advanced_tabs.addTab(self.technical, "Operation details")
        advanced_layout.addWidget(self.advanced_tabs)
        self.advanced_tabs.hide()
        self.advanced.toggled.connect(self.advanced_tabs.setVisible)
        activity.addWidget(self.advanced)
        self.add_page(self.activity_page, "Activity")
        settings = QWidget()
        form = QVBoxLayout(settings)
        self.verify = QPushButton("Verify connections / review setup")
        form.addWidget(self.verify)
        roots = QHBoxLayout()
        self.customers, self.suppliers = QComboBox(), QComboBox()
        roots.addWidget(QLabel("Customer root")); roots.addWidget(self.customers)
        roots.addWidget(QLabel("Supplier root")); roots.addWidget(self.suppliers)
        self.bind = QPushButton("Confirm pair and classification")
        roots.addWidget(self.bind)
        form.addLayout(roots)
        self.operator = QLineEdit()
        form.addWidget(QLabel("Your name (required once for transfer approvals)"))
        self.operator.setPlaceholderText("Operator name, saved for transfer approvals")
        form.addWidget(self.operator)
        self.setup_error = QLabel()
        self.setup_error.setWordWrap(True)
        self.setup_error.hide()
        form.addWidget(self.setup_error)
        note = QLabel("Saved policy: omit unavailable/invalid optional fields with audited reasons. "
            "GSTIN, PAN and registration type remain disabled pending verified Tally contracts. "
            "Only exact source values are transferred. No updates or unattended creation.")
        note.setWordWrap(True)
        form.addWidget(note)
        self.field_boxes = {}
        for direction in Direction:
            group = QGroupBox(direction.value.replace('_', ' '))
            row = QHBoxLayout(group)
            for field in CONTACT_FIELDS:
                box = QCheckBox(field)
                box.setChecked(True)
                row.addWidget(box)
                self.field_boxes[direction, field] = box
            form.addWidget(group)
        self.save_policy = QPushButton("Save operator and transfer policy")
        form.addWidget(self.save_policy)
        form.addStretch()
        self.add_page(settings, "Settings")
        self.status = QLabel("Waiting for local startup")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.review = BatchReview(self, self.send, self.review_pair)
        self.review.activity.clicked.connect(self.open_activity)
        self.refresh.clicked.connect(lambda: self.send("LOAD"))
        self.verify.clicked.connect(lambda: self.send("VERIFY"))
        self.bind.clicked.connect(self.confirm_setup)
        self.save_policy.clicked.connect(self.save_settings)
        self.refresh_activity.clicked.connect(self.load_activity)
        self.recover.clicked.connect(lambda: self.send("BATCH_RECOVER"))
        self.resume.clicked.connect(self.resume_batch)
        self.search.textChanged.connect(self.render)
        self.filter.currentIndexChanged.connect(self.render)
        self.update_controls()
        screen = self.screen()
        if screen:
            available = screen.availableGeometry()
            self.resize(min(1250, max(1, available.width() - 40)),
                min(850, max(1, available.height() - 80)))

    def add_page(self, page, title):
        # Tall tables/advanced forms must not become the main window's minimum
        # height. Scroll overflow at small logical sizes (including high DPI).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(page)
        self.page_scrolls.append(scroll)
        self.tabs.addTab(scroll, title)

    def attach(self, controller):
        self.controller = controller
        controller.result.connect(self.receive)
        controller.progress.connect(self.status.setText)
        self.send("RESTORE")

    def send(self, kind, **values):
        if not self.controller: return
        if kind in {"VERIFY", "RESTORE"}:
            self.discovery = self.policy = self.current_batch = None
            self.drag_session.reset(None, None)
            self.review.hide()
            self.technical.clear()
            self.render()
        self.status.setText("Working in background…")
        self.controller.submit(kind, **values)
        self.update_controls()

    def update_controls(self):
        bound = bool(self.controller and self.controller.binding)
        busy = bool(self.controller and self.controller.pending)
        executing = bool(self.current_batch and self.current_batch.state == "APPLYING")
        for w in (self.refresh, self.refresh_activity, self.recover, self.resume): w.setEnabled(bound and not busy and not executing)
        self.verify.setEnabled(not busy and not executing)
        self.bind.setEnabled(not busy and not executing and self.customers.count() > 0)
        self.save_policy.setEnabled(bound and not busy and not executing)
        self.links_previous.setEnabled(bound and not busy and self.links_offset > 0)
        self.links_next.setEnabled(bound and not busy and self.links_more)
        self.batch_previous.setEnabled(bound and not busy and self.batch_offset > 0)
        self.batch_next.setEnabled(bound and not busy and self.batch_more)
        needs_policy = bound and self.policy is None
        self.setup_notice.setVisible(needs_policy)
        self.finish_setup.setEnabled(needs_policy and not busy and not executing)
        for side, button in self.transfer_buttons.items():
            destination = "Tally" if side == Side.BAHI else "Bahi"
            button.setText(f"Set up transfers to {destination}…" if needs_policy else f"Transfer selected to {destination}…")
            enabled = bound and not busy and not executing and self.discovery is not None
            button.setEnabled(enabled)
            self.views[side].setDragEnabled(enabled and not needs_policy)
        self.legacy.set_busy(busy, bound)
        self.technical.generation = getattr(self.controller, "generation", None)
        self.technical.set_busy(busy, bound)

    def confirm_setup(self):
        if not self.customers.currentData() or not self.suppliers.currentData(): return
        if confirm_plain(self, "Confirm connection and classification", self.identity.text() +
            f"\nCustomers: {self.customers.currentText()}\nSuppliers: {self.suppliers.currentText()}\nSave this local classification?"):
            self.send("BIND", classification=Classification(customer_root=self.customers.currentData(), supplier_root=self.suppliers.currentData()))

    def open_transfer_setup(self):
        self.tabs.setCurrentIndex(2)
        self.page_scrolls[2].ensureWidgetVisible(self.operator)
        self.operator.setFocus(Qt.FocusReason.OtherFocusReason)
        self.status.setText("Enter your name, review the field choices and click Save operator and transfer policy once")

    def save_settings(self):
        try:
            policy = TransferPolicy(binding=self.controller.binding, version=self.policy.version if self.policy else 1,
                operator=self.operator.text().strip(), **{("to_bahi" if d == Direction.TO_BAHI else "to_tally"):
                tuple(f for f in CONTACT_FIELDS if self.field_boxes[d, f].isChecked()) for d in Direction})
        except ValueError:
            self.open_transfer_setup()
            self.setup_error.setText("Enter your name above before saving. No transfer has been started.")
            self.setup_error.show()
            self.status.setText("Enter the operator name before saving settings")
            return
        self.setup_error.hide()
        self.send("POLICY_SAVE", policy=policy)

    def prepare(self, sources):
        if not self.policy:
            self.open_transfer_setup()
            return
        sources = sources if isinstance(sources, tuple) else (sources,)
        if not 1 <= len(sources) <= 100:
            self.status.setText("Select 1–100 unique source parties")
            return
        if self.controller.pending or (self.current_batch and self.current_batch.state == "APPLYING"): return
        self.send("BATCH_PREPARE", sources=sources,
            direction=Direction.TO_TALLY if sources[0].side == Side.BAHI else Direction.TO_BAHI)

    def drop(self, source, target):
        if target is None: self.prepare(source)
        else: self.review_pair(source, target)

    def review_pair(self, source, target, *_):
        if not self.policy or isinstance(source, tuple) or source.party_type != target.party_type or source.side == target.side:
            return
        if source.is_active is False or target.is_active is False or source.is_system is True or target.is_system is True: return
        if confirm_plain(self, "Confirm identity link", f"{source.side} {source.identity}: {source.content.model_dump(exclude_unset=True)!r}\n"
            f"{target.side} {target.identity}: {target.content.model_dump(exclude_unset=True)!r}\n"
            f"Operator: {self.policy.operator}\nConfirm these represent the same party? No remote fields change."):
            a, b = (source, target) if source.side == Side.BAHI else (target, source)
            self.send("LINK", bahi=a, tally=b, reviewer=self.policy.operator)

    def receive(self, event):
        if event.error:
            self.status.setText(event.error)
            if event.kind == "SAVED": self.recovery_links_pending = False
            if event.kind == "POLICY_SAVE":
                self.setup_error.setText(event.error)
                self.setup_error.show()
            if event.kind.startswith("BATCH_"):
                self.review.error.setText(event.error)
                self.review.error.show()
            self.review.awaiting = False
            self.review.update_actions()
            if event.kind == "RESTORE": self.tabs.setCurrentIndex(2)
            if event.kind == "BATCH_STEP": self.load_activity()
            self.update_controls()
            return
        result, kind = event.result, event.kind
        if kind in {"RESTORE", "VERIFY"} and hasattr(result, "saved_setup"):
            self.discovery = self.policy = None
            self.drag_session.reset(None, None)
            self.render()
            snap = result.snapshot
            self.identity.setText(f"Bahi: {snap.business_name} ({snap.business_id}) ↔ Tally: {snap.company_name} ({snap.company_guid})")
            for combo in (self.customers, self.suppliers):
                combo.clear()
                combo.addItem("Select observed root…", None)
                for group in sorted(snap.groups, key=lambda g: g.name.casefold()): combo.addItem(group.name, group.identity)
            if result.saved_setup:
                self.customers.setCurrentIndex(self.customers.findData(result.saved_setup[1].customer_root))
                self.suppliers.setCurrentIndex(self.suppliers.findData(result.saved_setup[1].supplier_root))
            self.tabs.setCurrentIndex(2)
            self.status.setText("Confirm the observed connection and classification")
        elif kind in {"BIND", "RESTORE"}:
            snapshot = result.snapshot
            self.identity.setText(f"Connected: Bahi {snapshot.business_name} ({result.binding.business_id}) ↔ "
                f"Tally {snapshot.company_name} ({result.binding.company_guid})" if snapshot else
                f"Connected: Bahi {result.binding.business_id} ↔ Tally {result.binding.company_guid}")
            if snapshot:
                for combo, identity in ((self.customers, result.classification.customer_root), (self.suppliers, result.classification.supplier_root)):
                    combo.clear()
                    for group in sorted(snapshot.groups, key=lambda g: g.name.casefold()): combo.addItem(group.name, group.identity)
                    combo.setCurrentIndex(combo.findData(identity))
            self.links_offset, self.links_more = 0, result.has_more
            self.show_links(result.links)
            self.send("POLICY_GET")
        elif kind in {"POLICY_GET", "POLICY_SAVE"}:
            self.policy = result
            if result:
                self.setup_error.hide()
                self.operator.setText(result.operator)
                for d in Direction:
                    fields = result.to_bahi if d == Direction.TO_BAHI else result.to_tally
                    for f in CONTACT_FIELDS: self.field_boxes[d, f].setChecked(f in fields)
                self.tabs.setCurrentIndex(0)
            else:
                self.tabs.setCurrentIndex(2)
                self.status.setText("Confirm your operator name and default contact-field policy once")
            if result:
                self.recovery_pending = True
                self.send("LOAD")
        elif kind == "LOAD":
            self.discovery = result
            self.drag_session.reset(self.controller.binding, self.controller.generation)
            self.coverage.setText(" | ".join(f"{s.side}: {len(s.records)} parties, "
                f"{'complete page coverage' if s.coverage_complete else 'INCOMPLETE'}, observed {s.observed_at.isoformat()}"
                for s in (result.bahi, result.tally)) + " | Paginated observations are not a stable snapshot.")
            self.linked = set(result.linked)
            self.render()
            self.status.setText("Select parties and transfer. Creation always needs batch approval." if self.policy else
                "Transfers are not set up yet. Use Finish transfer setup to save your name and policy once.")
            if self.recovery_pending:
                self.recovery_pending = False
                self.send("BATCH_RECOVER")
        elif kind.startswith("BATCH_"):
            if isinstance(result, TransferBatch):
                self.current_batch = result
                self.row_states.update({(i.source.side, i.source.identity):
                    "Transferred" if i.status == "SUCCEEDED" else "Transferring" if result.state == "APPLYING" and i.preview else
                    "Needs review" if i.status in {"Needs review", "BLOCKED", "OUTCOME_UNKNOWN", "FAILED", "VERIFYING"} else
                    "Linked" if i.status == "Already linked" else "Available" for i in result.items})
                self.review.receive(result, self.controller.generation)
                self.review.show()
                self.review.raise_()
                self.render()
                if result.state != "APPLYING" and kind in {"BATCH_STEP", "BATCH_CANCEL"}:
                    self.send("LOAD"); self.send("SAVED"); self.send("BATCH_LIST")
                    if kind == "BATCH_STEP" and result.state == "BLOCKED": self.send("BATCH_RECOVER")
            else:
                self.batch_offset, self.batch_more = result.offset, result.has_more
                self.batch_model.replace([(b.created_at.isoformat(), b.direction, b.state, len(b.items), b.id) for b in result.records], result.records)
                if self.current_batch:
                    updated = next((b for b in result.records if b.id == self.current_batch.id), None)
                    if updated:
                        self.current_batch = updated
                        self.review.receive(updated, self.controller.generation)
                if kind == "BATCH_RECOVER":
                    self.recovery_links_pending = True
                    self.send("SAVED", offset=0)
                    self.status.setText("Read-only result checks completed. Refreshing saved links…")
        elif kind == "SAVED":
            self.show_links(result.links)
            self.links_offset, self.links_more = result.offset, result.has_more
            if self.recovery_links_pending:
                self.recovery_links_pending = False
                for link in result.links:
                    for party in (link.bahi, link.tally):
                        key = (party.side, party.identity)
                        self.linked.add(key)
                        self.row_states[key] = "Linked"
                self.render()
                self.status.setText("Read-only result checks complete. Saved links refreshed.")
            else:
                self.status.setText("Saved links refreshed.")
        elif kind == "LINK":
            self.status.setText("Identity link saved; no remote fields changed")
            self.send("LOAD"); self.send("SAVED")
        elif kind == "ACTIVITY":
            self.legacy.receive(result)
        elif kind == "ACTIVITY_DETAIL" or kind.startswith(("TRANSFER_", "EXP_")):
            self.technical.receive(event)
            self.advanced.setChecked(True)
            self.advanced_tabs.setCurrentIndex(1)
        self.update_controls()

    def render(self, *_):
        if not self.discovery:
            for model in self.models.values(): model.replace([])
            return
        candidates = {(c.bahi.side, c.bahi.identity) for c in self.discovery.candidates} | {(c.tally.side, c.tally.identity) for c in self.discovery.candidates}
        for scan in (self.discovery.bahi, self.discovery.tally):
            rows, objects = [], []
            for r in scan.records:
                kind = [None, "CUSTOMER", "SUPPLIER"][self.filter.currentIndex()]
                if kind and r.party_type != kind: continue
                if self.search.text().casefold() not in (r.content.name + " " + (r.content.gstin or "")).casefold(): continue
                key = (r.side, r.identity)
                status = self.row_states.get(key, "Linked" if key in self.linked else "Needs review" if key in candidates or r.is_active is False or r.is_system is True else "Available")
                rows.append((r.content.name, r.party_type.title(), status, r.identity)); objects.append(r)
            self.models[scan.side].replace(rows, objects)

    def show_links(self, links):
        self.saved_model.replace([(r.bahi.content.name, r.bahi.identity, r.tally.content.name, r.tally.identity, r.confirmed_by) for r in links], links)

    def inspect_link(self, *_):
        link = self.saved_model.selected(self.saved_view)
        if link: self.saved_details.setPlainText(link.model_dump_json(indent=2))

    def load_activity(self):
        self.send("BATCH_LIST")
        self.send("SAVED", offset=0)

    def open_activity(self):
        self.review.hide()
        self.tabs.setCurrentIndex(1)
        self.advanced.setChecked(True)
        self.load_activity()
        self.legacy.load(0)

    def inspect_batch(self, *_):
        batch = self.batch_model.selected(self.batch_view)
        if batch: self.send("BATCH_GET", batch_id=batch.id)

    def resume_batch(self):
        batch = self.batch_model.selected(self.batch_view)
        if not batch: return
        sources = tuple(i.source for i in batch.items if not i.result or not i.result.attempted)
        if sources: self.prepare(sources)
        else: self.status.setText("No unsent work. Inspect results; uncertain attempts cannot be recreated.")

    def closeEvent(self, event):
        if self.quitting: event.accept()
        else:
            if hasattr(self, "request_quit"): self.request_quit()
            event.ignore()
