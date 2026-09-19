import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from app import create_app, cleanup_work
from app.services import cpf_detector
from test_web import app, client, login


@pytest.fixture
def config_env(monkeypatch):
    monkeypatch.setattr('app.load_dotenv', lambda: None)
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('SECRET_KEY', 'test-only')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH', 'pbkdf2:sha256:1$salt$hash')


def test_local_defaults(config_env):
    application = create_app()
    assert application.config['WORK_DIR'] == str(Path(application.instance_path) / 'work')
    assert application.config['OCR_MODEL_DIR'] == str(Path(application.instance_path) / 'ocr-models')
    assert application.config['SQLALCHEMY_DATABASE_URI'] == f'sqlite:///{application.instance_path}/database.db'
    assert application.config['MAX_CONTENT_LENGTH'] == 4 * 1024 * 1024
    assert not application.debug


def test_vercel_defaults(config_env, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:////tmp/database.db')
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    monkeypatch.setenv('FLASK_DEBUG', '1')
    monkeypatch.setenv('DEBUG_OMR', 'false')
    application = create_app()
    assert application.config['WORK_DIR'] == '/tmp/work'
    assert application.config['OCR_MODEL_DIR'] == '/tmp/ocr-models'
    assert application.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:////tmp/database.db'
    assert application.config['SESSION_COOKIE_SECURE']
    assert not application.config['DEBUG_OMR']
    assert not application.debug
    assert Path('/tmp/work').is_dir()
    assert Path('/tmp/ocr-models').is_dir()


def test_vercel_requires_explicit_database(config_env, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    with pytest.raises(RuntimeError, match='DATABASE_URL'):
        create_app()


def test_database_environment(config_env, monkeypatch, tmp_path):
    uri = f'sqlite:///{tmp_path}/custom.db'
    monkeypatch.setenv('DATABASE_URL', uri)
    assert create_app().config['SQLALCHEMY_DATABASE_URI'] == uri


def test_pages_do_not_construct_ocr(client, app, monkeypatch):
    constructor = Mock(side_effect=AssertionError('OCR initialized by ordinary page'))
    monkeypatch.setattr(cpf_detector, 'EasyOCRDigitRecognizer', constructor)
    login(client)
    for url in ['/login', '/', '/answer-keys', '/history', '/capture']:
        assert client.get(url).status_code in (200, 302)
    assert app.extensions['digit_recognizer'] is None
    constructor.assert_not_called()


def test_recognizer_created_once_even_with_concurrency(app, monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(cpf_detector, 'EasyOCRDigitRecognizer', constructor)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: cpf_detector.get_digit_recognizer(app), range(12)))
    assert all(result is results[0] for result in results)
    constructor.assert_called_once_with(app.config['OCR_MODEL_DIR'])


def test_reader_lazy_and_download_disabled(tmp_path, monkeypatch):
    reader = Mock()
    reader.return_value.recognize.return_value = [([], '1', .99)]
    monkeypatch.setitem(sys.modules, 'easyocr', SimpleNamespace(Reader=reader))
    recognizer = cpf_detector.EasyOCRDigitRecognizer(str(tmp_path))
    reader.assert_not_called()
    for _ in range(2):
        assert recognizer.recognize(np.zeros((20, 20), dtype=np.uint8)) == '1'
    assert reader.call_count == 1
    assert reader.call_args.kwargs['download_enabled'] is False
    assert reader.call_args.kwargs['model_storage_directory'] == str(tmp_path)


@pytest.mark.parametrize('kind', ['missing', 'empty', 'file'])
def test_cleanup_unavailable_directory(tmp_path, kind):
    directory = tmp_path / 'work'
    if kind == 'empty':
        directory.mkdir()
    elif kind == 'file':
        directory.write_text('not a directory')
    cleanup_work(SimpleNamespace(config={'WORK_DIR': str(directory)}))


def test_missing_tables_message(config_env):
    application = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite://'})
    client = application.test_client()
    with client.session_transaction() as session:
        session['authenticated'] = True
    response = client.get('/history')
    assert response.status_code == 503
    assert 'flask --app index init-db' in response.text


def test_debug_disabled_does_not_write_images(client, app):
    from test_web import upload
    token = login(client)
    upload(client, token)
    assert client.post('/process', data={'csrf_token': token}).location.endswith('/review')
    assert not list(Path(app.config['WORK_DIR']).rglob('debug'))


def test_init_db_preserves_records(app):
    from app.models import db, Exam
    result = app.test_cli_runner().invoke(args=['init-db'])
    assert result.exit_code == 0
    with app.app_context():
        assert db.session.get(Exam, 1).name == 'Prova teste'


def test_startup_does_not_construct_recognizer(config_env, monkeypatch):
    constructor = Mock(side_effect=AssertionError('OCR initialized at startup'))
    monkeypatch.setattr(cpf_detector, 'EasyOCRDigitRecognizer', constructor)
    application = create_app()
    assert application.extensions['digit_recognizer'] is None
    constructor.assert_not_called()


def test_prepare_script_import_does_not_download(monkeypatch):
    import runpy
    reader = Mock(side_effect=AssertionError('Unexpected model download'))
    monkeypatch.setitem(sys.modules, 'easyocr', SimpleNamespace(Reader=reader))
    runpy.run_path('scripts/prepare_ocr.py', run_name='import_test')
    reader.assert_not_called()
