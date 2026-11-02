"""Native read-only party review; identity links are the only local action."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QTableView, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget)

from innoforia_tally_connector.domain.masters import Classification, PartyContent
from innoforia_tally_connector.ui.models.parties import TableModel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Innoforia — Party discovery and local links")
        self.resize(1250, 850)
        self.controller, self.discovery = None, None
        self.quitting = False
        self.saved_offset, self.saved_has_more = 0, False
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.addWidget(QLabel("READ ONLY · Bahi business 52 ↔ SIS Dummy · No remote master changes"))
        self.identity = QLabel("Starting local metadata…")
        self.identity.setWordWrap(True)
        layout.addWidget(self.identity)
        setup = QHBoxLayout()
        self.verify = QPushButton("Verify connections")
        self.customers, self.suppliers = QComboBox(), QComboBox()
        self.bind = QPushButton("Confirm pair and groups")
        setup.addWidget(self.verify)
        setup.addWidget(QLabel("Customer root"))
        setup.addWidget(self.customers, 1)
        setup.addWidget(QLabel("Supplier root"))
        setup.addWidget(self.suppliers, 1)
        setup.addWidget(self.bind)
        layout.addLayout(setup)
        toolbar = QHBoxLayout()
        self.load, self.saved = QPushButton("Load / Refresh parties"), QPushButton("Refresh saved links")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search observed names and GSTINs")
        self.party_filter = QComboBox()
        self.party_filter.addItems(["All parties", "Customers", "Suppliers"])
        for widget in (self.load, self.saved, self.search, self.party_filter):
            toolbar.addWidget(widget)
        layout.addLayout(toolbar)
        self.coverage = QLabel("No scan loaded. Page coverage does not establish a stable snapshot.")
        self.coverage.setWordWrap(True)
        layout.addWidget(self.coverage)
        self.tabs = QTabWidget()
        self.bahi_model, self.bahi_view = self.table(["Bahi party", "Type", "Active", "ID"])
        self.tally_model, self.tally_view = self.table(["Tally party", "Type", "GUID"])
        for view in (self.bahi_view, self.tally_view):
            view.setColumnWidth(0, 260)
            view.setColumnWidth(1, 95)
        split = QSplitter()
        split.addWidget(self.bahi_view)
        split.addWidget(self.tally_view)
        self.tabs.addTab(split, "Observed parties — select one on each side")
        self.candidate_model, self.candidate_view = self.table(["Bahi", "Tally", "Evidence"])
        self.candidate_view.setColumnWidth(0, 300)
        self.candidate_view.setColumnWidth(1, 300)
        self.tabs.addTab(self.candidate_view, "All matching suggestions")
        self.link_model, self.link_view = self.table(["Bahi", "Tally", "Reviewer", "Confirmed UTC"])
        for column, width in enumerate((300, 300, 220)):
            self.link_view.setColumnWidth(column, width)
        self.tabs.addTab(self.link_view, "Saved local links")
        layout.addWidget(self.tabs, 3)
        paging = QHBoxLayout()
        self.previous_links, self.next_links = QPushButton("Previous saved links"), QPushButton("Next saved links")
        self.previous_links.setEnabled(False)
        self.next_links.setEnabled(False)
        paging.addWidget(self.previous_links)
        paging.addWidget(self.next_links)
        paging.addStretch()
        layout.addLayout(paging)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        action = QHBoxLayout()
        self.reviewer = QLineEdit()
        self.reviewer.setPlaceholderText("Confirming reviewer (required)")
        self.link = QPushButton("Confirm selected local link…")
        action.addWidget(self.reviewer)
        action.addWidget(self.link)
        layout.addLayout(action)
        self.status = QLabel("Waiting for initialization")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        for widget in (self.verify, self.bind, self.load, self.saved, self.link):
            widget.setEnabled(False)
        self.verify.clicked.connect(self.verify_connections)
        self.bind.clicked.connect(self.confirm_binding)
        self.load.clicked.connect(lambda: self.send("LOAD"))
        self.saved.clicked.connect(lambda: self.send("SAVED", offset=0))
        self.previous_links.clicked.connect(lambda: self.send("SAVED", offset=max(0, self.saved_offset - 200)))
        self.next_links.clicked.connect(lambda: self.send("SAVED", offset=self.saved_offset + 200))
        self.link.clicked.connect(self.confirm_link)
        self.search.textChanged.connect(self.render)
        self.party_filter.currentIndexChanged.connect(self.render)
        self.candidate_view.selectionModel().selectionChanged.connect(self.show_difference)
        self.bahi_view.selectionModel().selectionChanged.connect(self.show_difference)
        self.tally_view.selectionModel().selectionChanged.connect(self.show_difference)
        self.tabs.currentChanged.connect(self.show_difference)

    def table(self, headers):
        model, view = TableModel(headers), QTableView()
        view.setModel(model)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setSortingEnabled(False)
        view.horizontalHeader().setStretchLastSection(True)
        return model, view

    def attach(self, controller):
        self.controller = controller
        controller.result.connect(self.receive)
        controller.progress.connect(self.status.setText)
        self.verify.setEnabled(True)
        self.identity.setText("Use the existing Windows credential. Verify both identities before confirming groups.")
        self.status.setText("Ready — no automatic polling")

    def send(self, kind, **values):
        if not self.controller:
            return
        self.controller.submit(kind, **values)
        self.status.setText("Reading / validating in background…")
        self.busy(True)

    def busy(self, busy):
        for widget in (self.verify, self.bind, self.load, self.saved, self.link):
            widget.setEnabled(not busy)
        self.previous_links.setEnabled(not busy and self.saved_offset > 0)
        self.next_links.setEnabled(not busy and self.saved_has_more)
        if not busy:
            self.bind.setEnabled(self.customers.count() > 1)
            bound = self.controller is not None and self.controller.binding is not None
            self.load.setEnabled(bound)
            self.saved.setEnabled(bound)
            self.link.setEnabled(bound and self.discovery is not None)

    def verify_connections(self):
        self.discovery = None
        self.render()
        self.customers.clear()
        self.suppliers.clear()
        self.link_model.replace([])
        self.saved_offset, self.saved_has_more = 0, False
        self.send("VERIFY")

    def confirm_binding(self):
        a, b = self.customers.currentData(), self.suppliers.currentData()
        if not a or not b:
            self.status.setText("Explicitly select both observed group roots")
            return
        if QMessageBox.question(self, "Confirm read/link context",
            f"{self.identity.text()}\nCustomer root: {self.customers.currentText()}\n"
            f"Supplier root: {self.suppliers.currentText()}\n\nConfirm this local classification? No remote changes.") != QMessageBox.StandardButton.Yes:
            return
        self.send("BIND", classification=Classification(customer_root=a, supplier_root=b))

    def receive(self, event):
        self.busy(False)
        if event.error:
            self.status.setText(event.error)
            return
        if event.kind == "VERIFY":
            snapshot, saved = event.result.snapshot, event.result.saved_setup
            self.identity.setText(f"Verified Bahi: {snapshot.business_name} ({snapshot.business_id}) | "
                                  f"Tally: {snapshot.company_name} ({snapshot.company_guid})")
            for combo in (self.customers, self.suppliers):
                combo.setEnabled(True)
                combo.clear()
                combo.addItem("Select an observed group…", None)
                for group in sorted(snapshot.groups, key=lambda g: g.name.casefold()):
                    combo.addItem(group.name, group.identity)
            if saved:
                self.customers.setCurrentIndex(self.customers.findData(saved[1].customer_root))
                self.suppliers.setCurrentIndex(self.suppliers.findData(saved[1].supplier_root))
            self.bind.setEnabled(True)
            self.status.setText("Confirm the verified pair and your group selections to enable discovery")
        elif event.kind == "BIND":
            self.show_links(event.result.links, has_more=event.result.has_more)
            self.busy(False)
            self.customers.setEnabled(False)
            self.suppliers.setEnabled(False)
            self.status.setText("Local binding confirmed. Load parties when ready.")
        elif event.kind == "LOAD":
            self.discovery = event.result
            scans = (event.result.bahi, event.result.tally)
            self.coverage.setText(" | ".join(
                f"{s.side}: {len(s.records)} parties; pages {len(s.pages_read)}/{s.total_pages if s.total_pages is not None else '?'}; "
                f"{'coverage complete' if s.coverage_complete else 'INCOMPLETE'}; observed {s.observed_at.isoformat()}"
                for s in scans) + " | Neither scan establishes a stable snapshot.")
            self.render()
            issues = [f"{s.side}: {i.name or i.identity or ''} — {i.message}" for s in scans for i in s.issues]
            self.details.setPlainText("\n".join(issues) or "No classification/read issues")
            self.status.setText(f"Observed parties loaded. {len(event.result.candidates)} suggestions; no automatic links.")
            self.busy(False)
        elif event.kind in {"SAVED", "LINK"}:
            if event.kind == "LINK":
                self.discovery = None
                self.render()
                self.send("SAVED")
            else:
                self.show_links(event.result.links, event.result.offset, event.result.has_more)
                self.status.setText("Saved links loaded. Linking grants no remote overwrite permission.")

    def show_links(self, links, offset=0, has_more=False):
        self.saved_offset, self.saved_has_more = offset, has_more
        self.tabs.setTabText(2, f"Saved local links — page {offset // 200 + 1}")
        self.previous_links.setEnabled(offset > 0)
        self.next_links.setEnabled(has_more)
        self.link_model.replace([(l.bahi.content.name, l.tally.content.name, l.confirmed_by,
                                  l.confirmed_at.isoformat()) for l in links], links)

    def matches(self, party):
        kind = [None, "CUSTOMER", "SUPPLIER"][self.party_filter.currentIndex()]
        text = self.search.text().casefold()
        return (kind is None or party.party_type == kind) and (
            text in party.content.name.casefold() or text in (party.content.gstin or "").casefold())

    def render(self, *_):
        if self.discovery is None:
            for model in (self.bahi_model, self.tally_model, self.candidate_model):
                model.replace([])
            return
        left = [r for r in self.discovery.bahi.records if self.matches(r)]
        right = [r for r in self.discovery.tally.records if self.matches(r)]
        candidates = [c for c in self.discovery.candidates if self.matches(c.bahi) or self.matches(c.tally)]
        self.bahi_model.replace([(r.content.name, r.party_type.title(),
            "Yes" if r.is_active else "No" if r.is_active is False else "Not provided", r.identity) for r in left], left)
        self.tally_model.replace([(r.content.name, r.party_type.title(), r.identity) for r in right], right)
        self.candidate_model.replace([(c.bahi.content.name, c.tally.content.name, ", ".join(c.reasons))
                                      for c in candidates], candidates)

    def pair(self):
        if self.tabs.currentIndex() == 2:
            return None, None
        if self.tabs.currentIndex() == 1:
            candidate = self.candidate_model.selected(self.candidate_view)
            return (candidate.bahi, candidate.tally) if candidate else (None, None)
        return self.bahi_model.selected(self.bahi_view), self.tally_model.selected(self.tally_view)

    def show_difference(self, *_):
        left, right = self.pair()
        if not left or not right:
            return
        def value(party, field):
            if field in party.unavailable_fields:
                return "[unavailable]"
            if field not in party.content.model_fields_set:
                return "[absent]"
            result = getattr(party.content, field)
            return "[null]" if result is None else repr(result)
        lines = [f"{left.content.name} ↔ {right.content.name}", "Identity link only; differing content remains separate."]
        lines += [f"{field}: Bahi {value(left, field)} | Tally {value(right, field)}" for field in PartyContent.model_fields]
        self.details.setPlainText("\n".join(lines))

    def confirm_link(self):
        left, right = self.pair()
        if not left or not right or left.party_type != right.party_type:
            self.status.setText("Select one record on each side with compatible classification")
            return
        if left.is_active is False:
            self.status.setText("Inactive Bahi parties are visible but cannot be linked in this milestone")
            return
        reviewer = self.reviewer.text().strip()
        if not reviewer:
            self.status.setText("Enter the confirming reviewer")
            return
        self.show_difference()
        if QMessageBox.question(self, "Confirm local identity link", self.details.toPlainText() +
            "\n\nConfirm these identities represent the same entity? No remote fields will change.") == QMessageBox.StandardButton.Yes:
            self.send("LINK", bahi=left, tally=right, reviewer=reviewer)

    def closeEvent(self, event):
        if self.quitting or not getattr(self, "tray_available", False):
            if not self.quitting:
                self.request_quit()
                event.ignore()
            else:
                event.accept()
        else:
            self.hide()
            event.ignore()
