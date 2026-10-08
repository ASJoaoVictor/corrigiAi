"""Installer helpers run inside the Docker image, never on the host."""
import getpass
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import json
import urllib.request

from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from werkzeug.security import generate_password_hash


def database_url(value):
    if value.startswith('postgres://'):
        value = 'postgresql://' + value[len('postgres://'):]
    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise ValueError("Connection string PostgreSQL inválida.") from None
    if url.drivername not in ('postgresql', 'postgresql+psycopg2', 'postgresql+psycopg') or not url.host or not url.database or not url.username or not url.password:
        raise ValueError('Informe uma connection string PostgreSQL completa do Supabase.')
    return value


def quote(value):
    if any(c in value for c in '\r\n\x00'):
        raise ValueError('A configuração deve ocupar uma única linha.')
    # Single quotes prevent Compose from interpolating dollar signs.
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def configure(root=Path('/config')):
    target = root / '.env'
    if target.is_symlink():
        raise ValueError('.env não pode ser um link simbólico.')
    exists = target.exists()
    if exists:
        choice = input('.env existente: [1] reutilizar [2] reconfigurar: ').strip()
        if choice == '1':
            values = dotenv_values(target, interpolate=False)
            current_url = values.get('DATABASE_URL') or ''
            if database_url(current_url) != current_url:
                raise ValueError('Reconfigure para normalizar o prefixo PostgreSQL.')
            if not values.get('SECRET_KEY') or values['SECRET_KEY'] == 'change-me' or not values.get('ADMIN_USERNAME') or not (values.get('ADMIN_PASSWORD_HASH') or '').startswith(('scrypt:', 'pbkdf2:')) or 'ADMIN_PASSWORD' in values:
                raise ValueError('.env incompleto ou com senha em texto puro. Execute novamente e escolha reconfigurar.')
            target.chmod(0o600)
            print('Configuração existente preservada.')
            return
        if choice != '2':
            raise ValueError('Instalação cancelada; .env preservado.')
    username = input('Usuário administrador [admin]: ').strip() or 'admin'
    if not username.replace('_', '').replace('-', '').isalnum():
        raise ValueError('Use letras, números, _ ou - no usuário.')
    password = getpass.getpass('Senha (pelo menos 10 caracteres): ')
    if len(password) < 10 or password != getpass.getpass('Confirme a senha: '):
        raise ValueError('Senha curta ou confirmação diferente; .env preservado.')
    print('Informe a connection string PostgreSQL do Supabase (entrada oculta).')
    url = database_url(getpass.getpass('DATABASE_URL: ').strip())
    replacements = {
        'SECRET_KEY': secrets.token_hex(32),
        'ADMIN_USERNAME': username,
        'ADMIN_PASSWORD_HASH': generate_password_hash(password),
        'DATABASE_URL': url,
    }
    del password
    # Preserve unrelated settings when explicitly reconfiguring an existing file.
    source = target if exists else root / '.env.example'
    lines = []
    for line in source.read_text(encoding='utf-8-sig').splitlines():
        key = line.split('=', 1)[0].strip().removeprefix('export ').strip()
        if key not in replacements and key != 'ADMIN_PASSWORD':
            lines.append(line)
    lines.extend(f'{key}={quote(value)}' for key, value in replacements.items())
    content = '\n'.join(lines) + '\n'
    fd, temporary = tempfile.mkstemp(prefix='.install-', dir=root)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
        if exists:
            os.replace(temporary, target)
        else:
            # Exclusive creation: do not overwrite a concurrently created .env.
            with target.open('x', encoding='utf-8') as stream:
                target.chmod(0o600)
                stream.write(content)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print('.env salvo; somente o hash da senha foi armazenado.')


def health():
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2) as response:
                if response.status == 200 and json.load(response).get('status') == 'ok':
                    return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise ValueError('A aplicação não respondeu dentro do tempo esperado.')


if __name__ == '__main__':
    try:
        {'configure': configure, 'health': health}[sys.argv[1]]()
    except (Exception, KeyboardInterrupt):
        # Never print exception details: URLs and credentials may be embedded.
        print('Não foi possível concluir esta etapa. Confira os dados informados; ao reutilizar .env, verifique DATABASE_URL e as credenciais. Nenhum segredo foi exibido.', file=sys.stderr)
        sys.exit(1)
