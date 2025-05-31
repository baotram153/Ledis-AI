from ledis.eviction.algos.rl import EvictionEnv
from ledis.eviction.metrics import EvictionMetrics
from ledis.parser import CommandParser

from pathlib import Path
import logging

from stable_baselines3 import PPO

import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

trace_file = "workload.txt"
capacity = 20
eviction_window = 10
total_timesteps = 20000
model_path = "ppo_eviction"


def load_trace(path: str):
    parser = CommandParser()
    trace = []  # list of (key, is_set)
    with Path(path).expanduser().open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cmd, args = parser.parse(line)
            if cmd == "set":
                trace.append((cmd, args, True))
            elif cmd == "get":
                trace.append((cmd, args, False))
            # skip other commands (expire, etc.)
    return trace

# Load workload trace
trace = load_trace(trace_file)


# -------------- Evaluation --------------
# Create a fresh env for evaluation
eval_env = EvictionEnv(trace, capacity=capacity, window_size=eviction_window)
model = PPO.load("ppo_eviction.zip", env=eval_env)
obs, _ = eval_env.reset()
done = False

while not done:
    action, _ = model.predict(obs)
    obs, _, done, _, _ = eval_env.step(int(action))

# Collect metrics
metrics = eval_env.lru.get_metrics()                         
eviction_metrics = EvictionMetrics(metrics)

hit_ratio = eviction_metrics.hit_ratio()
accuracy = eviction_metrics.accuracy()

print(metrics)
print(hit_ratio)
print(accuracy)

logger.info("Evaluation completed.")                
logger.info(f"Metrics: {metrics}")
logger.info(f"Hit Ratio: {hit_ratio:.4f}")
logger.info(f"Accuracy: {accuracy:.4f}")