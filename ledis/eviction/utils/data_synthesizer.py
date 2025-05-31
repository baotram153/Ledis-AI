import numpy as np
import random
import itertools as it
from collections import deque

# Eviction window is passed in as an input to the model

# ----------------- CONFIGURATIONS ----------------
NUM_PHASES = 10                  # number of working phases in the workload
WORKING_SET_SIZE = 100           # hot keys per phase
N_COMMANDS_PER_PHASE = 200       # number of commands per phase

INSERT_WS_PROB = 0.6            # prob of inserting a key in hot keys of that phase
INSERT_NOISE = 0.02             # prob of inserting a key that is outside hot keys 
REINESRT_PROB = 0.8             # prob of re-inserting a key that is recently evicted

READ_WS_PROB = 0.9            # prob of reading a key that is in the working set
READ_SET_PROB = 0.8            # prob of reading a key that have been set recently

EXPIRE_SET_PROB = 0.2           # prob of setting an expiry on a key -> not use
EXPIRE_TIME_MIN = 2
EXPIRE_TIME_MAX = 15            # expiry time range in seconds

CAPACITY = 20                   # capacity of the live set (number of keys that can be stored)

# seed anything!
rng = np.random.default_rng(42)
rnd = random.Random(42)

recently_evicted = set()  # set of recently evicted keys, used to reinsert them
recently_set = deque(maxlen=CAPACITY)  # deque to hold recently set keys, used for locality in reads

def evict_one(live):
    """
    Evicts one key from the live set. Used by the generator only
    Simple LRU callback
    Simulate to decide reinserting a recently evicted key
    """
    victim = live[0]
    live.remove(victim)
    return victim

# input need only (set/get, key)
def workload():
    live = []   # list of keys, in least recently used order
    phase_keys =[]  # hold the 4 disjoint working sets
    
    # ----------------- CREATE DISJOINT WORKING SETS -----------------
    # k + index
    universe_ids = ["k" + str(i) for i in range(NUM_PHASES * WORKING_SET_SIZE)]
    
    for i in range(NUM_PHASES):
        phase_keys.append(list(universe_ids[i * WORKING_SET_SIZE: (i + 1) * WORKING_SET_SIZE]))
        
    for phase in range(NUM_PHASES):
        # ----------------- FETCH HOT KEYS AND NOISE KEYS -----------------
        hot_keys = set(phase_keys[phase])
        noise_keys = list(set(universe_ids) - hot_keys)
        hot_keys = list(hot_keys)  # convert to list for random choice
        
        for _ in range(N_COMMANDS_PER_PHASE):
            write_prob = rng.random()
            # insert hot keys
            if write_prob < INSERT_WS_PROB:
                # print(write_prob)
                key = rng.choice(hot_keys)
                _ensure_materialized(key, live)
                yield from _write(key, live)
                
            # insert noise keys
            if write_prob < INSERT_NOISE:
                key = rng.choice(noise_keys)
                _ensure_materialized(key, live)
                yield from _write(key, live)
                
            # reinsert recently evicted keys
            if write_prob < REINESRT_PROB and recently_evicted: # recently evited is not empty
                key = rng.choice(list(recently_evicted))
                _ensure_materialized(key, live)
                yield from _write(key, live)
                
            expire_prob = rng.random()
            # if expire_prob < EXPIRE_SET_PROB and live:
            #     # set an expiry on a key
            #     key = rng.choice(live)
            #     yield f"EXPIRE {key} {rnd.randint(EXPIRE_TIME_MIN, EXPIRE_TIME_MAX)}"
                
            # read a key (mimics LeCAR locality - 90% in WS, 10% noise)
            read_prob = rng.random()
            if read_prob < READ_WS_PROB:
                recently_set_keys = list(recently_set)
                other_keys = list(set(hot_keys) - set(recently_set_keys))
                if read_prob < READ_SET_PROB and recently_set_keys:
                    key = rng.choice(recently_set_keys)
                elif other_keys: key = rng.choice(other_keys)
                else: key = rng.choice(hot_keys)
            _ensure_materialized(key, live)
            yield from _read(key)
        # yield "END_PHASE"  # signal the end of the phase
            
            

def _ensure_materialized(key, live):
    """
    Update LRU if key already exists
    If key does not exist, evict until there is room for the key
    """
    # full_key = f"k{key}"
    full_key = key  # in this model, key is already prefixed with 'k'
    if full_key in live:
        _touch(full_key, live)
        return
    
    # evict until there is a room
    while len(live) >= CAPACITY:
        victim = evict_one(live)
        
        # insert evicted key to recently evicted set
        recently_evicted.add(victim)
    
def _write(key, live):
    """
    Write a key to the live set
    Emit 
    """
    # full_key = f"k{key}"
    full_key = key
    value = f"v{key[1:]}"
    
    # insert the key to the live set
    live.append(full_key)
    _touch(full_key, live)
    
    # insert key to the recently set deque
    recently_set.append(full_key)
    
    yield f"SET {full_key} {value}"  # value is not important for this model
    
def _read(key):
    """
    Read a key from the live set
    Emit the read command
    """
    # full_key = f"k{key}"
    full_key = key
    yield f"GET {full_key}"
        
def _touch(key, live):
    if key in live:
        live.remove(key)
    live.append(key)  # append it to the end (most recently used position)
    
if __name__ == "__main__":
    # write a sample workload to a file
    with open("workload.txt", "w") as f:
        for command in workload():
            f.write(command + "\n")