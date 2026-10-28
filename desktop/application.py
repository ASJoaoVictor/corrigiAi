"""Construct Flask for an installed, writable per-user environment."""
from app import create_app


def desktop_app(config, paths, *, sqlite_test=False):
    from .config import validate_config
    validate_config(config, sqlite_test=sqlite_test)
    engine_options = {'hide_parameters': True, 'pool_pre_ping': True,
                      'connect_args': {'timeout': 30} if sqlite_test else {'connect_timeout': 10}}
    return create_app({**config, 'INSTANCE_PATH': str(paths.root),
                       'WORK_DIR': str(paths.work), 'OCR_MODEL_DIR': str(paths.models),
                       'OCR_USER_NETWORK_DIR': str(paths.root / 'ocr-user-network'),
                       'DESKTOP_MODE': True, 'SQLITE_TEST_MODE': sqlite_test,
                       'SESSION_COOKIE_NAME': 'corrigiai_test_session' if sqlite_test else 'session', 'DEBUG': False, 'DEBUG_OMR': False, 'SESSION_COOKIE_SECURE': False,
                       'SQLALCHEMY_ENGINE_OPTIONS': engine_options},
                      load_environment=False)

