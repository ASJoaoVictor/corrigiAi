"""Real EasyOCR smoke test with synthetic printed digits; not handwriting validation."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from app.omr.template_loader import load_template,pixel_rect
from app.services.cpf_detector import EasyOCRDigitRecognizer,detect_cpf
from app.services.image_processor import normalize_image
root=Path(__file__).resolve().parents[1]
im=cv2.imread(str(root/'app/omr/reference.png'));template=load_template()
for region,digit in zip(template['cpf']['cells'],'12345678909'):
    x,y,w,h=pixel_rect(region,im.shape[1],im.shape[0])
    cv2.putText(im,digit,(x+7,y+h-12),cv2.FONT_HERSHEY_SIMPLEX,1.0,(0,0,0),2,cv2.LINE_AA)
result=detect_cpf(normalize_image(im),template,EasyOCRDigitRecognizer(str(root/'instance/ocr-models')))
print('CPF synthetic OCR status:',result['status'])
assert result['status']=='valid', 'Synthetic CPF not confidently recognized; inspect digit service.'
assert result['value']=='12345678909'
print('11 synthetic printed digits recognized correctly; real handwriting still needs validation.')
