"""
Seccion "Briefing" para bens-seguimiento.

Se registra en app.py con dos lineas (ver LEEME.md). Guarda todo en su propio
archivo (briefing.json) dentro del mismo Volume que ya usas, asi que no toca
los datos de los hoteles.

Permisos por variables de entorno en Railway:
  BRIEFING_EDITORS = usuarios que cargan y tildan (ej: flor)
  BRIEFING_VIEWERS = usuarios que solo miran (ej: esteban)
Los nombres tienen que coincidir con los usuarios de USERS_CONFIG.
Si no hay ninguna variable, nadie entra (falla cerrado a proposito).
"""
import copy
import json
import os
import tempfile
import threading
import uuid
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, jsonify, render_template, request, session

bp = Blueprint("briefing", __name__)

_base = os.path.dirname(os.environ.get("DATA_FILE", "")) or "."
BRIEFING_FILE = os.environ.get("BRIEFING_FILE", os.path.join(_base, "briefing.json"))
_lock = threading.Lock()

DIA = {"lunes": 0, "viernes": 4}
TITULO = {"lunes": "Lunes: plan de la semana", "viernes": "Viernes: cierre y repaso"}


# ---------------------------------------------------------------- permisos
def _usuario():
    # AJUSTAR si tu login guarda el usuario con otra clave de sesion.
    u = session.get("user") or session.get("usuario") or session.get("username")
    return str(u).strip().lower() if u else None


def _lista(nombre):
    return {x.strip().lower() for x in os.environ.get(nombre, "").split(",") if x.strip()}


def _rol():
    u = _usuario()
    if not u:
        return None
    if u in _lista("BRIEFING_EDITORS"):
        return "editor"
    if u in _lista("BRIEFING_VIEWERS"):
        return "viewer"
    return None


def _requiere(editar=False):
    rol = _rol()
    if rol is None or (editar and rol != "editor"):
        abort(403 if _usuario() else 401)


# ---------------------------------------------------------------- plantilla
def _b(id_, titulo, grupo, hint="", items=()):
    return {"id": id_, "titulo": titulo, "grupo": grupo, "hint": hint, "items": [_item(t, plantilla=True) for t in items]}


def _item(texto, plantilla=False):
    return {"id": uuid.uuid4().hex[:10], "texto": texto, "hecho": False, "deadline": "", "nota": "", "prioridad": False, "plantilla": plantilla}


def plantilla(tipo):
    if tipo == "lunes":
        return [
            _b("entrada", "Preguntas de entrada", "Arranque", items=["¿Hay algo que se resuelve sí o sí hoy? (Florencia)"]),
            _b("t-mateo", "Temas Mateo", "Temas"),
            _b("t-agustin", "Temas Agustín", "Temas"),
            _b("t-eb", "Temas EB", "Temas"),
            _b("agenda", "Agenda (próximas 2 semanas)", "Agenda", items=["Confirmación CCAN", "Confirmación BOA"]),
            _b("correo", "Pendientes de correo", "Pendientes",
               "Correos o WhatsApp con poca info: aclarar y SIEMPRE pedir deadline."),
            _b("sin-resolver", "Sin resolver", "Pendientes generales",
               "Cosas que siguen sin resolver por falta de info o aprobación de EB."),
            _b("cerrados", "Cerrados tras mucho tiempo", "Pendientes generales",
               "CVs, automatizaciones, cowork, uniformes, etc."),
            _b("1on1", "1on1", "Pendientes generales"),
            _b("viajes-corto", "Corto plazo", "Viajes"),
            _b("viajes-medio", "Mediano plazo", "Viajes", "Próximos 6 viajes."),
            _b("viajes-personales", "Personales", "Viajes", "Fines de semana o vacaciones."),
            _b("entrenamiento-actual", "Curso actual", "Entrenamiento de Flor", "Dar FU a EB."),
            _b("entrenamiento-futuro", "Curso futuro", "Entrenamiento de Flor"),
            _b("entrenamiento-proximos", "Próximos a realizar", "Entrenamiento de Flor"),
            _b("cierre", "Cierre del briefing", "Cierre",
               items=["Repasar los action items para corroborar que todo se entendió"]),
        ]
    return [
        _b("repaso", "Repaso de proyectos", "Cierre de semana",
           "¿Se terminó o no? Si no se terminó y es importante y urgente, pasa como primera prioridad del siguiente día hábil."),
        _b("nuevos", "Temas nuevos donde falta información", "Cierre de semana"),
        _b("semana-entrante", "Semana entrante: repaso", "Cierre de semana"),
    ]


def proxima_fecha(tipo, desde=None):
    hoy = desde or date.today()
    dias = (DIA[tipo] - hoy.weekday()) % 7
    return (hoy + timedelta(days=dias)).isoformat()


def nuevo_briefing(tipo, anterior=None, desde=None, estricto=False):
    hoy = desde or date.today()
    if estricto:
        hoy = hoy + timedelta(days=1)
    bloques = plantilla(tipo)
    if anterior:
        previos = {b["id"]: b for b in anterior["bloques"]}
        for b in bloques:
            viejo = previos.get(b["id"])
            if not viejo:
                continue
            arrastre = [i for i in viejo["items"] if not i["hecho"] and not i["plantilla"]]
            prio = [i for i in arrastre if i["prioridad"]]
            resto = [i for i in arrastre if not i["prioridad"]]
            b["items"] = prio + b["items"] + resto
    return {"fecha": proxima_fecha(tipo, hoy), "bloques": bloques}


# ---------------------------------------------------------------- almacenamiento
def _leer():
    try:
        with open(BRIEFING_FILE, encoding="utf-8") as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = {}
    for tipo in ("lunes", "viernes"):
        if tipo not in st:
            st[tipo] = nuevo_briefing(tipo)
    st.setdefault("historial", [])
    return st


def _guardar(st):
    carpeta = os.path.dirname(BRIEFING_FILE) or "."
    os.makedirs(carpeta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, BRIEFING_FILE)


def _buscar_item(st, item_id):
    for tipo in ("lunes", "viernes"):
        for b in st[tipo]["bloques"]:
            for i, it in enumerate(b["items"]):
                if it["id"] == item_id:
                    return b, i, it
    return None, None, None


# ---------------------------------------------------------------- rutas
@bp.route("/briefing")
def pagina():
    _requiere()
    return render_template("briefing.html")


@bp.route("/briefing/api/estado")
def estado():
    _requiere()
    with _lock:
        st = _leer()
    return jsonify({
        "puede_editar": _rol() == "editor",
        "titulos": TITULO,
        "lunes": st["lunes"],
        "viernes": st["viernes"],
        "historial": st["historial"][:30],
    })


@bp.route("/briefing/api/item", methods=["POST"])
def agregar():
    _requiere(editar=True)
    d = request.get_json(force=True)
    texto = (d.get("texto") or "").strip()
    if d.get("tipo") not in DIA or not texto:
        abort(400)
    with _lock:
        st = _leer()
        for b in st[d["tipo"]]["bloques"]:
            if b["id"] == d.get("bloque"):
                it = _item(texto[:500])
                b["items"].append(it)
                _guardar(st)
                return jsonify(it)
    abort(404)


@bp.route("/briefing/api/item/<item_id>", methods=["PATCH"])
def editar(item_id):
    _requiere(editar=True)
    d = request.get_json(force=True)
    with _lock:
        st = _leer()
        _, _, it = _buscar_item(st, item_id)
        if not it:
            abort(404)
        if "hecho" in d:
            it["hecho"] = bool(d["hecho"])
        if "prioridad" in d:
            it["prioridad"] = bool(d["prioridad"])
        if "texto" in d and str(d["texto"]).strip():
            it["texto"] = str(d["texto"]).strip()[:500]
        if "deadline" in d:
            it["deadline"] = str(d["deadline"])[:10]
        if "nota" in d:
            it["nota"] = str(d["nota"])[:2000]
        _guardar(st)
        return jsonify(it)


@bp.route("/briefing/api/item/<item_id>", methods=["DELETE"])
def borrar(item_id):
    _requiere(editar=True)
    with _lock:
        st = _leer()
        b, i, _ = _buscar_item(st, item_id)
        if b is None:
            abort(404)
        b["items"].pop(i)
        _guardar(st)
    return jsonify(ok=True)


@bp.route("/briefing/api/cerrar", methods=["POST"])
def cerrar():
    _requiere(editar=True)
    tipo = (request.get_json(force=True) or {}).get("tipo")
    if tipo not in DIA:
        abort(400)
    with _lock:
        st = _leer()
        actual = st[tipo]
        st["historial"].insert(0, {
            "tipo": tipo,
            "fecha": actual["fecha"],
            "cerrado": datetime.now().isoformat(timespec="minutes"),
            "bloques": copy.deepcopy(actual["bloques"]),
        })
        st["historial"] = st["historial"][:200]
        st[tipo] = nuevo_briefing(tipo, anterior=actual, estricto=True)
        _guardar(st)
    return jsonify(ok=True)
