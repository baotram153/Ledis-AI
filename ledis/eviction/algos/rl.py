# ledis/eviction/algos/rl.py
from __future__ import annotations
import time
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)

import numpy as np
from stable_baselines3 import PPO

from .lru import LRU, KeyMetadata


class RL(LRU):
    """
    Learned eviction that falls back to pure LRU when:
        - model size is missing
        - observation space cannot be built
    """

    def __init__(
        self,
        capacity: int,
        kv_store,
        *,
        model_path: str | Path = "ledis/eviction/algos/rl_ckpt/model",
        window_size: int = 10,
        device: str = "cpu",
    ) -> None:
        super().__init__(capacity, kv_store)
        self.window_size = window_size

        try:
            self._policy = PPO.load(model_path, device=device)
            self._enabled = True
        except Exception as exc:
            # model not found / incompatible -> fall back to LRU
            print(f"[RL-Eviction] Could not load PPO model ({exc}); "
                  f"running as pure LRU.")
            self._policy = None
            self._enabled = False

    def update(self, key: str, is_set: bool):
        # update metadata for the key, haven't removed victim yet
        super()._touch(key, is_set)

        if len(self._lru_queue) <= self._capacity:
            return None          # cache not full yet

        if self._enabled and len(self._lru_queue) >= 1:
            victim = self._select_victim_rl()
            logger.debug(f"Action selected by RL policy: {victim}")
        else:
            victim = self._lru_queue[0]   # plain LRU

        # actually remove from LRU queue
        self._lru_queue.remove(victim)
        self._lru_queue.insert(0, victim)
        evicted = self.evict()            
        return evicted

    def _select_victim_rl(self) -> str:
        """
        Build the same feature vector your `EvictionEnv` expects,
        run the PPO policy, map action -> key.
        """
        candidates = list(self._lru_queue)[: self.window_size]
        obs: List[float] = []

        for k in candidates:
            md: KeyMetadata = self._key_metadata.get(k, KeyMetadata())
            obs.extend([md.last_access, md.hits, md.sets])

        # pad to fixed length
        while len(obs) < self.window_size * 3:
            obs.extend([0.0, 0.0, 0.0])
        obs.append(float(self._capacity))

        obs_array = np.array(obs, dtype=np.float32)
        action, _ = self._policy.predict(obs_array, deterministic=True)

        # map action index to key; fall back to LRU on bad index
        if 0 <= action < len(candidates):
            return candidates[action]
        return candidates[0]
