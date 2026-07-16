from sentinel_detect.core.entities.alert import AlertChannelType, AlertStatus
from sentinel_detect.core.entities.event import Event, EventSeverity, EventType
from sentinel_detect.core.exceptions import AlertDeliveryError
from sentinel_detect.core.interfaces.alert_channel import BaseAlertChannel
from sentinel_detect.services.alert_engine import AlertEngine


class _RecordingChannel(BaseAlertChannel):
    channel_type = AlertChannelType.REST

    def __init__(self) -> None:
        self.sent: list[Event] = []

    async def send(self, event: Event) -> None:
        self.sent.append(event)


class _FailingChannel(BaseAlertChannel):
    channel_type = AlertChannelType.WEBHOOK

    async def send(self, event: Event) -> None:
        raise AlertDeliveryError("simulated delivery failure")


def _event(event_type: EventType = EventType.PERSON_DETECTED) -> Event:
    return Event(
        camera_id="cam-1",
        type=event_type,
        severity=EventSeverity.INFO,
        rule="person_detected",
        message="a person was detected",
    )


async def test_dispatch_sends_every_event_through_every_channel() -> None:
    channel_a = _RecordingChannel()
    channel_b = _RecordingChannel()
    engine = AlertEngine({"a": channel_a, "b": channel_b})
    event = _event()

    alerts = await engine.dispatch([event])

    assert channel_a.sent == [event]
    assert channel_b.sent == [event]
    assert len(alerts) == 2
    assert all(alert.status is AlertStatus.SENT for alert in alerts)
    assert all(alert.delivered_at is not None for alert in alerts)


async def test_dispatch_records_failure_without_stopping_other_channels() -> None:
    working = _RecordingChannel()
    failing = _FailingChannel()
    engine = AlertEngine({"working": working, "failing": failing})
    event = _event()

    alerts = await engine.dispatch([event])

    assert working.sent == [event]
    statuses = {alert.channel: alert.status for alert in alerts}
    assert statuses[AlertChannelType.REST] is AlertStatus.SENT
    assert statuses[AlertChannelType.WEBHOOK] is AlertStatus.FAILED
    failed_alert = next(a for a in alerts if a.channel is AlertChannelType.WEBHOOK)
    assert failed_alert.error is not None
    assert "simulated delivery failure" in failed_alert.error


async def test_dispatch_with_no_events_produces_no_alerts() -> None:
    engine = AlertEngine({"a": _RecordingChannel()})
    assert await engine.dispatch([]) == []


def test_active_channel_keys_is_sorted() -> None:
    engine = AlertEngine({"b": _RecordingChannel(), "a": _RecordingChannel()})
    assert engine.active_channel_keys() == ["a", "b"]
