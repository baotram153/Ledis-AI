import logging
from ledis.datastore import DataStore

from ledis.eviction.algos.lru import LRU
from ledis.eviction.algos.lfu import LFU
from ledis.eviction.algos.hybrid import HybridEviction
from ledis.eviction.algos.rl import RL

from typing import Union, Optional

logger = logging.getLogger(__name__)

class KeyMetadata:
    def __init__(self, last_accessed: float, hits: int, sets: int, ttl: int):
        self.last_accessed = last_accessed
        self.hits = hits
        self.sets = sets
        self.ttl = ttl

    def __repr__(self):
        return f"KeyMetadata(last_accessed={self.last_accessed}, hits={self.hits}, sets={self.sets}, ttl={self.ttl})"
    
class EvictionManager:
    """
    Input:
        - `kv_store`: DataStore instance that holds the key-value pairs.
        - `algo`: Eviction algorithm to use (e.g., LRU, LFU, etc.).
            + "lru", "lfu", "random", "rl"
        - `model`: machine learning model for smart eviction.
    """
    def __init__(self, kv_store: DataStore, algo_name: str="lru", eviction_window=10):
        self._kv_store = kv_store
        self._algo_name = algo_name
        
        self._parser = {
            "lru": LRU,
            "lfu": LFU,
            "hybrid": HybridEviction,
            "rl": RL,
        }
        
        self._algo = self._parser[algo_name](eviction_window, kv_store)  # default algo is LRU

    def get_eviction_window(self) -> int:
        return self._algo._capacity
        
    def set_eviction_window(self, window: str):
        """
        Set the eviction window size.
        """
        window = int(window)
        if window <= 0:
            # raise ValueError("Eviction window must be a positive integer.")
            window = 0  # window size < 0 meaning no eviction
        self._algo._capacity = window
        return f"OK"
    
    def set_algo(self, algo_name: str="lru"):
        """
        Set the eviction algorithm to use.
        """
        if algo_name not in self._parser:
            raise ValueError(f"Unknown eviction algorithm: {algo_name}")
        
        self._algo = self._parser[algo_name](self._eviction_window, self._kv_store)
        
    def update(self, key: str, is_set: bool) -> Optional[str]:
        """
        Update the eviction algorithm with the given key (update lru, lfu queue).
        """
        self._algo._touch(key, is_set)   
        
    def evict(self, key, is_set) -> Union[str, None]:
        """
        Call the eviction algorithm to evict a key.
        """
        evicted_key = self._algo.update(key, is_set)
        return evicted_key