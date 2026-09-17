import logging
import cv2
import numpy as np
from app.omr.template_loader import crop
log = logging.getLogger(__name__)

def fill_ratio(region):
    if region.size == 0: raise ValueError('Região de resposta vazia.')
    h,w=region.shape[:2]
    yy,xx=np.ogrid[:h,:w]
    mask=((xx-(w-1)/2)/(w*.40))**2+((yy-(h-1)/2)/(h*.40))**2 <= 1
    return float(np.mean(region[mask]>0))

def classify_answer(ratios, thresholds):
    order=sorted(range(5),key=lambda i:ratios[i],reverse=True)
    first,second=(ratios[i] for i in order[:2])
    if sum(v>=thresholds['multiple_mark'] for v in ratios)>1: state='multiple'
    elif first < thresholds['blank_max']: state='blank'
    elif first < thresholds['min_fill'] or first-second < thresholds['min_difference']: state='ambiguous'
    else: state='detected'
    return dict(answer='ABCDE'[order[0]] if state=='detected' else None,status=state,ratios=ratios)

def detect_answers(threshold,template):
    answers={}
    for q in template['questions']['regions']:
        result=classify_answer([fill_ratio(crop(threshold,b)) for b in q['bubbles']],template['thresholds'])
        result.update(original_answer=result['answer'],original_status=result['status'],manually_changed=False)
        answers[str(q['number'])]=result
        log.info('[OMR] Q%02d -> %s',q['number'],result['answer'] or result['status'].upper())
    return answers
