import io
import json
import re
import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from app.models import db,Exam,AnswerKey,Correction
from app.services.correction_service import find_duplicates

@pytest.fixture
def app(tmp_path):
    app=create_app(dict(TESTING=True,SECRET_KEY='test-secret',ADMIN_USERNAME='admin',ADMIN_PASSWORD_HASH=generate_password_hash('test-password'),SQLALCHEMY_DATABASE_URI='sqlite://',WORK_DIR=str(tmp_path/'work'),DEBUG_OMR=False))
    with app.app_context():
        db.create_all();exam=Exam(name='Prova teste');db.session.add(exam);db.session.flush();db.session.add(AnswerKey(exam_id=exam.id,answers_json={str(n):'A' for n in range(1,31)}));db.session.commit()
    return app

@pytest.fixture
def client(app):return app.test_client()

def csrf(client,path='/login'):
    client.get(path)
    with client.session_transaction() as s:return s['csrf_token']

def login(client):
    response=client.post('/login',data=dict(csrf_token=csrf(client),username='admin',password='test-password'))
    assert response.status_code==302
    return csrf(client,'/')

def test_auth_and_csrf(client):
    for url in ['/','/capture','/preview','/photo','/review','/confirm','/history','/answer-keys']:
        assert client.get(url).status_code==302
    assert client.post('/login',data={}).status_code==400
    assert b'incorretos' in client.post('/login',data=dict(csrf_token=csrf(client),username='admin',password='wrong')).data
    login(client)
    assert client.get('/').status_code==200

def test_answer_key_validation(client,app):
    token=login(client)
    response=client.post('/answer-keys/1',data={'csrf_token':token,'q1':'A'})
    assert '30 questões' in response.text
    response=client.post('/answer-keys/1',data={'csrf_token':token,**{f'q{n}':'B' for n in range(1,31)}})
    assert response.status_code==302
    with app.app_context(): assert db.session.get(Exam,1).answer_key.answers_json['30']=='B'

def upload(client,token):
    with open('app/omr/reference.png','rb') as f:
        response=client.post('/capture',data={'csrf_token':token,'exam_id':'1','photo':(io.BytesIO(f.read()),'card.png')},content_type='multipart/form-data')
    assert response.status_code==302

def test_full_workflow_duplicates_cleanup(client,app):
    token=login(client)
    for version in range(2):
        upload(client,token)
        assert client.get('/preview').status_code==200
        assert client.get('/photo').status_code==200
        response=client.post('/process',data={'csrf_token':token})
        assert response.location.endswith('/review')
        assert client.get('/review').status_code==200
        response=client.post('/review',data={'csrf_token':token,'cpf':'123.456.789-09','q1':'A','q2':'B'})
        assert response.location.endswith('/confirm')
        confirmation=client.get('/confirm');assert confirmation.status_code==200
        assert '12345678909' not in confirmation.text and '***.***.***-09' in confirmation.text
        if version:
            assert 'Já existe uma correção' in confirmation.text
            assert client.post('/confirm',data={'csrf_token':token}).status_code==200
        response=client.post('/confirm',data={'csrf_token':token,'ack_duplicate':'yes'})
        assert response.status_code==302
        with app.app_context():
            records=find_duplicates(1,'12345678909');assert len(records)==version+1
            c=records[0];assert c.correct_count==1 and c.wrong_count==29 and c.manual_review
            assert c.external_sync_status=='pending' and c.answers_json['1']['manually_changed']
        assert not list(__import__('pathlib').Path(app.config['WORK_DIR']).iterdir())
        assert client.post('/confirm',data={'csrf_token':token}).status_code==302
        assert client.get(response.location).status_code==200
    history=client.get('/history')
    assert '12345678909' not in history.text
    assert '***.***.***-09' in history.text

def test_invalid_cpf_cannot_save(client,app):
    token=login(client);upload(client,token);client.post('/process',data={'csrf_token':token})
    response=client.post('/review',data={'csrf_token':token,'cpf':'11111111111'})
    assert 'CPF inválido' in response.text
    assert client.post('/confirm',data={'csrf_token':token}).location.endswith('/review')
    with app.app_context():assert db.session.query(Correction).count()==0

def test_bad_upload_and_size(client,app):
    token=login(client)
    response=client.post('/capture',data={'csrf_token':token,'exam_id':'1','photo':(io.BytesIO(b'broken'),'photo.jpg')},content_type='multipart/form-data')
    assert 'corrompida' in response.text
    app.config['MAX_CONTENT_LENGTH']=100
    assert client.post('/capture',data={'csrf_token':token,'photo':(io.BytesIO(b'x'*500),'big.jpg')}).status_code==413

def test_logout_deletes_photo(client,app):
    token=login(client);upload(client,token)
    assert client.post('/logout',data={'csrf_token':token}).status_code==302
    assert not list(__import__('pathlib').Path(app.config['WORK_DIR']).iterdir())
