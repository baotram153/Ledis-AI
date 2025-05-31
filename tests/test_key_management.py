import time

from ledis.executor import Executor
from ledis.parser import CommandParser
from ledis.datastore import DataStore
from ledis.eviction.manager import EvictionManager

import pytest

#-------------FIXTURES----------------
@pytest.fixture
def executor():
    db = DataStore()
    parser = CommandParser()
    eviction_manager = EvictionManager(db)
    return Executor(db, parser, eviction_manager)

# #-------------KEY MANAGEMENT----------------
# keys
def test_keys_empty(executor):
    cmd = "KEYS"
    assert executor.execute(cmd) == "(empty)"  # should return empty if no keys exist

def test_keys_with_existing_keys(executor):
    executor.execute("SET key1 value1")
    executor.execute("SET key2 value2")
    
    cmd = "KEYS"
    result = executor.execute(cmd)
    assert result == "key1 key2"
    
def test_keys_of_list(executor):
    executor.execute("RPUSH mylist1 item1")
    executor.execute("RPUSH mylist1 item2")
    executor.execute("RPUSH mylist2 item3")
    
    cmd = "KEYS"
    assert executor.execute(cmd) == "mylist1 mylist2"  # should return all keys including lists
    
# del
def test_deletion_of_key(executor):
    executor.execute("SET key1 value1")
    cmd = "DEL key1"
    assert executor.execute(cmd) == "(integer) 1"  # should return number of keys deleted
    
    cmd = "GET key1"
    assert executor.execute(cmd) == "(nil)"  # key should no longer exist
    
    cmd = "KEYS"
    assert executor.execute(cmd) == "(empty)"  # no keys left
    
# flushdb
def test_flushdb(executor):
    executor.execute("SET key1 value1")
    executor.execute("SET key2 value2")
    
    cmd = "FLUSHDB"
    assert executor.execute(cmd) == "OK"  # should return OK
    
    cmd = "KEYS"
    assert executor.execute(cmd) == "(empty)"  # all keys should be deleted
    
def test_flushdb_empty(executor):
    cmd = "FLUSHDB"
    assert executor.execute(cmd) == "OK"  # should return OK even if no keys exist
    
    cmd = "KEYS"
    assert executor.execute(cmd) == "(empty)"  # still no keys after flush
    
# expire & ttl
def test_set_expire_and_ttl(executor):
    executor.execute("SET key value")
    cmd = "EXPIRE key 10"
    assert executor.execute(cmd) == "(integer) 1"          # returns seconds set

    ttl = int(executor.execute("TTL key").replace("(integer) ", ""))
    assert 0 <= ttl <= 10


def test_expire_overwrites_old_expiry(executor):
    executor.execute("SET key value")
    executor.execute("EXPIRE key 5")
    
    cmd = "EXPIRE key 10"
    ttl = int(executor.execute(cmd).replace("(integer) ", ""))
    assert 0 < ttl <= 5     # not accept expiration overwriting


def test_key_actually_expires(executor, monkeypatch):
    executor.execute("SET key value")
    executor.execute("EXPIRE key 1")

    assert executor.execute("GET key") == "value"                 # before expiry

    # fast-forward clock by 2 seconds
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 2)

    # TTL now -2 (key vanished); GET returns nil
    assert executor.execute("TTL k") == "(integer) -2"
    assert executor.execute("GET k") == "(nil)"
    
def test_del_non_existing_key(executor):
    cmd = "DEL no_key"
    assert executor.execute(cmd) == "(integer) 0"  # should return 0 if key does not exist

def test_ttl_nonexistent_key(executor):
    assert executor.execute("TTL no_key") == "(integer) -2"


def test_expire_nonexistent_key(executor):
    assert executor.execute("EXPIRE no_key 10") == "ERROR: Key 'no_key' does not exist"