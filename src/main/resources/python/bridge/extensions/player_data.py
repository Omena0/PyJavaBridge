"""PlayerDataStore extension — persistent per-player key/value storage."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class PlayerDataStore:
    """Global per-player data store with dict-style access.

    Data is automatically saved to ``plugins/PyJavaBridge/playerdata/<name>.json``.

    Example::

        store = PlayerDataStore("stats")
        store[player]["kills"] = 10
        print(store[player]["kills"])  # 10
    """

    _DATA_DIR = "plugins/PyJavaBridge/playerdata"

    def __init__(self, name: str = "default"):
        self.name = name
        self._data: Dict[str, Dict[str, Any]] = {}
        self._dir = os.path.join(self._DATA_DIR, name)
        os.makedirs(self._dir, exist_ok=True)

    def _key(self, player: Any) -> str:
        uid = getattr(player, "uuid", None)
        if uid is None:
            uid = str(player)
        return str(uid)

    def _path(self, key: str) -> str:
        safe = key.replace("/", "_").replace("\\", "_").replace("..", "_")
        return os.path.join(self._dir, f"{safe}.json")

    def _load(self, key: str) -> Dict[str, Any]:
        if key in self._data:
            return self._data[key]
        path = self._path(key)
        if os.path.isfile(path):
            with open(path, "r") as f:
                self._data[key] = json.load(f)
        else:
            self._data[key] = {}
        return self._data[key]

    def _save(self, key: str):
        path = self._path(key)
        with open(path, "w") as f:
            json.dump(self._data.get(key, {}), f, indent=2, default=str)

    def __getitem__(self, player: Any) -> "_PlayerView":
        key = self._key(player)
        return _PlayerView(self, key)

    def __setitem__(self, player: Any, value: Dict[str, Any]):
        key = self._key(player)
        self._data[key] = dict(value)
        self._save(key)

    def get(self, player: Any, field: str, default: Any = None) -> Any:
        key = self._key(player)
        return self._load(key).get(field, default)

    def set(self, player: Any, field: str, value: Any):
        key = self._key(player)
        data = self._load(key)
        data[field] = value
        self._save(key)

    def delete(self, player: Any, field: Optional[str] = None):
        key = self._key(player)
        if field is None:
            self._data.pop(key, None)
            path = self._path(key)
            if os.path.isfile(path):
                os.remove(path)
        else:
            data = self._load(key)
            data.pop(field, None)
            self._save(key)

    def all_data(self, player: Any) -> Dict[str, Any]:
        return dict(self._load(self._key(player)))


class _PlayerView:
    """Proxy returned by ``store[player]`` for dict-like field access."""

    def __init__(self, store: PlayerDataStore, key: str):
        self._store = store
        self._key = key

    def __getitem__(self, field: str) -> Any:
        return self._store._load(self._key).get(field)

    def __setitem__(self, field: str, value: Any):
        data = self._store._load(self._key)
        data[field] = value
        self._store._save(self._key)

    def __delitem__(self, field: str):
        data = self._store._load(self._key)
        data.pop(field, None)
        self._store._save(self._key)

    def __contains__(self, field: str) -> bool:
        return field in self._store._load(self._key)

    def get(self, field: str, default: Any = None) -> Any:
        return self._store._load(self._key).get(field, default)

    def __repr__(self) -> str:
        return repr(self._store._load(self._key))
