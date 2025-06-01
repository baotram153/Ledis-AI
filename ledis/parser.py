from typing import Any, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)

class CommandParser:
    def __init__(self):
        # arities save (min, max) arguments for each command
        self._arities = {
            "set": (2, 2),
            "get": (1, 1),
            "llen": (1, 1),
            "rpush": (2, None),  # None means unlimited
            "lpop": (1, 1),
            "lrange": (3, 3),
            "keys": (0, 0),
            "del": (1, 1),
            "flushdb": (0, 0),
            "expire": (2, 2),
            "ttl": (1, 1),
            "smart_eviction": (1, 1),  # e.g., smart_eviction 100
        }
        
    def parse(self, command: str) -> Tuple:
        """
        Parse a command string
        Return a tupe of (command_name, args)
        """
        pattern = r'"([^"]*)"|\'([^\']*)\'|(\S+)'
        matches = re.findall(pattern, command)
        parts = [g1 or g2 or g3 for (g1, g2, g3) in matches]
        
        logger.debug(f"Parts after split: {parts}")
        if not parts:
            raise ValueError("Empty command")

        cmd = parts[0].lower()
        if cmd not in self._arities:
            raise ValueError(f"Unknown command: {cmd}")

        min_args, max_args = self._arities[cmd]
        args = parts[1:]

        if len(args) < min_args or (max_args is not None and len(args) > max_args):
            raise ValueError(f"Invalid number of arguments for {cmd}: expected {min_args}-{max_args}, got {len(args)}")

        return cmd, args