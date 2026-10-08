"""Configuration tests need neither Docker nor a real Supabase database."""
from pathlib import Path

import pytest
from dotenv import dotenv_values
from werkzeug.security import check_password_hash

from scripts.install_common import configure, database_url


def answers(monkeypatch, choices, hidden):
    choices, hidden = iter(choices), iter(hidden)
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    monkeypatch.setattr('getpass.getpass', lambda _: next(hidden))


def test_configure_and_reuse(monkeypatch, tmp_path, capsys):
    (tmp_path / '.env.example').write_text(Path('.env.example').read_text())
    url = 'postgresql://user:p%40ss$word@db.example.org/postgres?sslmode=require'
    answers(monkeypatch, ['admin'], ['password123', 'password123', url])
    configure(tmp_path)
    target = tmp_path / '.env'
    original = target.read_bytes()
    values = dotenv_values(target, interpolate=False)
    assert values['DATABASE_URL'] == url
    assert check_password_hash(values['ADMIN_PASSWORD_HASH'], 'password123')
    assert len(values['SECRET_KEY']) == 64
    assert 'password123' not in target.read_text()
    assert 'ADMIN_PASSWORD' not in values
    answers(monkeypatch, ['1'], [])
    configure(tmp_path)
    assert target.read_bytes() == original
    output = capsys.readouterr().out
    for secret in (url, values['SECRET_KEY'], values['ADMIN_PASSWORD_HASH'], 'password123'):
        assert secret not in output


def test_cancel_and_invalid_configuration_preserve_file(monkeypatch, tmp_path):
    target = tmp_path / '.env'
    original = 'CUSTOM=value\n'
    target.write_text(original)
    answers(monkeypatch, ['cancel'], [])
    with pytest.raises(ValueError):
        configure(tmp_path)
    assert target.read_text() == original
    answers(monkeypatch, ['2', 'admin'], ['short', 'short'])
    with pytest.raises(ValueError):
        configure(tmp_path)
    assert target.read_text() == original


def test_reconfigure_preserves_options_removes_plaintext(monkeypatch, tmp_path):
    target = tmp_path / '.env'
    target.write_text('CUSTOM=value\nADMIN_PASSWORD=legacy\nSECRET_KEY=old\n')
    answers(monkeypatch, ['2', 'admin'], ['password123', 'password123', 'postgres://u:p@host/db'])
    configure(tmp_path)
    values = dotenv_values(target, interpolate=False)
    assert values['CUSTOM'] == 'value'
    assert 'ADMIN_PASSWORD' not in values
    assert values['SECRET_KEY'] != 'old'
    assert values['DATABASE_URL'] == 'postgresql://u:p@host/db'


@pytest.mark.parametrize('driver', ['postgresql', 'postgresql+psycopg2', 'postgresql+psycopg'])
def test_accept_supported_postgres_drivers(driver):
    value = f'{driver}://user:password@host/database'
    assert database_url(value) == value


@pytest.mark.parametrize('value', ['', 'sqlite:///local.db', 'postgresql://host/db'])
def test_reject_non_postgres_or_incomplete_url(value):
    with pytest.raises(ValueError):
        database_url(value)


def test_init_db_leaves_existing_aluno_untouched(monkeypatch, tmp_path):
    import sqlite3
    from app import create_app
    from werkzeug.security import generate_password_hash

    path = tmp_path / 'existing.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE aluno (id INTEGER PRIMARY KEY, nome TEXT)')
        connection.execute("INSERT INTO aluno VALUES (1, 'Aluno existente')")
    monkeypatch.delenv('VERCEL', raising=False)
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-only',
        'ADMIN_PASSWORD_HASH': generate_password_hash('test-password'),
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}',
        'WORK_DIR': str(tmp_path / 'work'),
        'OCR_MODEL_DIR': str(tmp_path / 'ocr'),
    })
    for _ in range(2):
        assert app.test_cli_runner().invoke(args=['init-db']).exit_code == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT * FROM aluno').fetchall() == [(1, 'Aluno existente')]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {'aluno', 'exam', 'answer_key', 'correction'}
