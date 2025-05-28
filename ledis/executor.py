from ledis.datastore import DataStore
from ledis.parser import CommandParser

class Executor:
    def __init__(self, db: DataStore, parser: CommandParser):
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
            "ttl": db.ttl
        }
        self._db = db
        self._parser = parser
        
    def execute(self, command_str: str):
        """
        Execute a command on the database
        """
        try:
            cmd, args = self._parser.parse(command_str)
            if cmd in self._dispatch:
                result = self._dispatch[cmd](*args)
                print(f"Result: {result}")
                return str(result)
            else:
                print(f"Unknown command: {cmd}")
                return f"ERROR: Unknown command: {cmd}"
        except Exception as e:
            return f"ERROR: {str(e)}"