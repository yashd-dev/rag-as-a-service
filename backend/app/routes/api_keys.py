from flask import Blueprint, current_app, jsonify, request

from backend.app.routes.projects import auth_or_error
from backend.app.services.api_keys import ApiError, ApiKeys
from backend.app.services.corpus_access import CorpusAccessError

api_keys_bp = Blueprint("api_keys", __name__)


@api_keys_bp.get("")
def list_keys():
    auth, error = auth_or_error()
    if error:
        return error
    return jsonify({"items": ApiKeys(current_app.config).list(auth)})


@api_keys_bp.post("")
def create_key():
    auth, error = auth_or_error()
    if error:
        return error
    try:
        return jsonify(ApiKeys(current_app.config).create(auth, request.get_json(silent=True))), 201
    except (ApiError, CorpusAccessError) as exc:
        return jsonify({"error": exc.code.replace("_", " "), "code": exc.code}), exc.status


@api_keys_bp.delete("/<key_id>")
def revoke_key(key_id):
    auth, error = auth_or_error()
    if error:
        return error
    if not ApiKeys(current_app.config).revoke(auth, key_id):
        return jsonify({"error": "API key not found"}), 404
    return "", 204
