"""Construct Flask for an installed, writable per-user environment."""
from app import create_app


def desktop_app(config, paths):
    return create_app({**config, 'INSTANCE_PATH': str(paths.root),
                       'WORK_DIR': str(paths.work), 'OCR_MODEL_DIR': str(paths.models),
                       'OCR_USER_NETWORK_DIR': str(paths.root / 'ocr-user-network'),
                       'DESKTOP_MODE': True, 'DEBUG': False, 'DEBUG_OMR': False, 'SESSION_COOKIE_SECURE': False,
                       'SQLALCHEMY_ENGINE_OPTIONS': {'hide_parameters': True, 'pool_pre_ping': True,
                                                    'connect_args': {'connect_timeout': 10}}},
                      load_environment=False)

