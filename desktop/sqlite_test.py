"""Explicit offline test edition. Never imports credentials from production."""
from pathlib import Path
from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from .database import DatabaseSetupError
from .logging_config import log_failure
from app.models import db
from app.database import initialize_database

TEST_PORT = 8001
TEST_NAME = 'corrigiAi Testes'


def desktop_database_path():
    # Windows shell resolves redirected/OneDrive desktops and translated names.
    from win32com.shell import shell, shellcon
    desktop = Path(shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOPDIRECTORY, None, 0))
    directory = desktop / 'corrigiAi Testes'
    directory.mkdir(parents=True, exist_ok=True)
    return directory / 'corrigiai-testes.sqlite3'


def sqlite_url(path):
    return URL.create('sqlite', database=str(Path(path).resolve())).render_as_string(hide_password=False)


def prepare_test_database(app):
    if not app.config.get('SQLITE_TEST_MODE') or make_url(app.config['SQLALCHEMY_DATABASE_URI']).get_backend_name() != 'sqlite':
        raise ValueError('O modo de testes exige um banco SQLite local.')
    try:
        with app.app_context():
            if db.engine.dialect.name != 'sqlite':
                raise ValueError('O modo de testes exige um banco SQLite local.')
            initialize_database()
            # Only this explicit edition owns its local participants table.
            table = Table('participants', MetaData(), Column('cpf', String(14), primary_key=True), Column('grade', Integer))
            table.create(db.engine, checkfirst=True)
    except SQLAlchemyError as error:
        log_failure('sqlite_test_initialization_failed', error)
        raise DatabaseSetupError('Não foi possível abrir o SQLite de testes. Confira as permissões e o espaço livre na Área de Trabalho.') from None
