"""Validate onedir allowlist and generate deterministic WiX components."""
from pathlib import Path
import hashlib
import sys
import xml.etree.ElementTree as ET

NS = 'http://wixtoolset.org/schemas/v4/wxs'
ET.register_namespace('', NS)


def validate_payload(root):
    required = ['corrigiAi.exe', '_internal/app/templates/base.html', '_internal/app/static/js/app.js',
                '_internal/app/omr/reference.png', '_internal/app/omr/templates/opi_fundamental_2026.json',
                '_internal/ocr-models/english_g2.pth']
    if any(not (root / name).is_file() for name in required):
        raise ValueError('Distribuição incompleta: executável, recursos ou OCR ausentes.')
    forbidden = {'.env', 'database.db', 'settings.dpapi', 'config.json'}
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if path.is_symlink() or path.name in forbidden or path.name.startswith('.env.') or any(p in ('tests', 'backups', 'uploads', 'processed', 'work', '.git') for p in relative.parts):
            raise ValueError('Arquivo não permitido na distribuição.')


def generate_payload(root, target):
    validate_payload(root)
    wix = ET.Element(f'{{{NS}}}Wix')
    fragment = ET.SubElement(wix, f'{{{NS}}}Fragment')
    directory = ET.SubElement(fragment, f'{{{NS}}}DirectoryRef', Id='INSTALLFOLDER')
    group = ET.SubElement(fragment, f'{{{NS}}}ComponentGroup', Id='Payload')
    directories = {Path('.'): directory}
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix() != 'corrigiAi.exe')
    for path in files:
        relative = path.relative_to(root)
        current = Path('.')
        for part in relative.parts[:-1]:
            parent = current
            current = current / part
            if current not in directories:
                id_ = 'D' + hashlib.sha256(current.as_posix().encode()).hexdigest()[:24]
                directories[current] = ET.SubElement(directories[parent], f'{{{NS}}}Directory', Id=id_, Name=part)
        id_ = 'C' + hashlib.sha256(relative.as_posix().encode()).hexdigest()[:24]
        component = ET.SubElement(directories[current], f'{{{NS}}}Component', Id=id_, Guid='*', Bitness='always64')
        ET.SubElement(component, f'{{{NS}}}File', Id='F' + id_[1:], Source=str(path.resolve()), KeyPath='yes')
        ET.SubElement(group, f'{{{NS}}}ComponentRef', Id=id_)
    ET.indent(wix)
    ET.ElementTree(wix).write(target, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    generate_payload(Path(sys.argv[1]), Path(sys.argv[2]))
