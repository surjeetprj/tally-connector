"""Shared one-attempt external create lifecycle for experiment and real transfer."""
from innoforia_tally_connector.domain.experiments import UncertainWrite, WriteRejected


def apply_once(store, command, record, preflight, create):
    if record.attempted:
        return record
    preview = record.preview
    store.begin_attempt(preview, command, preflight)
    try:
        target = create(preview, preflight)
    except WriteRejected as error:
        store.result(preview.id, command.id, "FAILED", message=str(error))
    except UncertainWrite as error:
        store.result(preview.id, command.id, "OUTCOME_UNKNOWN", target=error.target, message=str(error))
    except Exception:
        store.result(preview.id, command.id, "OUTCOME_UNKNOWN",
                     message="Creation may have started; do not create again. Reconcile through reads only.")
    else:
        # Receipt first. No further external IO before the destination identity is durable.
        store.result(preview.id, command.id, "VERIFYING", target=target, message="Create receipt saved; detail verification pending")
    return store.get(preview.id, preview.binding)
