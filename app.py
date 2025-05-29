from flask import Flask, request, render_template, jsonify, Response

import logging
from logging.config import dictConfig

from ledis.datastore import DataStore
from ledis.parser import CommandParser
from ledis.eviction.manager import EvictionManager

from ledis.executor import Executor

app = Flask(__name__)

# configure logging
dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'default': {
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['default']
    }
})
logger = logging.getLogger(__name__)

data_store = DataStore()
parser = CommandParser()
eviction_manager = EvictionManager(data_store, algo_name="lru")
executor = Executor(data_store, parser, eviction_manager)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/", methods=["POST"])
def command():
    payload = request.get_json(silent=True) or {}
    cmd = payload.get("command", "").strip()
    logger.info(f"Received command: {cmd}")
    if not cmd or not isinstance(cmd, str):
        return Response("ERROR: No command provided", status=400, mimetype='text/plain')
    result = executor.execute(cmd)
    app.logger.info(f"Command result: {result}")
    return Response(result, mimetype='text/plain')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6379, debug=True, use_reloader=False)