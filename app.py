import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# DATA_FILE se puede sobreescribir con una variable de entorno.
# Si montás un Volume en Railway, apuntá DATA_FILE a un path dentro
# de ese volume (ej. /data/data.json) para que los datos sobrevivan
# a los redeploys.
DATA_FILE = Path(os.environ.get("DATA_FILE", "data.json"))
DEFAULT_STATE = {"threshold": 30, "hotels": []}


def load_state():
    if not DATA_FILE.exists():
        save_state(DEFAULT_STATE)
        return dict(DEFAULT_STATE)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("formato inválido")
        data.setdefault("threshold", 30)
        data.setdefault("hotels", [])
        return data
    except (json.JSONDecodeError, ValueError):
        return dict(DEFAULT_STATE)


def save_state(state):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DATA_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp_path.replace(DATA_FILE)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state", methods=["GET"])
def get_state():
    return jsonify(load_state())


@app.route("/api/state", methods=["POST"])
def set_state():
    payload = request.get_json(force=True, silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON inválido"}), 400

    hotels = payload.get("hotels", [])
    if not isinstance(hotels, list):
        return jsonify({"error": "hotels debe ser una lista"}), 400

    threshold = payload.get("threshold", 30)
    try:
        threshold = int(threshold)
    except (TypeError, ValueError):
        threshold = 30

    save_state({"threshold": threshold, "hotels": hotels})
    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
