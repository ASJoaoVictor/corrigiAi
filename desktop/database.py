from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from app.models import db
from app.database import initialize_database


class DatabaseSetupError(ValueError): pass


def prepare_database(app):
    with app.app_context():
        try:
            with db.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                inspector = inspect(connection)
                if not inspector.has_table('participants', schema='public'):
                    raise DatabaseSetupError('A tabela de alunos public.participants não foi encontrada.')
                columns = {column['name'] for column in inspector.get_columns('participants', schema='public')}
                if not {'cpf', 'grade'} <= columns:
                    raise DatabaseSetupError('A estrutura da tabela participants não é compatível (cpf/grade).')
            initialize_database()
        except SQLAlchemyError:
            raise DatabaseSetupError('Não foi possível acessar o banco de dados. Verifique sua conexão com a internet e tente novamente.') from None
