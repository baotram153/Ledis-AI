"""
Script to benchmark the performance of the eviction algorithm.
"""
from ledis.eviction.manager import EvictionManager
from ledis.parser import CommandParser
from ledis.datastore import DataStore
from ledis.eviction.metrics import EvictionMetrics

import argparse

from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

import logging
logger = logging.getLogger(__name__)

# write log to a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("benchmark.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class Benchmarker:
    def __init__(self, db: DataStore, parser: CommandParser, eviction_manager: EvictionManager = None, eviction_window: int = 10):
        self._dispatch = {
            "set": db.set,
            "get": db.get,
            "expire": db.set_expire,
        }
        
        # must use data store to purge expired keys
        self._db = db
        self._parser = parser
        
        self._eviction_manager = eviction_manager
        self._eviction_enabled = True
        self._eviction_manager.set_eviction_window(eviction_window)
        
    def execute(self, command_str: str):
        """
        Execute a command on the database
        """
        logger.debug(f"Command string: {command_str}")
        try:
            cmd, args = self._parser.parse(command_str)
            logger.debug(f"Parsed command: {cmd} with args: {args}")
            if cmd in self._dispatch:
                
                # only dispatch the command, no need to get response
                self._dispatch[cmd](*args)
                
                # handle eviction if enabled
                key = args[0]
                is_set = 1 if cmd == "set" else 0
                evicted_keys = self._eviction_manager.evict(key, is_set)
                if evicted_keys != []:
                    limit = self._eviction_manager.get_eviction_window()
                    for evicted_key in evicted_keys:
                        result = f"\nSmart eviction: Number of keys reached limit {limit}. Key `{evicted_key}` has been evicted."
                    logger.info(result)
            else:
                logger.debug(f"Unknown command: {cmd}")
            
        except Exception as e:
            logger.debug(f"ERROR: {str(e)}")
            
def command_stream(path: str):
    with Path(path).expanduser().open("r") as f:
        for line in f:
            yield line.strip()

if __name__ == "__main__":
    # argument parser for choosing eviction algorithm
    parser = argparse.ArgumentParser(description="Benchmark eviction algorithms.")
    parser.add_argument(
        "--algo",
        type=str,
        choices=["lru", "lfu", "hybrid"],
        default="lru",
        help="Eviction algorithm to use (default: lru)"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=10,
        help="Eviction window size (default: 10)"
    )
    args = parser.parse_args()
    # initialize benchmarker
    data_store = DataStore()
    parser = CommandParser()
    eviction_manager = EvictionManager(data_store, algo_name=args.algo)
    
    # Create a benchmarker instance
    benchmarker = Benchmarker(data_store, parser, eviction_manager, args.window)
    
    # get commands from file
    for cmd in command_stream("workload.txt"):
        logger.info(f"Executing command: {cmd}")
        benchmarker.execute(cmd)
        
    # get metrics
    metric_dict = eviction_manager._algo.get_metrics()
    eviction_metrics = EvictionMetrics(metric_dict)
    
    hit_ratio = eviction_metrics.hit_ratio()
    accuracy = eviction_metrics.accuracy()
    
    logger.info("Benchmarking completed.")
    logger.info(f"Metrics collected: {metric_dict}")
    logger.info(f"Hit Ratio: {hit_ratio:.2f}")
    logger.info(f"Accuracy: {accuracy:.2f}")