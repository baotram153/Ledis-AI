"""
eviction.manager
================

SmartEvictionManager
--------------------
A pluggable eviction controller that can operate in three modes:

    • Disabled - behave as an infinite cache
    • Heuristic - pure LRU fallback (cold-start, model missing, errors)
    • Learned - LRU shortlist  → ML ranker  → victim
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Dict, Optional, Callable, List

# ──────────────────────────────────────────────────────────────
# Dependencies inside the eviction package
# ──────────────────────────────────────────────────────────────
try:
    from .features import extract_features          # feature vector builder
    from .model import EvictionModel                # sklearn/lightgbm wrapper
except ImportError:
    # In unit-test contexts where the ML stack is not installed
    extract_features = None
    EvictionModel = None

# ──────────────────────────────────────────────────────────────
# Configuration knobs (tweak via env-vars or import-level monkey-patching)
# ──────────────────────────────────────────────────────────────
_CANDIDATE_POOL = 32             # LRU shortlist length
_MIN_SAMPLES_TO_ENABLE = 10_000  # model must see this many labelled rows
_LOCK_TIMEOUT = 0.005            # seconds – prevents deadlocks in hot paths


# store per-key metadata
class _KeyMeta:
    __slots__ = ("last_access", "hits", "sets", "size")

    def __init__(self, now: float, size: int):
        self.last_access: float = now
        self.hits: int = 0
        self.sets: int = 1
        self.size: int = size
        
class SmartEvictionManager:
    """
    Wraps all eviction-related state.

    Parameters
    ----------
    kv_store : Dict[str, str | bytes | list]
        Reference to the dictionary the database uses internally.
    model_factory : Callable[[], EvictionModel], optional
        Lazy constructor so you can defer importing sklearn/lightgbm
        until the first time Smart Eviction is enabled.
    """

    # ------------------------------------------------------------------
    # ctor / enable / disable
    # ------------------------------------------------------------------
    def __init__(
        self,
        kv_store: Dict[str, object],
        *,
        model_factory: Optional[Callable[[], "EvictionModel"]] = None,
    ) -> None:
        self._kv = kv_store
        self._meta: Dict[str, _KeyMeta] = {}

        # runtime knobs
        self._enabled: bool = False
        self._limit: int = 0

        # LRU bookkeeping
        self._lru_q: "deque[str]" = deque()

        # ML components (lazily initialised)
        self._model_factory = model_factory or (lambda: EvictionModel())
        self._model: Optional["EvictionModel"] = None

        # thread-safety; the store itself can already be locked elsewhere
        self._lock = threading.RLock()

    def enable(self, limit: int) -> None:
        """
        Enable Smart Eviction with the given limit.
        A non-positive `limit` disables the feature.
        """
        if limit <= 0:
            self.disable()
            return

        with self._lock:
            self._enabled = True
            self._limit = limit
            if self._model is None:
                # create on first enable – expensive imports kept here
                self._model = self._model_factory()

    def disable(self) -> None:
        """Turn Smart Eviction off but keep learned state in memory."""
        with self._lock:
            self._enabled = False
            self._limit = 0

    # ------------------------------------------------------------------
    #  API used by command handlers
    # ------------------------------------------------------------------
    def record_access(self, key: str, *, op: str, value_len: int = 0) -> None:
        """
        Must be called on every successful command that touches *key*.

        Parameters
        ----------
        key : str
            The logical cache key.
        op  : {'get', 'set', 'list_read', 'list_write', 'del', ...}
            Operation category – influences which counters are incremented.
        value_len : int, optional
            Current size (bytes or list length) – only relevant for writes.
        """
        now = time.time()
        meta = self._meta.get(key)

        if meta is None:
            meta = self._meta[key] = _KeyMeta(now, value_len)
        else:
            meta.last_access = now

        if op.startswith("get") or op.endswith("_read"):
            meta.hits += 1
        elif op in ("set", "list_write"):
            meta.sets += 1
            meta.size = value_len
        # deletions are handled by `after_delete` (below)

        # super-cheap LRU queue maintenance (duplicates allowed)
        self._lru_q.append(key)

    def after_delete(self, key: str) -> None:
        """
        Remove metadata when a key is `DEL`ed explicitly or expires.
        """
        self._meta.pop(key, None)

    def enforce_limit(self) -> None:
        """
        Delete as many keys as necessary to ensure len(store) ≤ limit.
        Called after a *mutating* command is committed.
        """
        if not self._enabled:
            return

        acquired = self._lock.acquire(timeout=_LOCK_TIMEOUT)
        if not acquired:
            # give up quickly; worst case we exceed the limit momentarily
            return

        try:
            while len(self._kv) > self._limit:
                victim = self._pick_victim()
                if victim is None:           # should never happen
                    break
                self._kv.pop(victim, None)
                self._meta.pop(victim, None)
                print(
                    f"Smart eviction: Number of keys reached limit "
                    f"{self._limit}. Key `{victim}` has been evicted."
                )
        finally:
            self._lock.release()

    # ------------------------------------------------------------------
    #  Internals – victim selection
    # ------------------------------------------------------------------
    def _pick_victim(self) -> Optional[str]:
        """
        1. Take the *oldest* `_CANDIDATE_POOL` distinct keys from the LRU queue.
        2. If the ML model is ready → rank and return the worst one.
           Else → return the very oldest (pure LRU).
        """
        # Pull up to N unique keys that are still live
        candidates: List[str] = []
        seen = set()

        while self._lru_q and len(candidates) < _CANDIDATE_POOL:
            k = self._lru_q.popleft()
            if k in self._kv and k not in seen:
                candidates.append(k)
                seen.add(k)

        if not candidates:
            return None

        # ----------------------------- ML branch ---------------------------------
        if (
            self._model is not None
            and self._model.num_samples_seen >= _MIN_SAMPLES_TO_ENABLE
        ):
            try:
                feats = [extract_features(k, self._meta[k]) for k in candidates]
                proba = self._model.predict_proba(feats)[:, 1]  # P(will-be-reused)
                victim = candidates[int(proba.argmin())]
                return victim
            except Exception as ex:  # pylint: disable=broad-exception-caught
                # Fallback silently to LRU; log locally if you have logging_conf
                print(f"[SmartEviction] model failure → LRU fallback ({ex})")

        # -- LRU branch -------------------------------------------------
        return candidates[0]

    # ------------------------------------------------------------------
    #  Misc helpers (optional, e.g. for admin commands)
    # ------------------------------------------------------------------
    @property
    def status(self) -> str:
        mode = (
            "disabled"
            if not self._enabled
            else "ml" if self._model and self._model.num_samples_seen >= _MIN_SAMPLES_TO_ENABLE
            else "lru"
        )
        return f"{mode}(limit={self._limit})"

    def dump_stats(self) -> Dict[str, object]:
        """Return a JSON-serialisable snapshot for introspection."""
        return {
            "enabled": self._enabled,
            "limit": self._limit,
            "keys_tracked": len(self._meta),
            "lru_queue_len": len(self._lru_q),
            "model_samples": self._model.num_samples_seen if self._model else 0,
        }