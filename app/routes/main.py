from flask import Blueprint, render_template, request
from .auth import login_required
from app.models import db, Exam, Correction
bp=Blueprint('main',__name__)

@bp.get('/')
@login_required
def index(): return render_template('index.html',exams=db.session.scalars(db.select(Exam).order_by(Exam.created_at.desc())).all())

@bp.get('/history')
@login_required
def history():
    page=max(1,request.args.get('page',1,type=int))
    results=db.paginate(db.select(Correction).order_by(Correction.created_at.desc()),page=page,per_page=20,error_out=False)
    return render_template('history.html',results=results)

@bp.get('/history/<int:correction_id>')
@login_required
def detail(correction_id):
    correction=db.get_or_404(Correction,correction_id)
    return render_template('detail.html',correction=correction)
