"""Explicit model download; importing this module never loads OCR or downloads."""
import os
from pathlib import Path
from dotenv import load_dotenv


def main():
    import easyocr
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root/'.env')
    default = Path('/tmp/ocr-models') if os.getenv('VERCEL') else root/'instance/ocr-models'
    models = Path(os.getenv('OCR_MODEL_DIR') or default)
    models.mkdir(parents=True, exist_ok=True)
    easyocr.Reader(['en'], gpu=False, detector=False,
                   model_storage_directory=str(models),
                   user_network_directory=str(models/'user_network'),
                   download_enabled=True, verbose=False)
    print('Modelos OCR disponíveis localmente.')


if __name__ == '__main__':
    main()
