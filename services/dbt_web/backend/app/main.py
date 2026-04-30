from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Tuple

from flask import Flask, Response, jsonify
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.blueprints import api_v1, ui
from app.core.config import settings
from app.core.errors import DbtWebError, error_payload
from app.state import AppState

logger = logging.getLogger(__name__)


def _bootstrap_model_index(state: AppState) -> None:
    for target in ("marts", "vault", "staging"):
        manifest = state.storage.get_json(f"dbt-artifacts/latest-success/{target}/manifest.json") or {}
        if manifest:
            state.model_index = state.lineage.build_index(manifest)
            logger.info("bootstrapped model_index from %s manifest (%d nodes)", target, len(state.model_index))
            return
    logger.info("no published manifest found in storage; model_index left empty")


def _root_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app() -> Flask:
    root = _root_dir()
    _ui = settings.dbt_web_ui_url_prefix
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
        static_url_path=f"{_ui}/static",
    )
    app.config["SECRET_KEY"] = settings.dbt_web_secret_key

    state = AppState()
    try:
        _bootstrap_model_index(state)
    except Exception as exc:  # noqa: BLE001
        logger.warning("model_index bootstrap failed: %s", exc)
    app.extensions["dbt_ctx"] = state

    app.register_blueprint(api_v1.bp, url_prefix="/api/v1")
    app.register_blueprint(ui.bp, url_prefix=_ui)

    @app.errorhandler(DbtWebError)
    def handle_dbt_web_error(exc: DbtWebError) -> Tuple[Any, int]:
        trace_id = str(uuid.uuid4())
        code, body = error_payload(exc, trace_id)
        return jsonify(body), code

    @app.route("/metrics", methods=["GET"])
    def metrics() -> Response:
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    return app


app = create_app()
