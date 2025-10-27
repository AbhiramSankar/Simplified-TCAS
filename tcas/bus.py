# A tiny pub/sub event bus to keep layers decoupled.
from typing import Callable, Dict, List

class EventBus:
    def __init__(self) -> None:
        self._subs: Dict[str, List[Callable]] = {}

    def on(self, topic: str, fn: Callable):
        self._subs.setdefault(topic, []).append(fn)

    def emit(self, topic: str, *args, **kwargs):
        for fn in self._subs.get(topic, []):
            fn(*args, **kwargs)
