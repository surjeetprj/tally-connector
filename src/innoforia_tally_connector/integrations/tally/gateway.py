"""One injected serialized gateway for all application Tally reads."""
from threading import Lock

from innoforia_tally_connector.domain.errors import Busy, ContextMismatch, ReadError
from innoforia_tally_connector.integrations.tally._transport import Transport
from innoforia_tally_connector.integrations.tally.queries import collection
from innoforia_tally_connector.integrations.tally.xml_codec import records

COMPANY_GUID = "0b212ad8-3be5-45fe-8719-e1a70e240d4c"


class Gateway:
    def __init__(self, transport=None, lock_timeout=1, stopped=lambda: False):
        self.transport = transport or Transport()
        self.lock = Lock()
        self.lock_timeout = lock_timeout
        self.stopped = stopped

    def _export(self, request):
        if self.stopped():
            raise ReadError("Tally read stopped during shutdown")
        return self.transport.export(request)

    def _company(self, guid):
        matches = [r for r in records(self._export(collection("Company")), "Company")
                   if r.get("GUID") == guid]
        if len(matches) != 1 or not matches[0].get("NAME"):
            raise ContextMismatch("Expected Tally company is not uniquely loaded")
        return matches[0]

    def read(self, entity="Company", company_guid=COMPANY_GUID, guid=None):
        if not self.lock.acquire(timeout=self.lock_timeout):
            raise Busy("Tally read is busy; retry after the current request")
        try:
            before = self._company(company_guid)
            if entity == "Company":
                return [before]
            result = records(self._export(collection(entity, before["NAME"], guid)), entity)
            after = self._company(company_guid)
            if before["NAME"] != after["NAME"]:
                raise ContextMismatch("Tally company changed during the read")
            return result
        finally:
            self.lock.release()

    def close(self):
        self.transport.close()
