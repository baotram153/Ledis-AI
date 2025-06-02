# Ledis-AI

A lightweight, Redis-inspired in-memory data-store **enhanced with AI Features**.

Live Demo: http://ledis.southeastasia.cloudapp.azure.com:6379/

**Important Note**
- Because Ledis is implemented in a backend-frontend manner like the requirements has specified. Deploying the backend on the server means that **a single data store is created**. And because this is a simple application, you can think of this as a common database of a product (a single source of truth) that every developers have access to and every change they make is a global change that other developers can see.
- So you can see that some keys have existed when you access the database, and your changes to the database is permanent (the state will remain even if you reload the CLI page). If you want to refresh the data store, just run the command `FLUSHDB` and `SMART_EVICTION -1` (disable eviction) before any commands.

An example `workload.txt` file used to train the model is available [here](https://drive.google.com/drive/u/0/folders/1--yJ20Ys6xDgH_6Q-95Et_3kVNrHQpRh)

| Feature | Status |
|---------|--------|
| Core commands (`SET / GET / RPUSH / LLEN / LPOP / LRANGE / EXPIRE / TTL`) | ✔ |
| TTL and Lazy Expiration | ✔ |
| Classical eviction (LRU · LFU ) | ✔ |
| Hybrid regret-minimisation (adaptive weights) and Smart Eviction (PPO) | ✔ |
| Natural Language Querying and Execution | ✔ |
| Training/Evaluation and Data Generation Scripts for further research | ✔ |

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/baotram153/Ledis-AI.git
cd Ledis-AI
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # flask, stable-baselines3, gymnasium …

# 2. Run the server
python -m ledis.server               # defaults to 127.0.0.1:6379

# 3. Add your Gemini API key to the .env file
```
GEMINI_API_KEY=...
```

# 4. Try it
$ ledis-cli                           # tiny wrapper in /scripts
> SET foo bar
OK
> SMART_EVICTION 30
OK
```

## Repository layout
```
ledis-ai
└── ledis/
    ├── datastore.py           # in-memory KV store
    ├── parser.py              # simple command parser
    ├── executor.py            # maps commands to
    ├── chat.py            # translate nl cmd to Ledis cmd
    ├── eviction/
    │   ├── algos/           # lru.py, lfu.py, hybrid.py, rl.py
    │   ├── manager.py       # enable/disable, pick_victim, record_access
    │   └── features.py      # feature extraction helpers
    ├── env/                 # Gymnasium RL environment
    └── server.py            # Flask API + TCP CLI shim
├── docs/
├── tests/                   # for unit testing
├── static/                  # css file for fe formatting
├── templates/               # html file for fe content
├── ...
```

## Train the model
- Model checkpoint is saved in ledis/eviction/algos/rl_ckpt/model.zip and is automatically load if you run the app with RL Eviction Manager
- But if you want to train the model again, run the script `train.py`. For example
    ```
    python train.py --window 20 --n_keys 10 --n_timesteps 200000
    ```

## Evaluate the model
- Run the following script, remember to set the flags exactly like how you set for the train.py script
- You should re-generate the data with another seed to ensure the evaluation is objective
    ```
    python evaluate_rl.py
    ```
    
## Generate Data
You can generate the data yourself by running `data_synthesizer.py` script:
```
python .\ledis\eviction\utils\data_synthesizer.py
```
Remember to configure the hyperparameters before running. Corresponding workload will be generated in the `workload.txt` folder.

## Benchmark other Eviction Algorithms (LRU, LFU, Hybrid)
```
python benchmark.py --algo lru --window 10 
```

## Unit Testing
- Don't use the flag `-q` if you want verbosity
    ```
    pytest -q
    ```
