"""Per-user configuration encrypted by Windows DPAPI, never by custom crypto."""
import json
import os
import secrets
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from werkzeug.security import generate_password_hash


class ConfigurationError(ValueError): pass


def validate_config(config):
    try:
        expected = {'SQLALCHEMY_DATABASE_URI', 'ADMIN_USERNAME', 'ADMIN_PASSWORD_HASH', 'SECRET_KEY'}
        if set(config) != expected or not all(isinstance(value, str) for value in config.values()):
            raise ValueError()
        url = make_url(config['SQLALCHEMY_DATABASE_URI'])
        valid_url = url.drivername in ('postgresql', 'postgresql+psycopg', 'postgresql+psycopg2') and all((url.host, url.database, url.username, url.password))
        valid = valid_url and bool(config['ADMIN_USERNAME']) and len(config['SECRET_KEY']) >= 32 and config['ADMIN_PASSWORD_HASH'].startswith(('scrypt:', 'pbkdf2:'))
        if not valid: raise ValueError()
    except (KeyError, TypeError, ValueError, ArgumentError):
        raise ConfigurationError('Configuração inválida. Confira a conexão PostgreSQL e as credenciais.') from None
    return config


def new_config(url, username, password):
    username = username.strip()
    if not username or not username.replace('_', '').replace('-', '').isalnum() or len(password) < 10:
        raise ConfigurationError('Use um usuário com letras, números, _ ou - e senha com pelo menos 10 caracteres.')
    if url.startswith('postgres://'): url = 'postgresql://' + url[len('postgres://'):]
    return validate_config(dict(SQLALCHEMY_DATABASE_URI=url.strip(), ADMIN_USERNAME=username,
                                ADMIN_PASSWORD_HASH=generate_password_hash(password), SECRET_KEY=secrets.token_hex(32)))


def save_config(path, config):
    import win32crypt
    validate_config(config)
    encrypted = win32crypt.CryptProtectData(json.dumps(config).encode('utf-8'), 'corrigiAi', None, None, None, 1)
    temporary = path.with_suffix('.tmp')
    try:
        with temporary.open('wb') as stream:
            stream.write(encrypted)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_config(path):
    import win32crypt
    try:
        _, clear = win32crypt.CryptUnprotectData(path.read_bytes(), None, None, None, 1)
        return validate_config(json.loads(clear.decode('utf-8')))
    except Exception:
        raise ConfigurationError('Não foi possível ler a configuração deste usuário. Consulte o suporte da organização.') from None
