"""
Base LRU eviction algorithm implementation.
"""

import time
from collections import deque
from ledis.datastore import DataStore

import logging
logger = logging.getLogger(__name__)

class KeyMetadata:
    """
    Per-key metadata: last access timestamp, hit count, set count. Used for RL
    """
    def __init__(self, last_access: float = 0.0, hits: int = 0, sets: int = 0) -> None:
        self.last_access = last_access
        self.hits = hits
        self.sets = sets

class LRU:
    """
    How to update the recently used keys when key expired
    """
    def __init__(self, capacity: int, kv_store: DataStore) -> None:
        self._capacity = capacity
        self._lru_queue = list()
        self._kv_store = kv_store  # Reference to the key-value store
        
        # params to calculate eviction metrics - global
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._n_evicts = 0
        self._delta = 10
        self._recently_evicted = deque(maxlen=self._delta)     # track if evicted key is reused within a time delta
        self._n_reuse_evicts = 0
        self.metadata = {}
        
        # per-key metadata
        self._key_metadata: dict[str, KeyMetadata] = {}
        
    def get_hits(self) -> int:
        return self._hits
    
    def get_sets(self) -> int:
        return self._sets
    
    def _touch(self, key: str, is_set: bool) -> None:
        """
        Update the LRU queue with the given key.
          - If the key is already in the queue, move it to the end.
          - If the key is not in the queue, add it to the end.
          - Sync queue with kv_store to ensure consistency.
        """
        current_time = time.time()
        # create or get the key metadata
        key_meta = self._key_metadata.get(key)
        if key_meta is None:
            key_meta = KeyMetadata()
            self._key_metadata[key] = key_meta
        key_meta.last_access = current_time   # update last access
        
        # --------------- METRICS BOOKKEEPING ------------------
        key_list = self._kv_store._get_key_list()
        key_len = self._kv_store._get_key_len()
        
        in_cache = key in key_list
        
        # logger.info(f"is set: {is_set}, in cache: {in_cache}, key: {key}, key list: {key_list}")
        if is_set:
            self._sets += 1
            key_meta.sets += 1  # update set count of key - used for RL
            if key in self._recently_evicted:
                self._recently_evicted.remove(key)       
        else:
            if in_cache:
                self._hits += 1
                key_meta.hits += 1  # update hit count of key - used for RL
            else:
                self._misses += 1 
                if key in self._recently_evicted:
                    self._n_reuse_evicts += 1
        
        # --------------- NORMAL LRU BOOKKEEPING ------------------
        if key in self._lru_queue:
            self._lru_queue.remove(key) 
            self._lru_queue.append(key)
        elif is_set:
            self._lru_queue.append(key)
        else:
            # get request for a key that doesn't exist
            return None
        
        # update LRU queue to sync with kv_stote (deletion or expiration noticed)
        if key_len < len(self._lru_queue):
            self._lru_queue = [k for k in self._lru_queue if k in key_list]
        logger.debug(f"LRU queue after touch: {self._lru_queue}")
        
        
    def update(self, key:str, is_set:bool) -> None:
        """
          - Call evict if the queue exceeds the capacity.
        """
        self._touch(key, is_set)
        # if lru queue exceeds capacity, evict the least recently used key
        logger.debug(f"LRU queue before eviction check: {self._lru_queue}, capacity: {self._capacity}")
        # if len(self._lru_queue) > self._capacity:
        #     key = self.evict()
        #     return key
        keys = []
        while len(self._lru_queue) > self._capacity:
            victim = self.evict()
            keys.append(victim)
        return keys
            
    def evict(self) -> str:
        """
        Evict the least recently used key from the queue and return it.
        """
        victim = self._lru_queue.pop(0)
        self._kv_store.delete_key(victim)
        self._n_evicts += 1
        self._recently_evicted.append(victim)
        return victim
    
    def get_metrics(self) -> dict:
        """
        Get the eviction metrics.
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "n_evicts": self._n_evicts,
            "n_reuse_evicts": self._n_reuse_evicts,
            "delta": self._delta,
        }
        
    def get_metadata(self, key:str) -> KeyMetadata:
        """
        Get the metadata for a given key. Used for RL
        """
        return self._key_metadata.get(key, KeyMetadata())