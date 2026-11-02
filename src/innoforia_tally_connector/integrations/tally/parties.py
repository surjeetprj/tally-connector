"""Verified ledger/group exports with explicitly confirmed classification roots."""
from datetime import datetime, timezone
import json

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.domain.masters import GroupObservation, PartyContent, PartyObservation, PartyScan, PartyType, ScanIssue, Side


def group_observations(rows):
    groups = tuple(GroupObservation(identity=r["GUID"], name=r["NAME"], parent=r.get("PARENT", ""),
                                    version=r["ALTERID"]) for r in rows)
    if len({g.identity for g in groups}) != len(groups) or len({g.name for g in groups}) != len(groups):
        raise ReadError("Ambiguous Tally group identities or names")
    return groups


def ancestry(parent, groups):
    by_name = {g.name: g for g in groups}
    path, visited = [], set()
    while parent and parent != "Primary":
        if parent in visited or parent not in by_name:
            raise ReadError("Unresolved or cyclic Tally group ancestry")
        visited.add(parent)
        group = by_name[parent]
        path.append(group)
        parent = group.parent
    return path


def validate_classification(classification, groups):
    by_id = {g.identity: g for g in groups}
    a, b = classification.customer_root, classification.supplier_root
    if a == b or a not in by_id or b not in by_id:
        raise ReadError("Select two distinct observed party group roots")
    for root, other in ((by_id[a], b), (by_id[b], a)):
        if other in {g.identity for g in ancestry(root.parent, groups)}:
            raise ReadError("Customer and supplier group roots overlap")


class PartyReader:
    def __init__(self, gateway, classification, progress=lambda *_: None):
        self.gateway, self.classification, self.progress = gateway, classification, progress

    def groups(self, binding):
        groups = group_observations(self.gateway.read("Group", binding.company_guid))
        validate_classification(self.classification, groups)
        return groups

    def _observation(self, row, binding, groups):
        if not row.get("GUID") or not row.get("NAME") or not row.get("ALTERID"):
            raise ReadError("Tally ledger identity/name/version is missing")
        path = ancestry(row.get("PARENT", ""), groups)
        ids = {g.identity for g in path}
        matches = []
        if self.classification.customer_root in ids:
            matches.append(PartyType.CUSTOMER)
        if self.classification.supplier_root in ids:
            matches.append(PartyType.SUPPLIER)
        if len(matches) != 1:
            raise ReadError("Ledger is outside the confirmed party classifications")
        fields = {"EMAIL": "email", "LEDGERPHONE": "phone", "PARTYGSTIN": "gstin",
                  "PINCODE": "pincode", "LEDSTATENAME": "state"}
        content = {dest: row[src] for src, dest in fields.items() if src in row}
        return PartyObservation(binding=binding, side=Side.TALLY, identity=row["GUID"],
                                party_type=matches[0], content=PartyContent(name=row["NAME"], **content),
                                version=row["ALTERID"], observed_at=datetime.now(timezone.utc),
                                master_id=row.get("MASTERID"),
                                classification_evidence=json.dumps([(g.identity, g.name, g.parent) for g in path]),
                                unavailable_fields=("address",))

    def detail(self, binding, identity):
        groups = self.groups(binding)
        rows = self.gateway.read("Ledger", binding.company_guid, identity)
        if len(rows) != 1 or rows[0].get("GUID") != identity:
            raise ReadError("Tally GUID was not found uniquely; no name fallback is allowed")
        return self._observation(rows[0], binding, groups)

    def scan(self, binding):
        groups = self.groups(binding)
        rows = self.gateway.read("Ledger", binding.company_guid)
        found, issues, seen = [], [], set()
        for row in rows:
            if row.get("GUID") and row["GUID"] in seen:
                raise ReadError("Duplicate Tally ledger GUIDs")
            if row.get("GUID"):
                seen.add(row["GUID"])
            try:
                found.append(self._observation(row, binding, groups))
            except ReadError as error:
                issues.append(ScanIssue(code="CLASSIFICATION", message=str(error),
                                        identity=row.get("GUID"), name=row.get("NAME")))
        self.progress("Tally", f"{len(found)} parties; {len(issues)} excluded ledgers")
        return PartyScan(binding=binding, side=Side.TALLY, records=tuple(found),
                         observed_at=datetime.now(timezone.utc), pages_read=(1,), total_pages=1,
                         issues=tuple(issues))
