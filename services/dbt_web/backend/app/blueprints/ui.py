from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import Blueprint, redirect, render_template, request, session, url_for

from app.core.config import settings

bp = Blueprint("ui", __name__)

F = TypeVar("F", bound=Callable[..., Any])


def _login_required(view: F) -> F:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not session.get("dbt_ok"):
            nxt = request.path if request.path and request.path != url_for("ui.login") else url_for("ui.runs")
            return redirect(url_for("ui.login", next=nxt))
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


@bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if session.get("dbt_ok") and request.method == "GET":
        nxt = request.args.get("next") or url_for("ui.runs")
        if not str(nxt).startswith("/dbt-web"):
            nxt = url_for("ui.runs")
        return redirect(nxt)
    err = None
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = (request.form.get("password") or "").strip()
        if u == settings.dbt_web_auth_user and p == settings.dbt_web_auth_password:
            session["dbt_ok"] = "1"
            nxt = request.form.get("next") or request.args.get("next") or url_for("ui.runs")
            if not str(nxt).startswith("/dbt-web"):
                nxt = url_for("ui.runs")
            return redirect(nxt)
        err = "Invalid username or password."
    return render_template("login.html", error=err, next=request.args.get("next", ""))


@bp.route("/logout", methods=["POST"])
def logout() -> Any:
    session.clear()
    return redirect(url_for("ui.login"))


@bp.route("/")
@_login_required
def index() -> Any:
    return redirect(url_for("ui.runs"))


@bp.route("/runs", methods=["GET"])
@_login_required
def runs() -> Any:
    return render_template("runs.html", active="runs")


@bp.route("/models", methods=["GET"])
@_login_required
def models() -> Any:
    return render_template("models.html", active="models")


@bp.route("/lineage", methods=["GET"])
@_login_required
def lineage() -> Any:
    return render_template("lineage.html", active="lineage")


@bp.route("/lineag", methods=["GET"])
@_login_required
def lineage_typo() -> Any:
    return redirect(url_for("ui.lineage"), 301)


@bp.route("/tests", methods=["GET"])
@_login_required
def tests() -> Any:
    return render_template("tests.html", active="tests")


@bp.route("/docs", methods=["GET"])
@_login_required
def docs() -> Any:
    return render_template("docs.html", active="docs")


@bp.route("/docs/models/<path:model_unique_id>", methods=["GET"])
@_login_required
def docs_model(model_unique_id: str) -> Any:
    return render_template("doc_placeholder.html", kind="Model", doc_id=model_unique_id, active="docs")


@bp.route("/docs/sources/<path:source_unique_id>", methods=["GET"])
@_login_required
def docs_source(source_unique_id: str) -> Any:
    return render_template("doc_placeholder.html", kind="Source", doc_id=source_unique_id, active="docs")


@bp.route("/docs/tests/<path:test_unique_id>", methods=["GET"])
@_login_required
def docs_test(test_unique_id: str) -> Any:
    return render_template("doc_placeholder.html", kind="Test", doc_id=test_unique_id, active="docs")


@bp.route("/artifacts", methods=["GET"])
@_login_required
def artifacts() -> Any:
    return render_template("artifacts.html", active="artifacts")
