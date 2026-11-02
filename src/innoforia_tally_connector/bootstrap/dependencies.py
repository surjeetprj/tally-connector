"""Own concrete clients/gateway; application and UI only see injected capabilities."""
from innoforia_tally_connector.application.masters.discovery import DiscoveryWorkflow
from innoforia_tally_connector.domain.masters import ConnectionSnapshot
from innoforia_tally_connector.execution.consumer import Runtime
from innoforia_tally_connector.host.windows.credentials import REFERENCE, read_key
from innoforia_tally_connector.integrations.bahi.client import Client
from innoforia_tally_connector.integrations.bahi.endpoints.parties import PartyReader as BahiReader
from innoforia_tally_connector.integrations.tally.gateway import Gateway
from innoforia_tally_connector.integrations.tally.parties import PartyReader as TallyReader, group_observations, validate_classification
from innoforia_tally_connector.persistence.database import metadata_engine
from innoforia_tally_connector.persistence.migrations.runner import migrate
from innoforia_tally_connector.persistence.repositories.discovery import DiscoveryStore
from innoforia_tally_connector.persistence.repositories.party_links import SqlPartyLinks


def build(directory, emit, credential=read_key, bahi_client=None, tally_gateway=None):
    engine = metadata_engine(directory / "sync_metadata.db")
    migrate(engine)
    store, links = DiscoveryStore(engine), SqlPartyLinks(engine)
    bahi = bahi_client or Client(credential)
    gateway = tally_gateway or Gateway()
    current = None
    runtime = None

    def progress(side, message):
        from innoforia_tally_connector.domain.commands import Event
        if current:
            emit(Event(current.id, current.generation, current.kind, f"{side}: {message}", final=False))

    def verify():
        business = bahi.business()
        company = gateway.read()[0]
        groups = group_observations(gateway.read("Group"))
        return ConnectionSnapshot(business_id=business["biz_id"], business_name=business["biz_name"],
            company_guid=company["GUID"], company_name=company["NAME"], groups=groups)

    def readers(classification):
        return (BahiReader(bahi, progress, lambda: runtime.stopping.is_set()),
                TallyReader(gateway, classification, progress))

    workflow = DiscoveryWorkflow(verify, readers, validate_classification, store, links, REFERENCE)

    def handle(command):
        nonlocal current
        current = command
        try:
            return workflow.handle(command)
        finally:
            current = None

    runtime = Runtime(directory, store, links, handle, emit)
    gateway.stopped = runtime.stopping.is_set
    bahi.stopped = runtime.stopping.is_set

    def cleanup():
        bahi.close()
        gateway.close()
        engine.dispose()

    return runtime, cleanup
