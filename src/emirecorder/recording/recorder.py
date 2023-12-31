import asyncio
import secrets
from datetime import timedelta
from uuid import UUID

from pydantic import NaiveDatetime
from pystreams.stream import Stream
from zoneinfo import ZoneInfo

from emirecorder.config.models import Config
from emirecorder.emishows.models import Event, EventInstance, EventSchedule
from emirecorder.emishows.service import EmishowsService
from emirecorder.locks.base import Lock
from emirecorder.recording.errors import (
    InstanceNotFoundError,
    NoPortsAvailableError,
)
from emirecorder.recording.models import Credentials, Format, Request, Response
from emirecorder.recording.runner import StreamRunner
from emirecorder.stores.base import Store
from emirecorder.time import utcnow, utczone


class Recorder:
    """Manages recordings."""

    def __init__(
        self,
        config: Config,
        store: Store[set[int]],
        lock: Lock,
        emishows: EmishowsService,
    ) -> None:
        self._config = config
        self._store = store
        self._lock = lock
        self._emishows = emishows

    def _get_reference_time(self) -> NaiveDatetime:
        """Returns a reference time for finding the nearest event instance."""

        return utcnow().replace(tzinfo=None)

    def _get_time_window(
        self, reference: NaiveDatetime
    ) -> tuple[NaiveDatetime, NaiveDatetime]:
        """Returns a time window for searching for event instances."""

        start = reference - self._config.recorder.window
        end = reference + self._config.recorder.window

        return start, end

    async def _get_schedule(
        self, event: UUID, start: NaiveDatetime, end: NaiveDatetime
    ) -> EventSchedule:
        """Returns the schedule for an event."""

        event = str(event)

        response = await self._emishows.schedule.list(
            start=start, end=end, where={"id": event}
        )

        schedule = next(
            (schedule for schedule in response.schedules if schedule.event.id == event),
            None,
        )

        if schedule is None:
            raise InstanceNotFoundError(event)

        return schedule

    def _find_nearest_instance(
        self, reference: NaiveDatetime, event: Event, instances: list[EventInstance]
    ) -> EventInstance:
        """Finds the nearest instance of an event."""

        def _compare(instance: EventInstance) -> timedelta:
            timezone = ZoneInfo(event.timezone)
            start = instance.start.replace(tzinfo=timezone)
            start = start.astimezone(utczone()).replace(tzinfo=None)
            return abs(start - reference)

        instance = min(instances, key=_compare, default=None)

        if instance is None:
            raise InstanceNotFoundError(UUID(event.id))

        return instance

    def _generate_token(self) -> str:
        """Generates a token for credentials."""

        return secrets.token_hex(16)

    def _get_token_expiry(self) -> NaiveDatetime:
        """Returns the expiry time for credentials."""

        return utcnow().replace(tzinfo=None) + self._config.recorder.timeout

    def _generate_credentials(self) -> Credentials:
        """Generates credentials for a recording."""

        return Credentials(
            token=self._generate_token(),
            expires_at=self._get_token_expiry(),
        )

    def _get_host(self) -> str:
        """Returns the host to use for a recording."""

        return self._config.recorder.host

    async def _reserve_port(self) -> int:
        """Reserves a port for a recording."""

        async with self._lock:
            used = await self._store.get()
            available = self._config.recorder.ports - used

            if not available:
                raise NoPortsAvailableError()

            port = available.pop()

            await self._store.set(used | {port})

        return port

    async def _free_port(self, port: int) -> None:
        """Marks a port as free."""

        async with self._lock:
            used = await self._store.get()
            used.remove(port)
            await self._store.set(used)

    async def _watch_stream(self, stream: Stream, port: int) -> None:
        """Watches a stream and frees the port when it ends."""

        try:
            await stream.wait()
        finally:
            await self._free_port(port)

    async def _run(
        self,
        event: Event,
        instance: EventInstance,
        credentials: Credentials,
        host: str,
        port: int,
        format: Format,
    ) -> None:
        """Runs a recording."""

        runner = StreamRunner(self._config)
        stream = await runner.run(
            event=event,
            instance=instance,
            credentials=credentials,
            host=host,
            port=port,
            format=format,
        )

        asyncio.create_task(self._watch_stream(stream, port))

    async def record(self, request: Request) -> Response:
        """Starts a recording stream."""

        reference = self._get_reference_time()
        start, end = self._get_time_window(reference)

        schedule = await self._get_schedule(request.event, start, end)
        instance = self._find_nearest_instance(
            reference, schedule.event, schedule.instances
        )

        credentials = self._generate_credentials()
        host = self._get_host()
        port = await self._reserve_port()

        try:
            await self._run(
                schedule.event, instance, credentials, host, port, request.format
            )

            return Response(credentials=credentials, host=host, port=port)
        except Exception:
            await self._free_port(port)
            raise
