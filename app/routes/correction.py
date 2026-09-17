import json
import secrets
import shutil
import os
from pathlib import Path
import cv2
from flask import Blueprint, current_app, session, request, redirect, url_for, render_template, flash, send_file, abort
from sqlalchemy.exc import IntegrityError
from .auth import login_required
from app.models import db, Exam, Correction
from app.omr.template_loader import load_template
from app.services.image_processor import load_image, process_card, ImageProcessingError
from app.services.cpf_validator import normalize_cpf, validate_cpf
from app.services.correction_service import compare_answers, apply_manual_answers, find_duplicates
bp=Blueprint('correction',__name__)

def work_path():
    token=session.get('work_token','')
    if not token or len(token)!=32 or any(c not in '0123456789abcdef' for c in token): abort(400,description='Captura expirada. Tire outra foto.')
    path=Path(current_app.config['WORK_DIR'])/token
    if not path.is_dir(): abort(400,description='Captura expirada. Tire outra foto.')
    os.utime(path,None)
    return path

def discard_work():
    token=session.pop('work_token',None)
    if token and len(token)==32 and all(c in '0123456789abcdef' for c in token):
        shutil.rmtree(Path(current_app.config['WORK_DIR'])/token,ignore_errors=True)

def read_draft():
    path=work_path()/'draft.json'
    if not path.exists(): abort(400,description='Processe uma foto antes de revisar.')
    return json.loads(path.read_text())

def save_draft(data):
    path=work_path();temporary=path/'draft.tmp'
    temporary.write_text(json.dumps(data));temporary.replace(path/'draft.json')

def selected_exam():
    exam=db.get_or_404(Exam,session.get('exam_id',0))
    if not exam.answer_key: abort(400,description='Cadastre o gabarito antes de corrigir cartões.')
    return exam

@bp.route('/capture',methods=['GET','POST'])
@login_required
def capture():
    exams=db.session.scalars(db.select(Exam).join(Exam.answer_key)).all()
    if request.method=='POST':
        exam=db.get_or_404(Exam,request.form.get('exam_id',type=int))
        if not exam.answer_key: abort(400,description='Gabarito ausente.')
        uploaded=request.files.get('photo')
        if uploaded is None or not uploaded.filename:
            flash('Selecione ou tire uma foto do cartão.','error')
        else:
            try:
                image=load_image(uploaded.stream)
                discard_work();session['work_token']=secrets.token_hex(16);session['exam_id']=exam.id
                path=Path(current_app.config['WORK_DIR'])/session['work_token'];path.mkdir(mode=0o700)
                cv2.imwrite(str(path/'photo.jpg'),image)
                return redirect(url_for('correction.preview'))
            except ImageProcessingError as e: flash(str(e),'error')
    return render_template('capture.html',exams=exams)

@bp.get('/preview')
@login_required
def preview():
    work_path();return render_template('preview.html',exam=selected_exam())

@bp.get('/photo')
@login_required
def photo():
    path=work_path()/'photo.jpg'
    if not path.exists(): abort(404)
    return send_file(path,mimetype='image/jpeg')

@bp.post('/discard')
@login_required
def discard():
    discard_work();return redirect(url_for('correction.capture'))

@bp.post('/process')
@login_required
def process():
    path=work_path();exam=selected_exam()
    if (path/'draft.json').exists(): return redirect(url_for('correction.review'))
    try:
        template=load_template(exam.template_id)
        result=process_card(path/'photo.jpg',template,current_app.extensions['digit_recognizer'],path/'debug' if current_app.config['DEBUG_OMR'] else None)
        result.update(exam_id=exam.id,key=exam.answer_key.answers_json,submission_token=secrets.token_hex(32),cpf_manually_changed=False)
        save_draft(result)
        return redirect(url_for('correction.review'))
    except (ImageProcessingError,ValueError) as e:
        flash(str(e),'error');return redirect(url_for('correction.preview'))
    except Exception:
        # Do not log exception payloads, which could contain personal data.
        current_app.logger.error('[OMR] Falha interna durante processamento')
        flash('Falha no processamento. Tente novamente ou tire outra foto.','error')
        return redirect(url_for('correction.preview'))

@bp.route('/review',methods=['GET','POST'])
@login_required
def review():
    draft=read_draft();exam=db.get_or_404(Exam,draft['exam_id'])
    if request.method=='POST':
        try: draft['answers']=apply_manual_answers(draft['answers'],request.form)
        except ValueError as e: abort(400,description=str(e))
        cpf=normalize_cpf(request.form.get('cpf'))
        draft['cpf_manually_changed']=draft['cpf_manually_changed'] or cpf!=draft['cpf']['value']
        draft['cpf']['value']=cpf;draft['cpf']['status']='valid' if validate_cpf(cpf) else 'invalid'
        draft.pop('duplicate_ids',None)
        save_draft(draft)
        if not validate_cpf(cpf): flash('CPF inválido. Confira os 11 dígitos e corrija antes de confirmar.','error')
        else: return redirect(url_for('correction.confirm'))
    correct,wrong=compare_answers(draft['answers'],draft['key'])
    return render_template('review.html',draft=draft,exam=exam,correct=correct,wrong=wrong)

@bp.route('/confirm',methods=['GET','POST'])
@login_required
def confirm():
    # A replay of a successful POST cannot insert another record.
    if not session.get('work_token') and session.get('last_correction'):
        return redirect(url_for('main.detail',correction_id=session['last_correction']))
    draft=read_draft();cpf=draft['cpf']['value']
    if not validate_cpf(cpf): return redirect(url_for('correction.review'))
    exam=db.get_or_404(Exam,draft['exam_id']);duplicates=find_duplicates(exam.id,cpf)
    correct,wrong=compare_answers(draft['answers'],draft['key'])
    if request.method=='POST':
        seen=draft.get('duplicate_ids',[])
        if duplicates and (request.form.get('ack_duplicate')!='yes' or seen!=[d.id for d in duplicates]):
            flash('Já existe uma correção para este participante nesta prova. Confira e confirme uma nova versão.','error')
        else:
            record=Correction(exam_id=exam.id,cpf=cpf,answers_json=draft['answers'],answer_key_json=draft['key'],correct_count=correct,wrong_count=wrong,manual_review=draft['cpf_manually_changed'] or any(a['manually_changed'] for a in draft['answers'].values()),submission_token=draft['submission_token'])
            db.session.add(record)
            try: db.session.commit()
            except IntegrityError:
                db.session.rollback();record=db.session.scalar(db.select(Correction).filter_by(submission_token=draft['submission_token']))
                if record is None: raise
            session['last_correction']=record.id;discard_work()
            flash('Correção salva. A foto temporária foi apagada.','success')
            return redirect(url_for('main.detail',correction_id=record.id))
    draft['duplicate_ids']=[d.id for d in duplicates];save_draft(draft)
    student=current_app.extensions['student_provider'].find_by_cpf(cpf)
    return render_template('confirm.html',draft=draft,exam=exam,correct=correct,wrong=wrong,duplicates=duplicates,student=student)
