from ledis.datastore import DataStore
from ledis.parser import CommandParser
from ledis.eviction.manager import EvictionManager
import logging

logger = logging.getLogger(__name__)

class Executor:
    def __init__(self, db: DataStore, parser: CommandParser, eviction_manager: EvictionManager = None):
        self._dispatch = {
            "set": db.set,
            "get": db.get,
            "llen": db.get_len,
            "rpush": db.right_push,
            "lpop": db.left_pop,
            "lrange": db.get_range,
            "keys": db.list_keys,
            "del": db.delete_key,
            "flushdb": db.flushdb,
            "expire": db.set_expire,
            "ttl": db.ttl,
            "smart_eviction": eviction_manager.set_eviction_window,
        }
        self._db = db
        self._parser = parser
        
        self._eviction_manager = eviction_manager
        self._eviction_enabled = False
        
    def execute(self, command_str: str):
        """
        Execute a command on the database
        """
        logger.debug(f"Command string: {command_str}")
        try:
            cmd, args = self._parser.parse(command_str)
            logger.debug(f"Parsed command: {cmd} with args: {args}")
            if cmd in self._dispatch:
                
                # dispatch the command to get corresponding response
                result = self._dispatch[cmd](*args)
                
                if isinstance(result, (int, bool)):
                    result = f"(integer) {int(result)}"
                
                # handle eviction if enabled
                if cmd == "smart_eviction": self._eviction_enabled = True
                if self._eviction_enabled and cmd not in ["smart_eviction", "keys", "flushdb"]:
                    set_key = args[0]
                    is_set = 1 if cmd in ["set", "rpush"] else 0
                    evicted_key = self._eviction_manager.evict(set_key, is_set)
                    if evicted_key:
                        limit = self._eviction_manager.get_eviction_window()
                        logger.info(f"Evicted key: {evicted_key}")
                        result += f"\nSmart eviction: Number of keys reached limit {limit}. Key `{evicted_key}` has been evicted."
                        
                logger.debug(f"Executed command: {cmd} with args: {args}, result: {result}")
                
                return result
            else:
                logger.debug(f"Unknown command: {cmd}")
                return f"ERROR: Unknown command: {cmd}"
        except Exception as e:
            return f"ERROR: {str(e)}"