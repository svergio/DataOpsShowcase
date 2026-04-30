from __future__ import annotations

import logging
import os

from flask import Flask, Response, jsonify, render_template

from catalog import API_AND_TOOLS, GRAPH_LINKS, GRAPH_NODES, WEB_UI_SERVICES
from status_service import build_graph_payload, build_service_rows, try_snapshots

logging.basicConfig(level=os.environ.get("PORTAL_LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    root = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
        static_url_path="/static",
    )

    @app.get("/health")
    def health() -> Response:
        return Response("OK", status=200, mimetype="text/plain")

    def _payload() -> dict[str, object]:
        snap, err = try_snapshots()
        return {
            "services_web": build_service_rows(WEB_UI_SERVICES, snap),
            "services_api": build_service_rows(API_AND_TOOLS, snap),
            "graph": build_graph_payload(GRAPH_NODES, GRAPH_LINKS, snap),
            "docker_error": err,
        }

    @app.get("/api/status")
    def api_status() -> Response:
        return jsonify(_payload())

    @app.get("/")
    def index() -> str:
        return render_template("index.html", portal_data=_payload())

    return app


app = create_app()
