import cv2
import numpy as np
import pytest
from app.services.cpf_validator import normalize_cpf,validate_cpf,mask_cpf
from app.omr.template_loader import load_template,pixel_rect
from app.services.omr_processor import fill_ratio,classify_answer,detect_answers
from app.services.correction_service import compare_answers,apply_manual_answers
from app.services.image_processor import normalize_image,apply_threshold,correct_perspective,load_image,ImageProcessingError
from app.services.cpf_detector import detect_cpf

@pytest.mark.parametrize('value,expected',[('123.456.789-09','12345678909'),(None,''),('abc12','12')])
def test_normalize(value,expected): assert normalize_cpf(value)==expected
@pytest.mark.parametrize('value,expected',[('12345678909',True),('529.982.247-25',True),('12345678908',False),('11111111111',False),('',False),('123',False)])
def test_validate(value,expected): assert validate_cpf(value)==expected

def test_mask():
    assert mask_cpf('123.456.789-09')=='***.***.***-09'
    assert mask_cpf('12')=='***.***.***-??'

def test_template():
    t=load_template()
    assert len(t['questions']['regions'])==30
    assert sum(len(q['bubbles']) for q in t['questions']['regions'])==150
    cells=t['cpf']['cells'];assert cells[9]['x']>cells[8]['x']+cells[8]['width']
    with pytest.raises(ValueError):load_template('../invalid')

def test_coordinates(): assert pixel_rect(dict(x=.1,y=.2,width=.3,height=.4),100,200)==(10,40,30,80)
def test_fill_ratio():
    assert fill_ratio(np.zeros((40,40),np.uint8))==0
    assert fill_ratio(np.full((40,40),255,np.uint8))==1

@pytest.mark.parametrize('ratios,status,answer',[
    ([.1,.2,.8,.1,.1],'detected','C'),
    ([.1,.2,.1,.1,.1],'blank',None),
    ([.8,.9,.1,.1,.1],'multiple',None),
    ([.45,.2,.1,.1,.1],'ambiguous',None),
    ([.61,.46,.1,.1,.1],'ambiguous',None),
])
def test_classification(ratios,status,answer):
    a=classify_answer(ratios,load_template()['thresholds']);assert (a['status'],a['answer'])==(status,answer)

def test_scoring_and_manual():
    a={'1':dict(status='multiple',answer=None,original_answer=None,original_status='multiple',manually_changed=False),'2':dict(status='detected',answer='B',original_answer='B',original_status='detected',manually_changed=False)}
    key={'1':'A','2':'B'}
    assert compare_answers(a,key)==(1,1)
    changed=apply_manual_answers(a,{'q1':'A','q2':'blank'})
    assert changed['1']['manually_changed'] and changed['2']['manually_changed']
    assert compare_answers(changed,key)==(1,1)
    assert a['1']['answer'] is None
    with pytest.raises(ValueError): apply_manual_answers(a,{'q1':'X'})

def test_blank_reference_and_marks():
    t=load_template();im=cv2.imread('app/omr/reference.png')
    answers=detect_answers(apply_threshold(normalize_image(im)),t)
    assert all(a['status']=='blank' for a in answers.values())
    expected={}
    for q in t['questions']['regions']:
        b=q['bubbles'][(q['number']-1)%5];x,y,w,h=pixel_rect(b,im.shape[1],im.shape[0])
        cv2.circle(im,(x+w//2,y+h//2),int(w*.46),(0,0,0),-1)
        expected[str(q['number'])]=b['answer']
    result=detect_answers(apply_threshold(normalize_image(im)),t)
    assert {n:a['answer'] for n,a in result.items()}==expected
    assert compare_answers(result,expected)==(30,0)

@pytest.mark.parametrize('rotation',[None,cv2.ROTATE_90_CLOCKWISE,cv2.ROTATE_180,cv2.ROTATE_90_COUNTERCLOCKWISE])
def test_rotation_and_perspective(rotation):
    t=load_template();reference=cv2.imread('app/omr/reference.png');im=reference.copy()
    x,y,w,h=pixel_rect(t['questions']['regions'][14]['bubbles'][2],im.shape[1],im.shape[0]);cv2.circle(im,(x+w//2,y+h//2),17,(0,0,0),-1)
    src=np.float32([[0,0],[1298,0],[1298,1838],[0,1838]])
    dst=np.float32([[130,90],[1440,170],[1350,2030],[80,1940]])
    im=cv2.warpPerspective(im,cv2.getPerspectiveTransform(src,dst),(1550,2130),borderValue=(70,70,70))
    if rotation is not None:im=cv2.rotate(im,rotation)
    aligned=correct_perspective(im,reference,t)
    answers=detect_answers(apply_threshold(normalize_image(aligned)),t)
    assert answers['15']['answer']=='C'
    assert sum(a['status']=='blank' for a in answers.values())==29

def test_reject_non_card():
    t=load_template();ref=cv2.imread('app/omr/reference.png')
    with pytest.raises(ImageProcessingError):correct_perspective(np.full_like(ref,255),ref,t)

def test_cpf_no_invented_digits():
    class Unknown:
        def recognize(self,cell):return None
    im=np.zeros((1839,1299),np.uint8)
    assert detect_cpf(im,load_template(),Unknown())['status']=='not_detected'
    class Sequence:
        def __init__(self):self.digits=iter('12345678909')
        def recognize(self,cell):return next(self.digits)
    assert detect_cpf(im,load_template(),Sequence())['status']=='valid'
