"""
HYBRID EVICTION ALGORITHM
- Idea: Initialize the weights for 2 experts (LRU and LFU) as equal -> use RL to update the weights based the performance
- Reward / penalty based on
- 
"""

from collections import deque, defaultdict
import random
from typing import Union
from ledis.datastore import DataStore

import logging
logger = logging.getLogger(__name__)

class HybridEviction:
    def __init__(self, capacity: int, kv_store: DataStore, lr: float=0.05, delta: int = 10) -> None:
        self._capacity = capacity
        self._kv_store = kv_store
        
        # expert 1: LRU queue (from least to most recently used -> evict head)
        self._lru_queue = list()
        
        # expert 2: LFU queue (from least to most frequently used -> evict head)
        self._freq_map: defaultdict[str, int] = defaultdict(int)
        
        # rl weights
        self._weights = {"lru": 0.8, "lfu": 0.2}
        self._evicted_by: dict[str, str] = {}   # key -> expert that evicted it
        self._lr = lr
        self._epsilon = 1e-5    # avoid divison by zero
        
        # params for metric calculation
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._n_evicts = 0
        self._delta = delta
        self._recently_evicted = deque(maxlen=self._delta)
        self._n_reuse_evicts = 0
        self._penalize = False
        
    # ----------------------- HELPERS -----------------------
    def get_policy_weights(self) -> dict:
        return self._weights
    
    def get_metrics(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "n_evicts": self._n_evicts,
            "n_reuse_evicts": self._n_reuse_evicts,
            "policy_weights": self._weights,
        }
        
    def _touch_lru(self, key: str):
        """
        Update the LRU queue by moving the key to the end (most recently used).
        """
        if key in self._lru_queue:
            self._lru_queue.remove(key)
        self._lru_queue.append(key)
        
    def _update_weights(self, penalized_expert: str):
        """
        Multiplicative weight update for the penalized expert.
        """
        self._weights[penalized_expert] = max(
            self._weights[penalized_expert] * (1 - self._lr), self._epsilon
        )
        
        # renormalize
        total = self._weights["lru"] + self._weights["lfu"]
        self._weights["lru"] /= total
        self._weights["lfu"] /= total     
        logger.debug(f"Updated weights: {self._weights} - Penalized expert: {penalized_expert}")
        
    # --------------------- MAIN UPDATE LOGIC --------------------
    def update(self, key, is_set: bool) -> Union[str, None]:
        """
        Update both the LRU and LFU queues with the given key.
        """
        key_list = self._kv_store._get_key_list()
        key_len = self._kv_store._get_key_len()
        
        logger.debug(f"Key length: {key_len}, Key list: {key_list}")
        
        in_cache = key in key_list
        
        # update metrics
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
                    logger.debug(f"Key {key} was recently evicted, incrementing reuse evicts.")
                    self._n_reuse_evicts += 1
                    
                penalized_expert = self._evicted_by[key]
                if penalized_expert:
                    self._update_weights(penalized_expert) 
                    self._penalize = True
        
        # logger.debug(f"Recently evicted keys: {self._recently_evicted}")
        # logger.debug(f"Is set: {is_set}, Key: {key}, In cache: {in_cache}")
        
        # penalty for bad eviction
        if not is_set:
            if (not in_cache) and (key in self._recently_evicted):
                penalized_expert = self._evicted_by[key]
                if penalized_expert:
                    self._update_weights(penalized_expert)  # rl update
                    self._penalize = True

        if self._penalize:
            self._evicted_by.pop(key, None)  # remove key from evicted_by
            self._penalize = False
                    
        # sync with kv_store (expiration)
        self._lru_queue = [k for k in self._lru_queue if k in key_list]
        self._freq_map = defaultdict(int, {k: v for k, v in self._freq_map.items() if k in key_list})
        
        logger.debug(f"is_set: {is_set}, Key: {key}, In cache: {in_cache}")
                    
        # update LRU and LFU queues
        if is_set:
            if key in self._lru_queue:
                logger.debug(f"LRU queue: {self._lru_queue}")
                # key already in LRU queue, move it to the end
                self._lru_queue.remove(key) 
            else:
                self._freq_map[key] = 0
            self._lru_queue.append(key)
            logger.debug(f"Frequency map: {self._freq_map}")
            self._freq_map[key] += 1  # increment frequency for LFU
            logger.debug(f"Capacity: {self._capacity}")
            # evict if exceeding capacity
            if len(key_list) >= self._capacity:
                logger.debug(f"Cache capacity exceeded: {self._capacity}. Evicting key...")
                return self.evict()    # only return key when evicted, else None
                
        else: # if it's a get
            if not in_cache:
                # key not in cache, nothing to do
                return None
            self._touch_lru(key)  # update LRU queue
            self._freq_map[key] += 1
            
        return None
    
    def evict(self) -> str:
        """
        Choose victim based on weighted random selection of the two experts.
        """
        
        # expert proposals
        lru_victim = self._lru_queue[0] if self._lru_queue else None
        lfu_victim = min(self._freq_map, key=self._freq_map.get) if self._freq_map else None
        
        victim_policy = random.choices(
            list(self._weights.keys()),
            weights=list(self._weights.values()),
            k=1
        )[0]
        
        victim = lru_victim if victim_policy == "lru" else lfu_victim
        
        # perform eviction in lru and lfu
        if victim in self._lru_queue:
            self._lru_queue.remove(victim)
        self._freq_map.pop(victim, None)
        
        self._kv_store.delete_key(victim)
        
        # bookeeping
        self._n_evicts += 1
        self._recently_evicted.append(victim)
        self._evicted_by[victim] = victim_policy
        
        logger.debug(f"Evicted key: {victim} by {victim_policy} policy")
        
        return victim