"""Acesso isolado à tabela externa ``public.participants``.

Esta tabela é administrada por outro sistema. Por isso ela é refletida em um
``MetaData`` separado e nunca participa de ``db.create_all()``.
"""
from dataclasses import dataclass
import logging

from flask import current_app
from sqlalchemy import MetaData, Table, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.models import db
from .cpf_validator import format_cpf

logger = logging.getLogger(__name__)


class StudentRepositoryError(Exception):
    """Erro seguro para exibir ao operador, sem detalhes da conexão."""


class StudentNotFoundError(StudentRepositoryError):
    pass


class StudentDuplicateError(StudentRepositoryError):
    pass


@dataclass(frozen=True)
class StudentLookup:
    found: bool


class StudentRepository:
    def _table(self):
        """Reflete a tabela somente no primeiro uso, dentro do app context."""
        cache_key = 'external_student_table'
        cached = current_app.extensions.get(cache_key)
        if cached is not None:
            return cached
        try:
            # SQLite is supported only by the automated tests. PostgreSQL uses
            # the explicit public schema required by the production database.
            schema = 'public' if db.engine.dialect.name == 'postgresql' else None
            table = Table('participants', MetaData(), schema=schema, autoload_with=db.engine)
            missing = {'cpf', 'grade'} - set(table.c.keys())
            if missing:
                raise StudentRepositoryError('Cadastro de alunos incompatível com a integração.')
        except StudentRepositoryError:
            raise
        except SQLAlchemyError as error:
            logger.error('Falha ao acessar a tabela externa de alunos: %s', type(error).__name__)
            raise StudentRepositoryError('Não foi possível consultar o cadastro de alunos.') from error
        current_app.extensions[cache_key] = table
        return table

    def find_by_cpf(self, cpf):
        """Retorna apenas se há exatamente um aluno para o CPF informado."""
        table = self._table()
        formatted_cpf = format_cpf(cpf)
        try:
            rows = db.session.execute(
                select(table.c.cpf).where(table.c.cpf == formatted_cpf).limit(2)
            ).all()
        except SQLAlchemyError as error:
            logger.error('Falha ao consultar aluno por CPF: %s', type(error).__name__)
            raise StudentRepositoryError('Não foi possível consultar o cadastro de alunos.') from error
        if len(rows) > 1:
            raise StudentDuplicateError('Há mais de um aluno com este CPF. Corrija o cadastro antes de confirmar.')
        return StudentLookup(found=bool(rows))

    def update_grade_by_cpf(self, cpf, grade):
        """Atualiza exclusivamente ``grade`` de um único aluno na sessão atual."""
        table = self._table()
        lookup = self.find_by_cpf(cpf)
        if not lookup.found:
            raise StudentNotFoundError('Aluno não encontrado. Confira o CPF antes de confirmar.')
        try:
            result = db.session.execute(
                update(table).where(table.c.cpf == format_cpf(cpf)).values(grade=grade)
            )
        except SQLAlchemyError as error:
            logger.error('Falha ao atualizar nota do aluno: %s', type(error).__name__)
            raise StudentRepositoryError('Não foi possível atualizar a nota do aluno.') from error
        if result.rowcount != 1:
            if result.rowcount == 0:
                raise StudentNotFoundError('Aluno não encontrado. Confira o CPF antes de confirmar.')
            raise StudentDuplicateError('Há mais de um aluno com este CPF. Corrija o cadastro antes de confirmar.')
