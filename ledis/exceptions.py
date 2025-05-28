class LedisException(Exception):
    """Base class for all Ledis exceptions."""
    pass

class WrongTypeError(LedisException):
    """Raised when the operation is applied to a key of the wrong type."""
    def __init__(self, message="WRONGTYPE Operation against a key holding the wrong kind of value"):
        super().__init__(message)
        
class KeyNotFoundError(LedisException):
    """For EXPIRE, RENAME"""
    def __init__(self, key: str):
        super().__init__(f"Key '{key}' does not exist")
        
class ParserError(LedisException):
    """Raised when there is an error in command parsing."""
    pass