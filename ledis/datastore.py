from typing import Dict, Any, Optional, Tuple, List, Union
from threading import Lock
import time
import logging

from ledis.exceptions import WrongTypeError, KeyNotFoundError

logger = logging.getLogger(__name__)

class DataStore:
    """
    A dictionary of key-(value, expiration) pairs
    """
    def __init__(self):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()
        
    """
    -----------------------HELPERS-------------------------
    """
    def _now(self) -> float:
        return time.time()
    
    def _exists(self, key: str) -> bool:
        """
        Check if the key exists in the store
        """
        return key in self._store
    
    def _alive(self, key: str) -> bool:
        """
        Check if the key exists and is not expired
        """
        logger.debug(f"Checking if key '{key}' is alive")
        if not self._exists(key): return False
        _, expire = self._store.get(key, (None, float('inf')))
        if self._now() > expire :
            self._store.pop(key, None)  # Lazy expiration
            return False
        return True
        
    def _requires_type(self, key: str, expected_type: type) -> bool:
        """
        Check if the value at key is of the expected type
        """
        value, _ = self._store.get(key)
        return isinstance(value, expected_type)
            
    def _purge_expired(self):
        """
        Purge expired keys from the store
        This is a lazy cleanup, called before any operation that requires checking key existence
        """
        list(map(lambda k : self._alive(k), list(self._store.keys())))
        
    """
    -----------------------STRING OPERATORS-------------------------
    """
        
    def set(self, key: str, value: Any) -> str:
        """
        - Set a key-value pair
        - Update value of existing key
        """
        with self._lock:
            if self._alive(key):
                # check if current value is a list
                if not isinstance(self._store[key][0], str):
                    raise WrongTypeError()
            self._store[key] = (value, float('inf'))
            return f"OK"
        
    def get(self, key: str) -> str:
        """
        - Get value by key
        - Return None if key does not exist
        """
        # check if key is alive 
        with self._lock:
            logger.debug(f"Getting value for key '{key}'")
            # check if key exists and is a string
            if not self._alive(key):
                return '(nil)'
            if not self._requires_type(key, str):
                raise WrongTypeError()
            value, _ = self._store[key]
            return value
            
    
    """
    ---------------------LIST OPERATIONS--------------------------
    Ordered collection of strings
    """
    def get_len(self, key: str) -> int:
        """
        - Get length of list at key
        - Return 0 if key does not exist or is not a list
        """
        with self._lock:
            if not self._alive(key):
                return 0
            if not self._requires_type(key, list):
                raise WrongTypeError()
            
            # return length of list if it exists
            value, _ = self._store[key]
            return len(value) if self._requires_type(key, list) else 0
        
    def right_push(self, key:str, *value) -> int:
        """
        - Append value to the right end of the list at key
        - Create a new list if key does not exist
        """
        with self._lock:
            if not self._alive(key):
                self._store[key] = ([], float('inf'))
            elif not self._requires_type(key, list):
                raise WrongTypeError()
            
            self._store[key][0].extend(str(v) for v in value)
            return len(self._store[key][0])
        
    def left_pop(self, key: str) -> str:
        """
        - Remove and return the leftmost element (stringified) of the list at key
        - Return '(nil)' if key does not exist or is not a list
        """
        with self._lock:
            if not self._alive(key):
                return '(nil)'
            if not self._requires_type(key, list):
                raise WrongTypeError()
            
            value = self._store[key][0]
            if value != []:   # not an empty list
                item = value.pop(0)
                return item
            return '(nil)'
        
    def get_range(self, key: str, start: str, stop: str) -> str:
        """
        - Get a range of elements from the list at key
        - Return empty list if key does not exist or is not a list
        """
        with self._lock:
            # check if key exists and is a list
            if not self._alive(key):
                return '(empty)'
            elif not self._requires_type(key, list):
                raise WrongTypeError()
            
            start, stop = int(start), int(stop)
            
            # check if positive indices
            if start < 0 or stop < 0:
                raise IndexError(f"Negative indices are not allowed")
            if not self._alive(key):
                return '(empty)'
            if not self._requires_type(key, list):
                raise WrongTypeError()
            
            value = self._store[key][0]
            
            # check if start and stop are within bounds
            if start > len(value) - 1:
                raise IndexError(f"Start index {start} is out of bounds for list '{key}' of length {len(value)}")
            if stop > len(value) - 1:
                stop = len(value) - 1  # adjust stop to the last index -> return whole list
            if start > stop:
                raise IndexError(f"Start index {start} cannot be greater than stop index {stop}")
            
            return " ".join(value[start:stop+1] if value else [])
        
    """
    KEY MANAGEMENT
    """
    def list_keys(self) -> str:
        """
        - List all keys in the store
        - Return 
        """
        with self._lock:
            self._purge_expired()
            if len(self._store) == 0:
                return '(empty)'
            else:
                return " ".join(self._store.keys())
    
    def delete_key(self, key: str) -> bool:
        """
        - Delete a key from the store
        - Return True if key was deleted, False if it did not exist
        """
        with self._lock:
            logger.debug(f"Deleting key '{key}'")
            if self._alive(key):
                removed = self._store.pop(key, None)
                return removed is not None
            return False
        
    def flushdb(self):
        """
        - Clear the entire store
        """
        with self._lock:
            self._store.clear()
            return "OK"
            
    def set_expire(self, key: str, seconds: str) -> bool:
        """
        - Set an expiration time for a key if timeout is not set -> return True
        - If key exists and the expiration is set -> return number of seconds until expiration
        - Throw error if the key is not set
        """
        with self._lock:
            if self._alive(key):
                value, expire = self._store[key]
                if (expire == float('inf')):
                    expire_time = self._now() + int(seconds)
                    self._store[key] = (value, expire_time)
                    return True
                return int(expire - self._now())
            raise KeyNotFoundError(key)
        
    def ttl(self, key: str) -> int:
        """
        - Get the time to live for a key
        """
        with self._lock:
            if self._alive(key):
                _, expire = self._store[key]
                # return -1 if no expiration is set
                return int(expire - self._now()) if expire != float('inf') else -1
            return -2  # convention: -2 when key expired or does not exist