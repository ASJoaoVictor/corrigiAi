"""Initialize only application-owned tables; external metadata stays separate."""
from .models import db, Exam, AnswerKey, Correction


def initialize_database():
    db.metadata.create_all(db.engine, tables=[Exam.__table__, AnswerKey.__table__, Correction.__table__])
