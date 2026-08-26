import json
import os
from functools import wraps
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)

# DATA_FILE se puede sobreescribir con una variable de entorno.
# Si montás un Volume en Railway, apuntá DATA_FILE a un path dentro
# de ese volume (ej. /data/data.json) para que los datos sobrevivan
# a los redeploys.
DATA_FILE = Path(os.environ.get("DATA_FILE", "data.json"))
DEFAULT_STATE = {"threshold": 30, "hotels": []}

# Usuario/contraseña para proteger la app. Se configuran como variables
# de entorno en Railway (APP_USER, APP_PASSWORD). Si APP_PASSWORD no está
# seteada, no se pide nada (útil para correrlo local sin configurar nada).
APP_USER = os.environ.get("APP_USER", "bens")
APP_PASSWORD = os.environ.get("APP_PASSWORD")


def check_auth(username, password):
    if not APP_PASSWORD:
        return True
    return username == APP_USER and password == APP_PASSWORD


def authenticate():
    return Response(
        "Acceso restringido.",
        401,
        {"WWW-Authenticate": 'Basic realm="Seguimiento BENS"'},
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


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
@requires_auth
def index():
    return render_template("index.html")


@app.route("/api/state", methods=["GET"])
@requires_auth
def get_state():
    return jsonify(load_state())


@app.route("/api/state", methods=["POST"])
@requires_auth
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
