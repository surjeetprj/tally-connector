"""Private, bounded HTTP export transport. Imported only by the gateway."""
import time

import httpx

from innoforia_tally_connector.domain.errors import ReadError
from innoforia_tally_connector.integrations.tally.xml_codec import parse

MAX_BYTES = 8 * 1024 * 1024


class Transport:
    def __init__(self, client=None):
        self.client = client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)

    def export(self, request: bytes) -> bytes:
        if parse(request).findtext("HEADER/TALLYREQUEST") != "Export":
            raise ReadError("Only Tally exports are enabled")
        started = time.monotonic()
        try:
            with self.client.stream("POST", "http://localhost:9000", content=request,
                                    follow_redirects=False,
                                    headers={"Content-Type": "text/xml; charset=utf-8"}) as response:
                if response.status_code != 200:
                    raise ReadError(f"Tally read failed (HTTP {response.status_code})")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES or time.monotonic() - started > 15:
                        raise ReadError("Tally response exceeded read limits")
                return bytes(data)
        except httpx.HTTPError:
            raise ReadError("Tally is unavailable or the read timed out") from None

    def close(self):
        self.client.close()
