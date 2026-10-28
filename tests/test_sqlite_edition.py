from pathlib import Path
import pytest
from sqlalchemy import inspect, MetaData, Table, select
from desktop.application import desktop_app
from desktop.config import new_config, validate_config, ConfigurationError
from desktop.paths import application_paths, AppPaths
from desktop.sqlite_test import sqlite_url, prepare_test_database, TEST_PORT
from app.models import db, Exam, AnswerKey, Correction
from app import create_app
from test_web import login, upload


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    # A populated production env must never select a production connection.
    monkeypatch.setenv('DATABASE_URL', 'postgresql://do-not-use:secret@invalid.invalid/db')
    paths = application_paths({'LOCALAPPDATA': str(tmp_path)}, sqlite_test=True)
    paths.prepare()
    monkeypatch.setattr(AppPaths, 'models', property(lambda self: tmp_path / 'models'))
    database = tmp_path / 'Desktop' / 'corrigiAi Testes' / 'corrigiai-testes.sqlite3'
    database.parent.mkdir(parents=True)
    config = new_config(sqlite_url(database), 'admin', 'test-password', sqlite_test=True)
    app = desktop_app(config, paths, sqlite_test=True)
    app.config['TESTING'] = True
    prepare_test_database(app)
    yield app, database
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_sqlite_is_opt_in_and_config_separate(tmp_path):
    url = sqlite_url(tmp_path / 'test.sqlite3')
    with pytest.raises(ConfigurationError): new_config(url, 'admin', 'test-password')
    config = new_config(url, 'admin', 'test-password', sqlite_test=True)
    with pytest.raises(ConfigurationError): validate_config(config)
    production = new_config('postgresql://user:password@host/db', 'admin', 'test-password')
    with pytest.raises(ConfigurationError): validate_config(production, sqlite_test=True)
    env = {'LOCALAPPDATA': str(tmp_path)}
    assert application_paths(env).root != application_paths(env, sqlite_test=True).root
    assert TEST_PORT != 8000


def test_initialization_persists_and_does_not_reset_grades(local_app):
    app, database = local_app
    with app.app_context():
        assert db.engine.dialect.name == 'sqlite'
        assert set(inspect(db.engine).get_table_names()) == {'participants', 'exam', 'answer_key', 'correction'}
        table = Table('participants', MetaData(), autoload_with=db.engine)
        db.session.execute(table.insert().values(cpf='123.456.789-09', grade=12))
        db.session.commit()
    prepare_test_database(app)
    with app.app_context():
        assert db.session.execute(select(table.c.grade)).scalar_one() == 12
    assert database.is_file()


def test_full_local_correction_workflow(local_app):
    app, database = local_app
    client = app.test_client()
    assert client.get('/test-participants').status_code == 302
    token = login(client)
    assert 'SQLite local' in client.get('/').text
    assert client.post('/test-participants', data={'cpf': '12345678909'}).status_code == 400
    bad = client.post('/test-participants', data={'csrf_token': token, 'cpf': '11111111111'})
    assert 'dígitos verificadores' in bad.text
    assert client.post('/test-participants', data={'csrf_token': token, 'cpf': '12345678909'}).status_code == 302
    again = client.post('/test-participants', data={'csrf_token': token, 'cpf': '12345678909'})
    assert 'já está cadastrado' in again.text
    with app.app_context():
        exam = Exam(name='Prova de teste'); db.session.add(exam); db.session.flush()
        db.session.add(AnswerKey(exam_id=exam.id, answers_json={str(n): 'A' for n in range(1, 31)})); db.session.commit()
    upload(client, token)
    client.post('/process', data={'csrf_token': token})
    client.post('/review', data={'csrf_token': token, 'cpf': '12345678909', 'q1': 'A'})
    client.get('/confirm')
    assert client.post('/confirm', data={'csrf_token': token}).status_code == 302
    with app.app_context():
        correction = db.session.scalar(db.select(Correction))
        assert correction is not None
        table = Table('participants', MetaData(), autoload_with=db.engine)
        assert db.session.execute(select(table.c.grade)).scalar_one() == correction.correct_count


def test_production_does_not_register_test_route(tmp_path):
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'SECRET_KEY': 'test',
        'ADMIN_PASSWORD_HASH': 'pbkdf2:sha256:1$salt$hash', 'WORK_DIR': str(tmp_path / 'work')})
    assert 'test_participants.index' not in app.view_functions
    assert app.test_client().get('/test-participants').status_code == 404
    with pytest.raises(ValueError): prepare_test_database(app)


def test_desktop_path_uses_windows_shell_for_redirected_desktop(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock
    from desktop.sqlite_test import desktop_database_path
    redirected = tmp_path / 'OneDrive' / 'Área de Trabalho'
    api = Mock(return_value=str(redirected))
    monkeypatch.setitem(sys.modules, 'win32com.shell', SimpleNamespace(
        shell=SimpleNamespace(SHGetFolderPath=api),
        shellcon=SimpleNamespace(CSIDL_DESKTOPDIRECTORY=16)))
    path = desktop_database_path()
    assert path == redirected / 'corrigiAi Testes' / 'corrigiai-testes.sqlite3'
    assert path.parent.is_dir()
    api.assert_called_once_with(0, 16, None, 0)


def test_local_edition_has_own_cookie(local_app):
    app, _ = local_app
    assert app.config['SESSION_COOKIE_NAME'] == 'corrigiai_test_session'
