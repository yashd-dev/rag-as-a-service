"""OpenAI-compatible single-turn RAG. SSE emits only validated answer text."""

import json
import time
from urllib.parse import quote

from flask import Blueprint, Response, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from backend.app.services.api_keys import ApiError, ApiKeys
from backend.app.services.corpus_access import CorpusAccess, CorpusAccessError
from backend.app.services.generation import SelectionError, list_configs, resolve
from backend.app.services.passages import resolve_passage
from backend.app.services.query_service import QueryFailure, QueryService
from backend.app.services.retrieval import MODES, RetrievalUnavailable

public_api_bp = Blueprint("public_api", __name__)


@public_api_bp.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    if response.status_code == 429:
        response.headers["Retry-After"] = "60"
    return response


@public_api_bp.errorhandler(Exception)
def api_error(exc):
    if isinstance(exc, (ApiError, CorpusAccessError, SelectionError, QueryFailure, RetrievalUnavailable)):
        code, status = exc.code, exc.status
    elif isinstance(exc, HTTPException):
        code, status = "invalid_request", exc.code
    else:
        code, status = "service_unavailable", 503
    return jsonify({"error": {"message": code.replace("_", " "), "type": "invalid_request_error" if status < 500 else "server_error", "param": None, "code": code}}), status


def authenticate():
    keys = ApiKeys(current_app.config)
    key, auth = keys.authenticate(request.headers.get("Authorization"))
    return keys, key, auth


@public_api_bp.get("/models")
def models():
    _, _, auth = authenticate()
    return jsonify({"object": "list", "data": [{"id": item["id"], "object": "model", "created": 0, "owned_by": "workspace" if item["id"].startswith("credential:") else "platform", "name": item["name"]} for item in list_configs(current_app.config, auth) if item["available"]]})


@public_api_bp.get("/corpora/<corpus_id>/passages/<chunk_id>")
def passage(corpus_id, chunk_id):
    keys, key, auth = authenticate()
    keys.scope(key["id"], corpus_id)
    scope = CorpusAccess(current_app.config).resolve(auth, corpus_id)
    result = resolve_passage(current_app.config, scope.retrieval_project, chunk_id, citation_project=scope.project)
    if result is None:
        raise ApiError("source_not_found", 404)
    result["source_view_url"] = f"/v1/corpora/{quote(corpus_id, safe='')}/passages/{quote(chunk_id, safe='')}"
    return jsonify(result)


def validate(payload):
    if not isinstance(payload, dict):
        raise ApiError("json_object_required")
    if set(payload) - {"model", "messages", "stream", "stream_options", "corpus_id", "mode", "temperature", "max_tokens"}:
        raise ApiError("unsupported_request_field")
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) != 1 or not isinstance(messages[0], dict) or set(messages[0]) != {"role", "content"} or messages[0]["role"] != "user":
        raise ApiError("one_user_message_required")
    message = messages[0]["content"]
    try:
        valid = isinstance(message, str) and bool(message.strip()) and len(message.encode("utf-8")) <= 1024
    except UnicodeError:
        valid = False
    if not valid:
        raise ApiError("invalid_message")
    if type(payload.get("stream", False)) is not bool:
        raise ApiError("invalid_stream")
    if "stream_options" in payload and (not isinstance(payload["stream_options"], dict) or set(payload["stream_options"]) != {"include_usage"} or type(payload["stream_options"]["include_usage"]) is not bool):
        raise ApiError("unsupported_stream_options")
    if "temperature" in payload and (type(payload["temperature"]) not in (int, float) or payload["temperature"] != 0):
        raise ApiError("temperature_fixed_at_zero")
    if "max_tokens" in payload and (type(payload["max_tokens"]) is not int or payload["max_tokens"] != 1024):
        raise ApiError("max_tokens_fixed_at_1024")
    mode = payload.get("mode", "vector")
    if not isinstance(mode, str) or mode not in MODES:
        raise ApiError("unsupported_mode")
    if not isinstance(payload.get("model"), str) or not payload["model"]:
        raise ApiError("explicit_model_required")
    return message.strip(), mode


@public_api_bp.post("/chat/completions")
def chat():
    keys, key, auth = authenticate()
    request.max_content_length = 16 * 1024
    payload = request.get_json(silent=True)
    message, mode = validate(payload)
    corpus_id, model = payload.get("corpus_id"), payload["model"]
    keys.scope(key["id"], corpus_id)
    scope = CorpusAccess(current_app.config).resolve(auth, corpus_id)
    resolve(current_app.config, auth, model)
    request_id = keys.begin(key, corpus_id, model)
    try:
        result = QueryService(current_app.config, scope.project, auth, retrieval_project=scope.retrieval_project).answer(message, mode, generation_config=model)
        keys.scope(key["id"], corpus_id)
        CorpusAccess(current_app.config).resolve(auth, corpus_id)
    except Exception as exc:
        keys.finish(request_id, getattr(exc, "status", 503))
        raise
    sources = [source | {"source_view_url": f"/v1/corpora/{quote(corpus_id, safe='')}/passages/{quote(source['chunk_id'], safe='')}"} for source in result["sources"]]
    rag = {"corpus_id": corpus_id, "mode": mode, "status": result["status"], "query_run_id": result["query_run_id"], "generation": result["generation"], "vector_generation": result["vector_generation"], "graph_generation": result["graph_generation"]}
    envelope = {"id": "chatcmpl-" + result["query_run_id"], "created": int(time.time()), "model": model}
    usage = result["generation"].get("usage")
    if not payload.get("stream", False):
        keys.finish(request_id, 200, result)
        return jsonify(envelope | {"object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": result["answer"]}, "finish_reason": "stop"}], "citations": sources, "rag": rag, **({"usage": usage} if usage else {})})

    def stream():
        completed = False
        try:
            base = envelope | {"object": "chat.completion.chunk"}
            yield "data: " + json.dumps(base | {"choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}) + "\n\n"
            for offset in range(0, len(result["answer"]), 80):
                yield "data: " + json.dumps(base | {"choices": [{"index": 0, "delta": {"content": result["answer"][offset:offset + 80]}, "finish_reason": None}]}) + "\n\n"
            yield "data: " + json.dumps(base | {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "citations": sources, "rag": rag, **({"usage": usage} if usage else {})}) + "\n\n"
            completed = True
            yield "data: [DONE]\n\n"
        finally:
            keys.finish(request_id, 200 if completed else 499, result)

    response = Response(stream(), mimetype="text/event-stream", headers={"X-Accel-Buffering": "no"})
    response.call_on_close(lambda: keys.finish(request_id, 499, result))
    return response
