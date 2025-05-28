import time

from ledis.executor import Executor
from ledis.parser import CommandParser
from ledis.datastore import DataStore

import pytest

#-------------FIXTURES----------------
@pytest.fixture
def executor():
    db = DataStore()
    parser = CommandParser()
    return Executor(db, parser)

#-------------LIST OPERATORS----------------
def test_rpush(executor):
    cmd = "RPUSH mylist item1"
    result = executor.execute(cmd)
    assert result == "(integer) 1"
    
    cmd = "RPUSH mylist item2"
    result = executor.execute(cmd)
    assert result == "(integer) 2"

def test_lpop_empty_list(executor):
    cmd = "LPOP mylist"
    result = executor.execute(cmd)
    assert result == "(nil)"
    
def test_lpop_existing_list(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    
    cmd = "LPOP mylist"
    result = executor.execute(cmd)
    assert result == "item1"
    
    cmd = "LPOP mylist"
    result = executor.execute(cmd)
    assert result == "item2"
    
    cmd = "LPOP mylist"
    result = executor.execute(cmd)
    assert result == "(nil)"
    
def test_llen_empty_list(executor):
    executor.execute("RPUSH mylist item1")  # clear the list
    executor.execute("LPOP mylist")  # clear the list
    
    cmd = "LLEN mylist"
    result = executor.execute(cmd)
    assert result == "(integer) 0"
    
def test_llen_existing_list(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    
    cmd = "LLEN mylist"
    result = executor.execute(cmd)
    assert result == "(integer) 2"
    
def test_lrange_empty_list(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("LPOP mylist")  # clear the list
    
    cmd = "LRANGE mylist 0 0"
    result = executor.execute(cmd)
    assert result == "ERROR: Start index 0 is out of bounds for list 'mylist' of length 0"
    
def test_lrange_existing_list(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    executor.execute("RPUSH mylist item3")
    
    cmd = "LRANGE mylist 0 2"
    result = executor.execute(cmd)
    assert result == "item1 item2 item3"
    
def test_lrange_with_same_start_stop(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    executor.execute("RPUSH mylist item3")
    
    cmd = "LRANGE mylist 1 1"
    result = executor.execute(cmd)
    assert result == "item2"
    
def test_stop_out_of_bound(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    executor.execute("RPUSH mylist item3")
    
    cmd = "LRANGE mylist 0 5"  # out of bound
    result = executor.execute(cmd)
    assert result == "item1 item2 item3"  # should return all items
    
def test_start_out_of_bound(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    
    cmd = "LRANGE mylist 5 6"  # out of bound
    result = executor.execute(cmd)
    assert result == "ERROR: Start index 5 is out of bounds for list 'mylist' of length 2"

def test_start_greater_than_stop(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    executor.execute("RPUSH mylist item3")
    
    cmd = "LRANGE mylist 2 1"  # start > stop
    result = executor.execute(cmd)
    assert result == "ERROR: Start index 2 cannot be greater than stop index 1"
    
def test_lrange_with_negative_indices(executor):
    executor.execute("RPUSH mylist item1")
    executor.execute("RPUSH mylist item2")
    executor.execute("RPUSH mylist item3")
    
    cmd = "LRANGE mylist -3 -1"  # should return all items
    result = executor.execute(cmd)
    assert result == "ERROR: Negative indices are not allowed"
    
def test_lpop_non_existing_key(executor):
    cmd = "LPOP non_existing_list"
    result = executor.execute(cmd)
    assert result == "(nil)"  # should return nil for non-existing key
    
def test_lrange_non_existing_key(executor):
    cmd = "LRANGE non_existing_list 0 1"
    result = executor.execute(cmd)
    assert result == "(empty)"  # should return empty for non-existing key
    
def test_llen_non_existing_key(executor):
    cmd = "LLEN non_existing_list"
    result = executor.execute(cmd)
    assert result == "(integer) 0"  # should return 0 for non-existing key
    
#-------------TYPE MISMATCH----------------
def test_type_mismatch_lrange(executor):
    executor.execute("SET key1 value1")
    cmd = "LRANGE key1 0 1"  # trying to treat a string as a list
    result = executor.execute(cmd)
    assert result == "ERROR: WRONGTYPE Operation against a key holding the wrong kind of value"
    
def test_type_mismatch_lpop(executor):
    executor.execute("SET key1 value1")
    cmd = "LPOP key1"  # trying to pop from a string
    result = executor.execute(cmd)
    assert result == "ERROR: WRONGTYPE Operation against a key holding the wrong kind of value"
    
def test_type_mismatch_rpush(executor):
    executor.execute("SET key1 value1")
    cmd = "RPUSH key1 item2"  # trying to push to a string
    result = executor.execute(cmd)
    assert result == "ERROR: WRONGTYPE Operation against a key holding the wrong kind of value"

def test_type_mismatch_llen(executor):
    executor.execute("SET key1 value1")
    cmd = "LLEN key1"  # trying to get length of a string
    result = executor.execute(cmd)
    assert result == "ERROR: WRONGTYPE Operation against a key holding the wrong kind of value"
    
def test_type_mismatch_set(executor):
    executor.execute("RPUSH mylist item1")
    cmd = "SET mylist value1"  # trying to set a value on a list
    result = executor.execute(cmd)
    assert result == "ERROR: WRONGTYPE Operation against a key holding the wrong kind of value"
    
def test_type_mismatch_get(executor):
    executor.execute("RPUSH mylist item1")
    cmd = "GET mylist"  # trying to get a value from a list
    result = executor.execute(cmd)
    assert result == "ERROR: WRONGTYPE Operation against a key holding the wrong kind of value"