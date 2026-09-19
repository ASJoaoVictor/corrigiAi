"""Explicit model download; importing this module never loads OCR or downloads."""
import os
from pathlib import Path


def main():
    import easyocr
    root = Path(__file__).resolve().parents[1]
    models = Path('/tmp/ocr-models') if os.getenv('VERCEL') else root/'instance/ocr-models'
    models.mkdir(parents=True, exist_ok=True)
    easyocr.Reader(['en'], gpu=False, detector=False,
                   model_storage_directory=str(models),
                   user_network_directory=str(models/'user_network'),
                   download_enabled=True, verbose=False)
    print('Modelos OCR disponíveis localmente.')


if __name__ == '__main__':
    main()
