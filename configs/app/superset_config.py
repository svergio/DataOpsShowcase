import os

SQLALCHEMY_DATABASE_URI = os.getenv(
    "SQLALCHEMY_DATABASE_URI",
    "sqlite:////app/superset_home/superset.db",
)

SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "change_me_superset_secret")
WTF_CSRF_ENABLED = True
FEATURE_FLAGS = {"ENABLE_TEMPLATE_PROCESSING": True}
ENABLE_PROXY_FIX = True

SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
}
