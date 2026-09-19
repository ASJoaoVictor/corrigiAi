"""Interactive local setup: stores only a password hash."""
import getpass
from pathlib import Path
import secrets
from werkzeug.security import generate_password_hash
root=Path(__file__).resolve().parents[1]
target=root/'.env'
if target.exists():
    raise SystemExit('.env já existe. Edite-o diretamente; nenhum arquivo foi alterado.')
username=input('Usuário da organização [admin]: ').strip() or 'admin'
if not username.replace('_','').replace('-','').isalnum():
    raise SystemExit('Use letras, números, _ ou - no usuário.')
password=getpass.getpass('Senha (pelo menos 10 caracteres): ')
if len(password)<10 or password!=getpass.getpass('Confirme a senha: '):
    raise SystemExit('Senha curta ou confirmação diferente. Tente novamente.')
with target.open('x') as file:
    file.write(f"SECRET_KEY={secrets.token_hex(32)}\nADMIN_USERNAME={username}\nADMIN_PASSWORD_HASH='{generate_password_hash(password)}'\nDEBUG_OMR=false\nCOOKIE_SECURE=false\nPORT=5000\n")
target.chmod(0o600)
print('.env criado. Execute: flask --app run.py init-db')
