from flask import Blueprint, render_template, request, redirect, url_for, flash
from .auth import login_required
from app.models import db, Exam, AnswerKey
bp=Blueprint('keys',__name__)

@bp.route('/answer-keys',methods=['GET','POST'])
@login_required
def index():
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if not name or len(name)>120: flash('Informe um nome de até 120 caracteres.','error')
        else:
            exam=Exam(name=name);db.session.add(exam);db.session.commit()
            return redirect(url_for('keys.edit',exam_id=exam.id))
    return render_template('keys.html',exams=db.session.scalars(db.select(Exam).order_by(Exam.id.desc())).all())

@bp.route('/answer-keys/<int:exam_id>',methods=['GET','POST'])
@login_required
def edit(exam_id):
    exam=db.get_or_404(Exam,exam_id)
    answers=exam.answer_key.answers_json if exam.answer_key else {}
    if request.method=='POST':
        answers={str(n):request.form.get(f'q{n}') for n in range(1,31)}
        if any(a not in list('ABCDE') for a in answers.values()):
            flash('Selecione uma alternativa para cada uma das 30 questões.','error')
        else:
            if exam.answer_key: exam.answer_key.answers_json=answers
            else: db.session.add(AnswerKey(exam_id=exam.id,answers_json=answers))
            db.session.commit();flash('Gabarito salvo. Correções anteriores mantêm o gabarito original.','success')
            return redirect(url_for('keys.index'))
    return render_template('answer_key.html',exam=exam,answers=answers)
