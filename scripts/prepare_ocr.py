"""Download OCR models once; no participant images or CPF are sent."""
from pathlib import Path
import easyocr
root=Path(__file__).resolve().parents[1]
models=root/'instance/ocr-models'
models.mkdir(parents=True,exist_ok=True)
easyocr.Reader(['en'],gpu=False,detector=False,model_storage_directory=str(models),user_network_directory=str(models/'user_network'),download_enabled=True,verbose=False)
print('Modelos OCR disponíveis localmente.')
