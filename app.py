from flask import Flask, request, render_template, jsonify, Response
from ledis.datastore import DataStore
from ledis.parser import CommandParser
from ledis.executor import Executor

app = Flask(__name__)

data_store = DataStore()
parser = CommandParser()
executor = Executor(data_store, parser)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/", methods=["POST"])
def command():
    payload = request.get_json(silent=True) or {}
    cmd = payload.get("command", "").strip()
    print(f"Received command: {cmd}")
    if not cmd or not isinstance(cmd, str):
        return Response("ERROR: No command provided", status=400, mimetype='text/plain')
    result = executor.execute(cmd)
    print(f"Command result: {result}")
    return Response(result, mimetype='text/plain')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6379, debug=True, use_reloader=False)