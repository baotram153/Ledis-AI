"""
Base LFU eviction algorithm implementation
"""
from collections import defaultdict, deque
from ledis.datastore import DataStore

import logging
logger = logging.getLogger(__name__)

class LFU:
    def __init__(self, capacity: int, kv_store: DataStore, delta: int = 10) -> None:
        self._capacity    = capacity
        self._kv_store    = kv_store  # reference to store

        # LFP params
        self._freq_map    : dict[str, int]       = {}  # mapping for key to freq
        self._groups      : dict[int, deque[str]] = defaultdict(deque)
        self._min_freq    : int                  = 0   # smallest freq present

        # metrics
        self._hits        = 0
        self._misses      = 0
        self._sets        = 0
        self._n_evicts    = 0
        self._delta       = delta
        self._recently_evicted = deque(maxlen=self._delta)
        self._n_reuse_evicts   = 0

    def get_metrics(self) -> dict:
        return {
            "hits"           : self._hits,
            "misses"         : self._misses,
            "sets"           : self._sets,
            "n_evicts"       : self._n_evicts,
            "n_reuse_evicts" : self._n_reuse_evicts,
            "delta"          : self._delta,
        }

    def update(self, key: str, is_set: bool) -> str | None:
        key_list = self._kv_store._get_key_list()   # live keys in datastore
        in_cache = key in key_list
        
        # logger.info(f"freq_map: {self._freq_map}")

        # ----------------- METRIC BOOKKEEPING ---------------------
        if is_set:
            self._sets += 1
            if key in self._recently_evicted:
                self._recently_evicted.remove(key)
        else:
            if in_cache:
                self._hits += 1
            else:
                self._misses += 1
                if key in self._recently_evicted:
                    self._n_reuse_evicts += 1

        # ------------ NORMAL LFU BOOKKEEPING --------------------
        logger.info(f"In cache: {in_cache}")
        if key in self._freq_map:
            # key already cached -> bump its frequency
            self._increment_freq(key)
        else:
            if not is_set:                   # GET miss on absent key -> done
                return None

            # Insert new key; evict if full first
            if len(self._freq_map) >= self._capacity:
                victim = self._evict()
            else:
                victim = None
            self._add_new_key(key)

        # sync kv_store with freq_map
        self._remove_stale_keys(key_list)

        return victim

    # helpers
    def _increment_freq(self, key: str) -> None:
        """Move key from freq f to f+1 while preserving LRU order."""
        f = self._freq_map[key]
        self._groups[f].remove(key)
        if not self._groups[f]:
            del self._groups[f]
            if self._min_freq == f:
                self._min_freq += 1

        new_f = f + 1
        self._freq_map[key] = new_f
        self._groups[new_f].append(key)

    def _add_new_key(self, key: str) -> None:
        """Add a brand-new key with frequency = 1."""
        logger.info(f"Adding new key: {key} with frequency 1")
        self._freq_map[key] = 1
        self._groups[1].append(key)
        self._min_freq = 1

    def _evict(self) -> str:
        """
        Remove key with loweest frequency from freq_map and kv_store.
        """
        logger.info(f"Freq map before eviction: {self._freq_map}")
        victims = self._groups[self._min_freq]
        victim  = victims.popleft()               # oldest within min-freq
        if not victims:
            del self._groups[self._min_freq]

        # delete from bookkeeping
        del self._freq_map[victim]

        # delete from datastore
        self._kv_store.delete_key(victim)

        # metrics
        self._n_evicts += 1
        self._recently_evicted.append(victim)
        logger.info(f"Evicting key: {victim} with frequency {self._min_freq}")
        return victim

    def _remove_stale_keys(self, live_keys: list[str]) -> None:
        """
        Purge bookkeeping for keys that disappeared from kv_store
        (expired, deleted externally, etc.).
        """
        live_set = set(live_keys)
        for key in list(self._freq_map.keys()):
            if key not in live_set:
                freq = self._freq_map.pop(key)
                bucket = self._groups[freq]
                try:
                    bucket.remove(key)
                    if not bucket:
                        del self._groups[freq]
                except ValueError:
                    pass
        # recompute _min_freq if the old bucket vanished
        if self._min_freq not in self._groups and self._groups:
            self._min_freq = min(self._groups.keys())