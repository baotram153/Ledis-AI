import logging
from pathlib import Path
import argparse

import gymnasium as gym
import numpy as np

import os
import wandb
from wandb.integration.sb3 import WandbCallback
os.environ["WANDB_DISABLE_SYMLINK"] = "true"

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from ledis.parser import CommandParser
from ledis.eviction.algos.lru import LRU, KeyMetadata
from ledis.eviction.algos.rl_env.env import EvictionEnv
from ledis.eviction.metrics import EvictionMetrics

# -------------- Logging Setup --------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trainer.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------- Trace Loading --------------

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

# -------------- Trainer --------------

def main():
    # parse window size, n_keys
    parser = argparse.ArgumentParser(description="Train a reinforcement learning model for eviction policy")
    parser.add_argument("--window", type=int, default=10, help="Eviction window size")
    parser.add_argument("--n_keys", type=int, default=10, help="Number of keys as input features")
    parser.add_argument("--n_timesteps", type=int, default=300000, help="Total timesteps for training")
    
    args = parser.parse_args()
    
    # Configuration
    trace_file = "workload.txt"
    capacity = args.window
    window_size = args.n_keys
    total_timesteps = args.n_timesteps
    model_path = "ledis/eviction/algos/rl_ckpt/"
    
    # initialize wandb logging
    wandb.init(
    project="ledis-eviction-rl",    # change to your project name
    name="ppo-eviction-run-1",      # optional, a unique run name
    config={
        "capacity": capacity,
        "eviction_window": window_size,
        "total_timesteps": total_timesteps,
        "learning_rate": 3e-4,
        "n_steps": 2048,
        "batch_size": 64,
        "ent_coef": 0.01,
        "tensorboard_log": "tensorboard_logs",  # path to save tensorboard logs
    }
    )


    # Load workload trace
    trace = load_trace(trace_file)
    logger.info(f"Loaded trace with {len(trace)} operations.")

    # Create Gym environment factory
    def make_env():
        return EvictionEnv(trace, capacity=capacity, window_size=window_size)

    env = DummyVecEnv([make_env])

    # Instantiate PPO
    model = PPO(
        policy="MlpPolicy",
        env=env,
        verbose=1,
        learning_rate=wandb.config.learning_rate,
        n_steps=wandb.config.n_steps,
        batch_size=wandb.config.batch_size,
        ent_coef=wandb.config.ent_coef,
        tensorboard_log=wandb.config.tensorboard_log,
    )

    # train
    logger.info("Starting training...")
    model.learn(
        total_timesteps=total_timesteps,
        callback=WandbCallback(
            gradient_save_freq=1000,  # save gradients every 1000 steps
            model_save_path=model_path,
            verbose=1
        )
    )
    logger.info(f"Training completed; model saved to {model_path}.zip")
    
    wandb.finish()

if __name__ == "__main__":
    main()
