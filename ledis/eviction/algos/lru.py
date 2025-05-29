"""
Base LRU eviction algorithm implementation.
"""

from collections import deque
from ledis.datastore import DataStore

class LRU:
    """
    How to update the recently used keys when key expired
    """
    def __init__(self, capacity: int, kv_store: DataStore) -> None:
        self._capacity = capacity
        self._lru_queue = list()
        self._kv_store = kv_store  # Reference to the key-value store
        
    def update(self, key:str, is_set:bool) -> None:
        """
        Update the LRU queue with the given key.
          - If the key is already in the queue, move it to the end.
          - If the key is not in the queue, add it to the end.
          - Sync queue with kv_store to ensure consistency.
          - Call evict if the queue exceeds the capacity.
        """
        if key in self._lru_queue:
            self._lru_queue.remove(key) 
            self._lru_queue.append(key)
        elif is_set:
            self._lru_queue.append(key)
        else:
            # get request for a key that doesn't exist
            return None
        
        # update LRU queue to sync with kv_stote (deletion or expiration noticed)
        if self._kv_store._get_key_len() < len(self._lru_queue):
            self._lru_queue = [k for k in self._lru_queue if k in self._kv_store._get_key_list()]
            
        # if lru queue exceeds capacity, evict the least recently used key
        if len(self._lru_queue) > self._capacity:
            key = self.evict()
            return key
        return None
            
    def evict(self) -> str:
        """
        Evict the least recently used key from the queue and return it.
        """
        victim = self._lru_queue.pop(0)
        self._kv_store.delete_key(victim)
        return victim