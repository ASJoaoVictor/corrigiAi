import io
import logging
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from app.omr.template_loader import pixel_rect
from .omr_processor import detect_answers
from .cpf_detector import detect_cpf
log=logging.getLogger(__name__)
Image.MAX_IMAGE_PIXELS=25_000_000

class ImageProcessingError(ValueError): pass

def load_image(source):
    try:
        with Image.open(source) as im:
            if im.format not in ('JPEG','PNG','WEBP'): raise ImageProcessingError('Use uma imagem JPEG, PNG ou WebP.')
            if im.width*im.height>25_000_000: raise ImageProcessingError('Imagem grande demais. Use até 25 megapixels.')
            im=ImageOps.exif_transpose(im).convert('RGB')
            im.thumbnail((2400,2400))
            result=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ImageProcessingError('Imagem inválida ou corrompida. Tire outra foto.') from e
    if min(result.shape[:2])<500: raise ImageProcessingError('Foto pequena demais. Aproxime a câmera e tente novamente.')
    if np.mean(convert_to_grayscale(result))<45: raise ImageProcessingError('Foto muito escura. Procure um local iluminado.')
    return result

def convert_to_grayscale(image): return cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
def normalize_image(image):
    gray=convert_to_grayscale(image)
    background=cv2.GaussianBlur(gray,(0,0),25)
    return cv2.divide(gray,background,scale=255)
def apply_threshold(gray): return cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]

def detect_document(image):
    gray=convert_to_grayscale(image)
    edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),50,150)
    contours,_=cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours,key=cv2.contourArea,reverse=True):
        polygon=cv2.approxPolyDP(contour,.02*cv2.arcLength(contour,True),True)
        if len(polygon)==4 and cv2.isContourConvex(polygon) and cv2.contourArea(polygon)>.30*gray.size:
            return polygon.reshape(4,2)
    return None

def correct_perspective(image,reference,template):
    # Feature registration also handles rotation and verifies the actual printed model.
    orb=cv2.ORB_create(nfeatures=6000)
    kp1,d1=orb.detectAndCompute(convert_to_grayscale(image),None)
    kp2,d2=orb.detectAndCompute(convert_to_grayscale(reference),None)
    if d1 is None or d2 is None: raise ImageProcessingError('Cartão não encontrado. Fotografe a folha inteira, com boa luz.')
    pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1,d2,k=2)
    good=[a for pair in pairs if len(pair)==2 for a,b in [pair] if a.distance < .70*b.distance]
    if len(good)<30: raise ImageProcessingError('Cartão não identificado. Confira o modelo e tire outra foto.')
    src=np.float32([kp1[m.queryIdx].pt for m in good]);dst=np.float32([kp2[m.trainIdx].pt for m in good])
    matrix,inliers=cv2.findHomography(src,dst,cv2.RANSAC,3)
    if matrix is None or inliers.sum()<25 or inliers.mean()<.30:
        raise ImageProcessingError('Não foi possível alinhar o cartão. Tire outra foto.')
    points=dst[inliers.ravel()==1]
    w,h=template['normalized_width'],template['normalized_height']
    if np.ptp(points[:,0]) < w*.55 or np.ptp(points[:,1]) < h*.55:
        raise ImageProcessingError('Cartão parcialmente visível. Inclua toda a folha na foto.')
    corners=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]]).reshape(-1,1,2)
    projected=cv2.perspectiveTransform(corners,np.linalg.inv(matrix)).reshape(4,2)
    ih,iw=image.shape[:2]
    if not np.isfinite(projected).all() or not cv2.isContourConvex(projected) or any(x < -iw*.025 or y < -ih*.025 or x>iw*1.025 or y>ih*1.025 for x,y in projected):
        raise ImageProcessingError('Bordas cortadas ou perspectiva excessiva. Tire outra foto.')
    log.info('[OMR] Documento localizado; perspectiva corrigida')
    return cv2.warpPerspective(image,matrix,(w,h),borderValue=(255,255,255))

def generate_debug_image(image,template,answers=None):
    out=image.copy()
    for r in [template['cpf']['region']]+template['cpf']['cells']:
        x,y,w,h=pixel_rect(r,out.shape[1],out.shape[0]);cv2.rectangle(out,(x,y),(x+w,y+h),(255,0,0),2)
    for q in template['questions']['regions']:
        result=(answers or {}).get(str(q['number']),{})
        for b in q['bubbles']:
            x,y,w,h=pixel_rect(b,out.shape[1],out.shape[0]);color=(0,160,0) if result.get('answer')==b['answer'] else (0,0,230)
            cv2.rectangle(out,(x,y),(x+w,y+h),color,1)
            cv2.putText(out,f"{q['number']}{b['answer']}",(x,y-3),cv2.FONT_HERSHEY_SIMPLEX,.3,color,1)
        b=q['bubbles'][0];x,y,_,_=pixel_rect(b,out.shape[1],out.shape[0])
        cv2.putText(out,result.get('answer') or result.get('status',''),(x-60,y+12),cv2.FONT_HERSHEY_SIMPLEX,.3,(255,0,0),1)
    return out

def process_card(path,template,recognizer,debug_dir=None):
    try:
        original=load_image(path); log.info('[OMR] Imagem recebida')
        log.info('[OMR] Template carregado: %s',template['name'])
        document=original.copy();quad=detect_document(original)
        if quad is not None: cv2.polylines(document,[quad],True,(0,200,0),3)
        reference=cv2.imread(str(Path(__file__).parents[1]/'omr/reference.png'))
        if reference is None: raise ImageProcessingError('Referência do modelo indisponível.')
        warped=correct_perspective(original,reference,template)
        gray=normalize_image(warped);threshold=apply_threshold(gray)
        cpf=detect_cpf(gray,template,recognizer)
        answers=detect_answers(threshold,template)
        if debug_dir:
            Path(debug_dir).mkdir(parents=True,exist_ok=True)
            for name,im in [('01_original',original),('02_document',document),('03_warped',warped),('04_threshold',threshold),('05_cpf_cells',generate_debug_image(warped,template)),('06_answer_regions',generate_debug_image(warped,template)),('07_result',generate_debug_image(warped,template,answers))]:
                cv2.imwrite(str(Path(debug_dir)/f'{name}.jpg'),im)
        log.info('[OMR] Processamento concluído')
        return dict(cpf=cpf,answers=answers)
    except cv2.error as e:
        raise ImageProcessingError('Erro ao analisar a imagem. Tire outra foto com boa iluminação.') from e
