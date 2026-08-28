import json
import os
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request

app = Flask(__name__)

# DATA_FILE se puede sobreescribir con una variable de entorno.
# Si montás un Volume en Railway, apuntá DATA_FILE a un path dentro
# de ese volume (ej. /data/data.json) para que los datos sobrevivan
# a los redeploys.
DATA_FILE = Path(os.environ.get("DATA_FILE", "data.json"))

# --- Secciones disponibles ---
# Para sumar una nueva sección más adelante: agregá una entrada acá
# (id interno + nombre visible), y si necesita otro tipo de checklist,
# se arma su propia plantilla. "duenos" reutiliza el checklist original.
SECTIONS = {
    "duenos": {"label": "Vínculo con dueños"},
}

DEFAULT_SECTION_STATE = {"threshold": 30, "hotels": []}


# --- Usuarios y permisos ---
# Se definen en la variable de entorno USERS_CONFIG, en formato JSON:
#   {"esteban": {"password": "clave1", "sections": ["duenos"]},
#    "flor":    {"password": "clave2", "sections": ["duenos"]}}
# Cada usuario solo ve las secciones listadas en "sections".
def load_users():
    raw = os.environ.get("USERS_CONFIG")
    if not raw:
        # Fallback de desarrollo (sin configurar nada en Railway todavía):
        # un usuario demo con acceso a todas las secciones.
        return {"demo": {"password": "demo", "sections": list(SECTIONS.keys())}}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


USERS = load_users()


def check_auth(username, password):
    user = USERS.get(username)
    return bool(user) and user.get("password") == password


def user_sections(username):
    return USERS.get(username, {}).get("sections", [])


def authenticate():
    return Response(
        "Acceso restringido.",
        401,
        {"WWW-Authenticate": 'Basic realm="Seguimiento BENS"'},
    )


def current_user():
    """Username si las credenciales de la request son válidas, si no None."""
    auth = request.authorization
    if auth and check_auth(auth.username, auth.password):
        return auth.username
    return None


# --- Persistencia (todas las secciones viven en un solo data.json) ---
def load_all_state():
    if not DATA_FILE.exists():
        empty = {"sections": {}}
        save_all_state(empty)
        return empty
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("formato inválido")
    except (json.JSONDecodeError, ValueError):
        return {"sections": {}}

    # Migración automática: si el archivo viene del formato viejo
    # (threshold/hotels sueltos, sin "sections"), se envuelve como
    # la sección "duenos" para no perder los datos ya cargados.
    if "sections" not in data and ("hotels" in data or "threshold" in data):
        data = {"sections": {"duenos": {
            "threshold": data.get("threshold", 30),
            "hotels": data.get("hotels", []),
        }}}
        save_all_state(data)

    data.setdefault("sections", {})
    return data


def save_all_state(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DATA_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(DATA_FILE)


def get_section_state(section_id):
    data = load_all_state()
    return data["sections"].get(section_id, dict(DEFAULT_SECTION_STATE))


def set_section_state(section_id, state):
    data = load_all_state()
    data["sections"][section_id] = state
    save_all_state(data)


# --- Rutas ---
@app.route("/")
def dashboard():
    username = current_user()
    if not username:
        return authenticate()
    allowed = [sid for sid in user_sections(username) if sid in SECTIONS]
    sections = [{"id": sid, "label": SECTIONS[sid]["label"]} for sid in allowed]
    return render_template("dashboard.html", sections=sections, username=username)


@app.route("/s/<section_id>")
def section_page(section_id):
    username = current_user()
    if not username:
        return authenticate()
    if section_id not in SECTIONS or section_id not in user_sections(username):
        abort(404)
    return render_template(
        "index.html",
        section_id=section_id,
        section_label=SECTIONS[section_id]["label"],
    )


@app.route("/api/state/<section_id>", methods=["GET"])
def api_get_state(section_id):
    username = current_user()
    if not username:
        return authenticate()
    if section_id not in SECTIONS or section_id not in user_sections(username):
        abort(403)
    return jsonify(get_section_state(section_id))


@app.route("/api/state/<section_id>", methods=["POST"])
def api_set_state(section_id):
    username = current_user()
    if not username:
        return authenticate()
    if section_id not in SECTIONS or section_id not in user_sections(username):
        abort(403)

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

    set_section_state(section_id, {"threshold": threshold, "hotels": hotels})
    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
