import gymnasium as gym
import numpy as np

from ledis.datastore import DataStore
from ledis.eviction.algos.lru import LRU
from ledis.eviction.metrics import EvictionMetrics

import wandb

import logging
logger = logging.getLogger(__name__)

class EvictionEnv(gym.Env):
    def __init__(self,
                 trace: list,
                 capacity: int = 10,
                 window_size: int = 10) -> None:
        super().__init__()
        self.trace = trace # list of keys
        self.capacity = capacity
        self.window_size = window_size
        
        self.kv_store = DataStore()
        self.lru = LRU(capacity, self.kv_store)
        
        # observation: n_keys * 3 + eviction_window
        obs_dim = self.window_size*3+1
        self.observation_space = gym.spaces.Box(low=0, high=1, shape=(obs_dim,), dtype=np.float32)
        
        # action: index in [0, window_size)
        self.action_space = gym.spaces.Discrete(self.window_size)
        
        self.pos = 0    # current index in trace
        self.done = False
        
    def reset(self, seed: int = None):
        self.kv_store = DataStore()
        self.lru = LRU(self.capacity, self.kv_store)
        self._dispatch = {
            "set": self.kv_store.set,
            "get": self.kv_store.get,
            "expire": self.kv_store.set_expire,
        }
        self.pos = 0
        self.done = False
        return self._get_observation(), {}
    
    def step(self, action: int):
        if self.done:
            raise RuntimeError("Environment is done. Please reset it.")
        
        # perform operations until eviction
        evicted = None
        while self.pos < len(self.trace) and evicted is None:
            cmd, args, is_set = self.trace[self.pos]
            if not isinstance(args, (list, tuple)):
                args = [args]
            # update the KV store
            # logger.debug(f"Dispatching {cmd}({args})")
            self._dispatch[cmd](*args)
            # logger.debug(f"KV store state: {self.kv_store._get_key_list()}")
                
            # update LRU
            key = args[0]
            evicted = self.lru.update(key, is_set)
            self.pos += 1
        
        if evicted is None:
            self.done = True
            metrics = self.lru.get_metrics()
            eviction_metrics = EvictionMetrics(metrics)
            wandb.log({
                "train/episode_length": self.pos,
                "train/hit_ratio": eviction_metrics.hit_ratio(),
                "train/accuracy": eviction_metrics.accuracy()
            })
            return self._get_observation(), 0, self.done, False, {}
        
        # agent decides which key to evict
        victim = self._select_victim(action)
        
        # force the eviction in lru
        self.lru._lru_queue.remove(victim)
        self.lru._lru_queue.insert(0, victim)  # add evicted key to the front
        actual_eviction = self.lru.evict()
        assert actual_eviction == victim, f"Eviction mismatch! {actual_eviction} != {victim}"
        
        # compute reward: -1 if the victim is reused in next window_size operations, else + 1
        reused = self._simulate_reuse(victim)
        reward = -1 if reused else 1
        
        # prepare next observation
        obs = self._get_observation()
        self.done = self.pos >= len(self.trace)
        
        # sync lru with kv_store
        self.lru._lru_queue = [k for k in self.lru._lru_queue if k in self.kv_store._get_key_list()]
        
        return obs, reward, self.done, False, {}
    
    def _get_observation(self):
        # build featuure vector for current eviction candidates
        candidates = self._lru_candidates()
        features = []
        for k in candidates:
            metadata = self.lru.get_metadata(k)    # implement in DataStore
            features.extend([metadata.last_access, metadata.hits, metadata.sets])
        
        # pad if fewer than window_size
        while len(features) < self.window_size * 3:
            features.extend([0, 0, 0])
        features.append(float(self.capacity))
        return np.array(features, dtype=np.float32)
    
    def _lru_candidates(self):
        return list(self.lru._lru_queue)[:self.window_size]
    
    def _select_victim(self, action: int):
        candidates = self._lru_candidates()
        if action < 0 or action >= len(candidates):
            return candidates[0]    # fallback to lru algo
        return candidates[action]
    
    def _simulate_reuse(self, victim: str):
        # look ahead in the trace to see if victim is reused
        look_ahead = self.trace[self.pos:self.pos + self.window_size]
        return any(key == victim and not is_set for key,_,is_set in look_ahead)