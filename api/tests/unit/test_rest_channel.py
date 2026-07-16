from sentinel_detect.alerts.rest_channel import AlertStore, RestAlertChannel
from sentinel_detect.config.settings import AlertChannelSettings
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType


def _event(camera_id: str = "cam-1") -> Event:
    return Event(
        camera_id=camera_id,
        type=EventType.PERSON_DETECTED,
        severity=EventSeverity.INFO,
        rule="person_detected",
        message="a person was detected",
    )


def test_alert_store_recent_returns_most_recent_first() -> None:
    store = AlertStore(max_size=10)
    first, second, third = _event("cam-1"), _event("cam-2"), _event("cam-3")

    store.add(first)
    store.add(second)
    store.add(third)

    assert store.recent() == [third, second, first]


def test_alert_store_recent_respects_limit() -> None:
    store = AlertStore(max_size=10)
    for _ in range(5):
        store.add(_event())

    assert len(store.recent(limit=2)) == 2


def test_alert_store_is_bounded() -> None:
    store = AlertStore(max_size=3)
    for _ in range(5):
        store.add(_event())

    assert len(store) == 3


async def test_rest_alert_channel_writes_into_the_shared_store() -> None:
    from sentinel_detect.alerts.resources import AlertResources
    from sentinel_detect.alerts.websocket_channel import ConnectionManager

    store = AlertStore()
    resources = AlertResources(connection_manager=ConnectionManager(), alert_store=store)
    channel = RestAlertChannel(AlertChannelSettings(), resources)
    event = _event()

    await channel.send(event)

    assert store.recent() == [event]
