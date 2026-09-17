from copy import deepcopy
from app.models import Correction, db

def compare_answers(answers,key):
    correct=sum(a['status']=='detected' and a['answer']==key.get(n) for n,a in answers.items())
    return correct,len(answers)-correct

def apply_manual_answers(answers,form):
    updated=deepcopy(answers)
    for n,a in updated.items():
        value=form.get(f'q{n}','keep')
        if value=='keep': continue
        if value not in list('ABCDE')+['blank']: raise ValueError('Resposta inválida.')
        answer=None if value=='blank' else value
        status='blank' if answer is None else 'detected'
        a.update(answer=answer,status=status,manually_changed=(answer!=a['original_answer'] or status!=a['original_status']))
    return updated

def find_duplicates(exam_id,cpf):
    return db.session.scalars(db.select(Correction).filter_by(exam_id=exam_id,cpf=cpf).order_by(Correction.created_at.desc())).all()
