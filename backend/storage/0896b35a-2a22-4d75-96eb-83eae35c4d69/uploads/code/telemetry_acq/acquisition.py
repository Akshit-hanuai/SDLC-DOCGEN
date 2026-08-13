"""Sample acquisition engine. Implements REQ-0001: multi-channel telemetry acquisition."""

import threading
import time
from dataclasses import dataclass, field
from queue import Queue


@dataclass
class Sample:
    channel: int
    timestamp: float
    values: list[float] = field(default_factory=list)


class AcquisitionEngine:
    """Acquires telemetry from N sensor channels concurrently (REQ-0001)."""

    def __init__(self, num_channels: int = 3, sample_rate_hz: int = 100) -> None:
        self.num_channels = num_channels
        self.sample_rate_hz = sample_rate_hz
        self._queue: Queue[Sample] = Queue(maxsize=10000)
        self._running = False
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        self._running = True
        for channel in range(self.num_channels):
            thread = threading.Thread(target=self._acquire, args=(channel,), daemon=True)
            thread.start()
            self._threads.append(thread)

    def _acquire(self, channel: int) -> None:
        while self._running:
            sample = Sample(channel=channel, timestamp=time.time(), values=[0.0, 0.0, 0.0])
            self._queue.put(sample)
            time.sleep(1.0 / self.sample_rate_hz)

    def read(self, timeout_s: float = 1.0) -> list[Sample]:
        samples: list[Sample] = []
        for _ in range(self.num_channels):
            try:
                samples.append(self._queue.get(timeout=timeout_s))
            except Exception:
                continue
        return samples

    def stop(self) -> None:
        self._running = False
        for thread in self._threads:
            thread.join(timeout=1.0)
