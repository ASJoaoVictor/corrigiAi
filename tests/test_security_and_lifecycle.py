import io
import os
import time
from pathlib import Path
import cv2
import numpy as np
import pytest
from app import cleanup_work
from app.services.image_processor import load_image,ImageProcessingError,correct_perspective,process_card
from app.omr.template_loader import load_template
from test_web import app,client,login,upload


def test_expired_work(app):
    expired=Path(app.config['WORK_DIR'])/'expired'
    expired.mkdir();(expired/'photo.jpg').write_bytes(b'test')
    os.utime(expired,(time.time()-3601,time.time()-3601))
    live=Path(app.config['WORK_DIR'])/'live';live.mkdir()
    cleanup_work(app)
    assert not expired.exists() and live.exists()


def test_dark_photo():
    ok,data=cv2.imencode('.jpg',np.zeros((800,600,3),np.uint8));assert ok
    with pytest.raises(ImageProcessingError,match='escura'):load_image(io.BytesIO(data.tobytes()))


def test_cropped_card_is_rejected():
    reference=cv2.imread('app/omr/reference.png')
    with pytest.raises(ImageProcessingError):correct_perspective(reference[450:],reference,load_template())


def test_debug_files_and_no_cpf_logs(tmp_path,caplog):
    class Unknown:
        def recognize(self,image):return None
    with caplog.at_level('INFO'):
        result=process_card('app/omr/reference.png',load_template(),Unknown(),tmp_path)
    assert len(list(tmp_path.glob('*.jpg')))==7
    assert '[OMR] Processamento concluído' in caplog.text
    assert result['cpf']['status']=='not_detected'


def test_private_photo_is_not_shared_between_sessions(client,app):
    token=login(client);upload(client,token)
    other=app.test_client();login(other)
    assert other.get('/photo').status_code==400
    assert client.get('/photo').headers['Cache-Control']=='no-store'


def test_key_snapshot_does_not_change_mid_review(client,app):
    from app.models import db,Exam,Correction
    token=login(client);upload(client,token);client.post('/process',data={'csrf_token':token})
    with app.app_context():
        db.session.get(Exam,1).answer_key.answers_json={str(n):'B' for n in range(1,31)};db.session.commit()
    client.post('/review',data={'csrf_token':token,'cpf':'12345678909','q1':'A'})
    client.get('/confirm');client.post('/confirm',data={'csrf_token':token})
    with app.app_context():
        c=db.session.scalar(db.select(Correction));assert c.correct_count==1 and c.answer_key_json['1']=='A'


def test_processing_busy_does_not_start_ocr(client, app, monkeypatch):
    token=login(client);upload(client,token)
    def unexpected(*args, **kwargs): raise AssertionError('OCR não deve iniciar')
    monkeypatch.setattr('app.routes.correction.process_card', unexpected)
    lock=app.extensions['processing_lock']
    lock.acquire()
    try:
        response=client.post('/process',data={'csrf_token':token},follow_redirects=True)
        assert 'processando outro cartão' in response.text
        assert lock.locked()
    finally: lock.release()


def test_processing_failure_releases_lock(client, app, monkeypatch):
    token=login(client);upload(client,token)
    def fail(*args, **kwargs): raise ValueError('Falha controlada')
    monkeypatch.setattr('app.routes.correction.process_card', fail)
    response=client.post('/process',data={'csrf_token':token})
    assert response.location.endswith('/preview')
    assert not app.extensions['processing_lock'].locked()
