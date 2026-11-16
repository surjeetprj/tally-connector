"""A failed history-detail capture must not strand its record's refresh action."""
from innoforia_tally_connector.execution.consumer import Runtime


def test_failed_capture_can_be_retried_for_same_history_record(qtbot, tmp_path):
    events = []
    class FailedStore:
        def recover(self, links): pass
        def pending(self): return []
        def capture(self, command): raise RuntimeError("storage busy")
    runtime = Runtime(tmp_path, FailedStore(), None, lambda command: None, events.append)
    try:
        first = runtime.submit("ACTIVITY_DETAIL", 1, experiment_id="record")
        qtbot.waitUntil(lambda: len(events) == 1)
        second = runtime.submit("ACTIVITY_DETAIL", 1, experiment_id="record")
        qtbot.waitUntil(lambda: len(events) == 2)
        assert first != second and all(event.error for event in events)
        assert not runtime.inflight
    finally:
        runtime.shutdown(runtime.queue.storage.close)
        qtbot.waitUntil(runtime.closed.is_set, timeout=10000)
