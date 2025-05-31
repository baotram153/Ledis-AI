from ledis.eviction.algos.rl_env.env import EvictionEnv
from ledis.eviction.metrics import EvictionMetrics
from ledis.parser import CommandParser

from pathlib import Path
import logging
import argparse

from stable_baselines3 import PPO

import wandb

def main():
    # -------------- Argument Parsing --------------
    parser = argparse.ArgumentParser(description="Evaluate a reinforcement learning model for eviction policy")
    parser.add_argument("--window", type=int, default=10, help="Eviction window size")
    parser.add_argument("--n_keys", type=int, default=10, help="Number of keys as input features")
    parser.add_argument("--n_timesteps", type=int, default=300000, help="Total timesteps for training")
    args = parser.parse_args()
    
    
    trace_file = "workload.txt"
    capacity = args.window
    eviction_window = args.n_keys
    total_timesteps = args.n_timesteps
    
    model_path = "ledis/eviction/algos/rl_ckpt/model"

    wandb.init(
        project="ledis-eviction-rl",    # change to your project name
        name="ppo-eviction-run-1",      # optional, a unique run name
        config={
            "capacity": capacity,
            "eviction_window": eviction_window,
            "total_timesteps": total_timesteps,
            "learning_rate": 3e-5,
            "n_steps": 2048,
            "batch_size": 64,
            "ent_coef": 0.01,
            "tensorboard_log": "tensorboard_logs",  # path to save tensorboard logs
        }
        )

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)


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

    trace = load_trace(trace_file)


    # -------------- Evaluation --------------

    eval_env = EvictionEnv(trace, capacity=capacity, window_size=eviction_window)
    model = PPO.load(model_path, env=eval_env)
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
    
if __name__ == "__main__":
    main()