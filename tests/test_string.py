import ledis.datastore
import pytest
import time

from ledis.executor import Executor
from ledis.parser import CommandParser
from ledis.datastore import DataStore

#-------------FIXTURES----------------
@pytest.fixture
def executor():
    db = DataStore()
    parser = CommandParser()
    return Executor(db, parser)


#-------------STRING OPERATORS----------------
def test_set(executor):
    cmd = "set key1 value1"
    result = executor.execute(cmd)
    assert result == "OK"
    
def test_get_no_existence(executor):
    cmd = "get key1"
    result = executor.execute(cmd)
    assert result == "(nil)"
    
def test_get_existing_key(executor):
    assert executor.execute("set key1 value1") == "OK"
    assert executor.execute("get key1") == "value1"
    
def test_overwrite_value(executor):
    executor.execute("SET k v1")
    executor.execute("SET k v2")
    assert executor.execute("GET k") == "v2"
    
def test_get_list(executor):
    assert executor.execute("RPUSH mylist item1") == "(integer) 1"
    assert executor.execute("RPUSH mylist item2") == "(integer) 2"
    assert executor.execute("GET mylist") == "ERROR: WRONGTYPE Operation against a key holding the wrong kind of value"