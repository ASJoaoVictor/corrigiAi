"""Database preflight with actionable messages that never include driver payloads."""
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from app.models import db
from app.database import initialize_database
from .logging_config import log_failure


class DatabaseSetupError(ValueError): pass


def database_failure(error, stage):
    """Inspect driver diagnostics internally; return only predefined safe text."""
    original = getattr(error, 'orig', None)
    state = getattr(original, 'sqlstate', None) or getattr(original, 'pgcode', None)
    # libpq connection failures often lack SQLSTATE. Never display or log this text.
    detail = str(original if original is not None else error).lower()
    if state in ('28P01', '28000') or 'password authentication failed' in detail:
        reason = 'authentication'
        message = ('O banco recusou as credenciais. Confira o usuário e a senha do banco '
                   'na URL copiada em Connect → Session pooler no Supabase.')
    elif 'tenant or user not found' in detail:
        reason = 'pooler_identity'
        message = ('O pooler não reconheceu o projeto ou usuário. Copie novamente a URL '
                   'em Connect → Session pooler, preservando host e usuário completos.')
    elif state == '42501' or 'permission denied' in detail:
        reason = 'permissions'
        message = ('O usuário do banco não tem as permissões necessárias. Solicite ao responsável '
                   'acesso ao schema public, leitura de participants.cpf e atualização de participants.grade. '
                   'Na configuração inicial, também é necessário criar as tabelas próprias do corrigiAi.')
    elif state == '3D000':
        reason = 'database_name'
        message = 'O banco informado na URL não existe. Confira o nome do banco na conexão do Supabase.'
    elif any(marker in detail for marker in ('could not translate host name', 'getaddrinfo failed', 'name or service not known', 'nodename nor servname')):
        reason = 'dns'
        message = 'Não foi possível localizar o servidor do banco. Confira o host da URL e a conexão com a internet.'
    elif any(marker in detail for marker in ('ssl', 'tls', 'certificate')):
        reason = 'ssl'
        message = ('Não foi possível estabelecer a conexão SSL com o banco. Confira os parâmetros SSL '
                   'da URL do Supabase e a data/hora do computador. Não desative a proteção SSL.')
    elif any(marker in detail for marker in ('timeout', 'timed out', 'connection refused', 'network is unreachable', 'no route to host')):
        reason = 'network'
        message = ('O servidor do banco não respondeu. Verifique se o projeto Supabase está ativo, '
                   'se a rede permite a porta indicada na URL e tente outra rede, se necessário.')
    else:
        reason = 'unknown'
        message = ('Não foi possível acessar o banco de dados. Confira a URL em Connect → Session pooler '
                   'no Supabase e verifique sua conexão com a internet.')
    if stage == 'initialize':
        message = 'A conexão foi estabelecida, mas não foi possível inicializar as tabelas do corrigiAi. ' + message
    return reason, message


def prepare_database(app):
    stage = 'connect'
    with app.app_context():
        try:
            with db.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                stage = 'schema'
                inspector = inspect(connection)
                if not inspector.has_table('participants', schema='public'):
                    raise DatabaseSetupError('A tabela de alunos public.participants não foi encontrada.')
                columns = {column['name'] for column in inspector.get_columns('participants', schema='public')}
                if not {'cpf', 'grade'} <= columns:
                    raise DatabaseSetupError('A estrutura da tabela participants não é compatível (cpf/grade).')
                # Reflection alone does not verify that this role can read the CPF.
                connection.execute(text('SELECT cpf, grade FROM public.participants LIMIT 0'))
            stage = 'initialize'
            initialize_database()
        except SQLAlchemyError as error:
            reason, message = database_failure(error, stage)
            log_failure(f'database_{stage}_{reason}', error)
            raise DatabaseSetupError(message) from None
