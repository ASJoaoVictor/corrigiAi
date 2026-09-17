from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db=SQLAlchemy()
def now(): return datetime.now(timezone.utc)

class Exam(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(120),nullable=False)
    template_id=db.Column(db.String(80),nullable=False,default='opi_fundamental_2026')
    number_of_questions=db.Column(db.Integer,nullable=False,default=30)
    created_at=db.Column(db.DateTime,default=now,nullable=False)
    answer_key=db.relationship('AnswerKey',uselist=False,backref='exam',cascade='all, delete-orphan')

class AnswerKey(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    exam_id=db.Column(db.Integer,db.ForeignKey('exam.id'),unique=True,nullable=False)
    answers_json=db.Column(db.JSON,nullable=False)

class Correction(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    exam_id=db.Column(db.Integer,db.ForeignKey('exam.id'),nullable=False,index=True)
    exam=db.relationship('Exam')
    cpf=db.Column(db.String(11),nullable=False,index=True)
    answers_json=db.Column(db.JSON,nullable=False)
    answer_key_json=db.Column(db.JSON,nullable=False)
    correct_count=db.Column(db.Integer,nullable=False)
    wrong_count=db.Column(db.Integer,nullable=False)
    manual_review=db.Column(db.Boolean,nullable=False,default=False)
    external_sync_status=db.Column(db.String(16),nullable=False,default='pending')
    external_sync_id=db.Column(db.String(120),nullable=True)
    submission_token=db.Column(db.String(64),unique=True,nullable=False)
    created_at=db.Column(db.DateTime,default=now,nullable=False)
