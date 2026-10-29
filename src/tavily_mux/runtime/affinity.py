from collections import OrderedDict
from collections.abc import Callable

AffinitySink = Callable[[str, str, str], bool]


class AffinityRegistry:
    def __init__(
        self,
        *,
        persistent: dict[tuple[str, str], str] | None = None,
        sink: AffinitySink | None = None,
        max_ephemeral: int = 50_000,
    ) -> None:
        self._persistent = persistent or {}
        self._ephemeral: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._sink = sink
        self._max_ephemeral = max_ephemeral

    def key_id(self, pool_id: str, resource_id: str) -> str | None:
        affinity = (pool_id, resource_id)
        ephemeral = self._ephemeral.get(affinity)
        if ephemeral is not None:
            self._ephemeral.move_to_end(affinity)
            return ephemeral
        return self._persistent.get(affinity)

    def remember(
        self,
        pool_id: str,
        resource_id: str,
        key_id: str,
        *,
        persist: bool,
    ) -> None:
        affinity = (pool_id, resource_id)
        if persist:
            self._persistent[affinity] = key_id
            if self._sink is not None:
                self._sink(pool_id, resource_id, key_id)
            return

        self._ephemeral[affinity] = key_id
        self._ephemeral.move_to_end(affinity)
        while len(self._ephemeral) > self._max_ephemeral:
            self._ephemeral.popitem(last=False)
