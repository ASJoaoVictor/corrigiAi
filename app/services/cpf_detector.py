"""Replace DigitRecognizer without changing the correction workflow."""
import logging
import threading
from pathlib import Path
import cv2
from app.omr.template_loader import crop
from .cpf_validator import validate_cpf
log=logging.getLogger(__name__)

class EasyOCRDigitRecognizer:
    def __init__(self, model_directory):
        self.directory=model_directory
        self.reader=None
        self.lock=threading.Lock()

    def recognize(self, cell):
        with self.lock:
            if self.reader is None:
                import easyocr
                self.reader=easyocr.Reader(['en'],gpu=False,detector=False,model_storage_directory=self.directory,user_network_directory=str(Path(self.directory)/'user_network'),download_enabled=False,verbose=False)
            enlarged=cv2.resize(cell,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
            enlarged=cv2.copyMakeBorder(enlarged,20,20,20,20,cv2.BORDER_CONSTANT,value=255)
            results=self.reader.recognize(enlarged,allowlist='0123456789',detail=1,paragraph=False)
            if len(results)==1:
                _,digit,confidence=results[0]
                if len(digit)==1 and digit in '0123456789' and confidence>=.80:
                    return digit
            return None

def extract_cpf_region(gray,template):
    return crop(gray,template['cpf']['region'])

def detect_cpf(gray,template,recognizer):
    log.info('[CPF] Processando 11 células')
    digits=[]
    try:
        for region in template['cpf']['cells']:
            cell=crop(gray,region,inset=4)
            if cv2.countNonZero(cv2.threshold(cell,140,255,cv2.THRESH_BINARY_INV)[1])<5:
                digits.append(None)
            else: digits.append(recognizer.recognize(cell))
    except (ImportError, OSError, RuntimeError):
        log.warning('[CPF] OCR indisponível; revisão manual necessária')
        return dict(value='',status='not_detected',message='OCR indisponível. Digite o CPF manualmente.')
    value=''.join(d or '?' for d in digits)
    status=('valid' if validate_cpf(value) else 'invalid') if all(digits) else ('uncertain' if any(digits) else 'not_detected')
    log.info('[CPF] Reconhecimento concluído: %s',status)
    return dict(value=value if any(digits) else '',status=status,message='Confira os 11 dígitos antes de confirmar.')


def get_digit_recognizer(app):
    with app.extensions['digit_recognizer_lock']:
        recognizer = app.extensions.get('digit_recognizer')
        if recognizer is None:
            recognizer = EasyOCRDigitRecognizer(app.config['OCR_MODEL_DIR'])
            app.extensions['digit_recognizer'] = recognizer
        return recognizer
