import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, inspect, select

from app import create_app
from app.models import db
from app.services.student_repository import StudentDuplicateError, StudentRepository


@pytest.fixture
def app(tmp_path):
    application = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
        'ADMIN_PASSWORD_HASH': 'pbkdf2:sha256:1$salt$hash',
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'WORK_DIR': str(tmp_path / 'work'),
    })
    with application.app_context():
        participants = Table('participants', MetaData(), Column('cpf', String(14)), Column('grade', Integer), Column('origem', String(20)))
        participants.create(db.engine)
        db.session.execute(participants.insert(), [
            {'cpf': '123.456.789-09', 'grade': 4, 'origem': 'legado'},
            {'cpf': '529.982.247-25', 'grade': 7, 'origem': 'legado'},
        ])
        db.session.commit()
    return application


def test_find_and_update_only_external_grade(app):
    with app.app_context():
        repository = StudentRepository()
        assert repository.find_by_cpf('12345678909').found
        assert not repository.find_by_cpf('00000000000').found
        repository.update_grade_by_cpf('12345678909', 24)
        db.session.commit()
        participants = Table('participants', MetaData(), autoload_with=db.engine)
        rows = db.session.execute(select(participants).order_by(participants.c.cpf)).mappings().all()
        assert rows[0] == {'cpf': '123.456.789-09', 'grade': 24, 'origem': 'legado'}
        assert rows[1] == {'cpf': '529.982.247-25', 'grade': 7, 'origem': 'legado'}


def test_duplicate_cpf_is_rejected(app):
    with app.app_context():
        participants = Table('participants', MetaData(), autoload_with=db.engine)
        db.session.execute(participants.insert().values(cpf='123.456.789-09', grade=1, origem='duplicado'))
        db.session.commit()
        with pytest.raises(StudentDuplicateError):
            StudentRepository().find_by_cpf('12345678909')


def test_init_db_never_creates_external_student_table(tmp_path):
    application = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
        'ADMIN_PASSWORD_HASH': 'pbkdf2:sha256:1$salt$hash',
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'WORK_DIR': str(tmp_path / 'work'),
    })
    with application.app_context():
        db.create_all()
        assert 'participants' not in inspect(db.engine).get_table_names()
