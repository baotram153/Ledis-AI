import logging
from ledis.datastore import DataStore

from ledis.eviction.algos.lru import LRU
# from ledis.eviction.algos.lfu import LFU
# from ledis.eviction.random import Random
# from ledis.eviction.rl import RL

from typing import Union, Optional

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
    def __init__(self, kv_store: DataStore, algo_name: str="lru", model=None):
        self._kv_store = kv_store
        self._algo_name = algo_name
        
        self._parser = {
            "lru": LRU,
            # "lfu": LFU,
            # "random": algos.random.Random,
            # "rl": algos.rl.RL
        }
        
        self._model = model
        
        self._eviction_window = 0

    def get_eviction_window(self) -> int:
        return self._eviction_window
        
    def set_eviction_window(self, window: str):
        """
        Set the eviction window size.
        """
        window = int(window)
        if window <= 0:
            raise ValueError("Eviction window must be a positive integer.")
        self._eviction_window = window
        self.set_algo(self._algo_name)
        return f"OK"
    
    def set_algo(self, algo_name: str="lru"):
        """
        Set the eviction algorithm to use.
        """
        if algo_name not in self._parser:
            raise ValueError(f"Unknown eviction algorithm: {algo_name}")
        
        self._algo = self._parser[algo_name](self._eviction_window, self._kv_store)
        
    def evict(self, key, is_set) -> Union[str, None]:
        """
        Call the eviction algorithm to evict a key.
        """
        evicted_key = self._algo.update(key, is_set)
        return evicted_key