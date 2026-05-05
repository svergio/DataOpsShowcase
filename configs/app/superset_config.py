import os

from flask import Flask

SQLALCHEMY_DATABASE_URI = os.getenv(
    "SQLALCHEMY_DATABASE_URI",
    "sqlite:////app/superset_home/superset.db",
)

SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "change_me_superset_secret")
WTF_CSRF_ENABLED = True
FEATURE_FLAGS = {"ENABLE_TEMPLATE_PROCESSING": True}
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {
    "x_for": 1,
    "x_proto": 1,
    "x_host": 1,
    "x_port": 1,
    "x_prefix": 1,
}
LOAD_EXAMPLES = False

_INGRESS = os.getenv("INGRESS_BASE_URL", "http://localhost:8090").rstrip("/")
SUPERSET_WEBSERVER_BASE_URL = os.getenv(
    "SUPERSET_WEBSERVER_BASE_URL",
    f"{_INGRESS}/superset/",
)

SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
}


def FLASK_APP_MUTATOR(app: Flask) -> None:
    from superset.views import utils as superset_view_utils
    from superset.views.core import Superset

    Superset.route_base = ""

    _orig_redirect_to_login = superset_view_utils.redirect_to_login

    def redirect_to_login(next_target: str | None = None):
        from flask import has_request_context, request

        if next_target is None and has_request_context():
            root = request.root_path.rstrip("/")
            if request.query_string:
                qs = request.query_string.decode()
                next_target = f"{root}{request.path}?{qs}"
            else:
                next_target = f"{root}{request.path}"
            return _orig_redirect_to_login(next_target=next_target)
        return _orig_redirect_to_login(next_target=next_target)

    superset_view_utils.redirect_to_login = redirect_to_login
    import superset.views.core as superset_core

    superset_core.redirect_to_login = redirect_to_login
