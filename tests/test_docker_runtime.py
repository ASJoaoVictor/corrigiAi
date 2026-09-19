"""Runtime contract used by Docker, without requiring Docker or OCR downloads."""
import sys

from werkzeug.security import generate_password_hash

from app import create_app
from app.models import db, Exam


def test_runtime_paths_health_and_persistence(monkeypatch, tmp_path):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('SECRET_KEY', 'runtime-test-only')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH', generate_password_hash('test-password'))
    database = tmp_path / 'data' / 'database.db'
    database.parent.mkdir()
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{database}')
    monkeypatch.setenv('WORK_DIR', str(tmp_path / 'temporary'))
    monkeypatch.setenv('OCR_MODEL_DIR', str(tmp_path / 'models'))
    # Any accidental eager OCR import fails this test without downloading models.
    monkeypatch.setitem(sys.modules, 'easyocr', None)
    application = create_app()
    assert application.config['WORK_DIR'] == str(tmp_path / 'temporary')
    assert application.config['OCR_MODEL_DIR'] == str(tmp_path / 'models')
    assert application.config['DEBUG'] is False
    response = application.test_client().get('/health')
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}
    assert 'Set-Cookie' not in response.headers
    assert application.extensions['digit_recognizer'] is None
    assert application.test_cli_runner().invoke(args=['init-db']).exit_code == 0
    with application.app_context():
        db.session.add(Exam(name='Persistent test'))
        db.session.commit()
        db.session.remove()
        db.engine.dispose()
    restarted = create_app()
    assert restarted.test_cli_runner().invoke(args=['init-db']).exit_code == 0
    with restarted.app_context():
        assert db.session.execute(db.select(Exam.name)).scalars().all() == ['Persistent test']
        db.session.remove()
        db.engine.dispose()
