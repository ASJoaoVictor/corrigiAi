"""Windows logic without GUI, real Supabase, downloads or external listeners."""
import io
import json
import logging
import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from sqlalchemy import inspect
from werkzeug.security import check_password_hash

from app import create_app
from app.database import initialize_database
from app.models import db
from app.runtime import DEFAULT_PORT, resource_path
from desktop.config import ConfigurationError, load_config, new_config, save_config, validate_config
from desktop.network import access_url, lan_addresses, private_ipv4
from desktop.paths import application_paths
from desktop.logging_config import SafeFormatter, log_failure
from desktop.server import LocalServer, PortInUseError, check_port
from desktop.database import DatabaseSetupError, prepare_database


@pytest.mark.parametrize('address', ['10.0.1.2','172.16.0.2','172.31.255.254','192.168.1.2'])
def test_private_lan(address):
    assert private_ipv4(address)
    assert access_url(address, DEFAULT_PORT) == f'http://{address}:8000'


@pytest.mark.parametrize('address', ['127.0.0.1','169.254.1.1','172.32.1.1','8.8.8.8','::1','invalid'])
def test_reject_non_lan(address):
    assert not private_ipv4(address)
    with pytest.raises(ValueError): access_url(address, DEFAULT_PORT)


def test_localhost_and_port():
    assert access_url('localhost', DEFAULT_PORT) == 'http://localhost:8000'
    with pytest.raises(ValueError): access_url('localhost', 0)


def test_network_filters_virtual_and_down(monkeypatch):
    psutil = pytest.importorskip('psutil')
    address = lambda ip: SimpleNamespace(family=socket.AF_INET, address=ip)
    monkeypatch.setattr(psutil, 'net_if_addrs', lambda: {
        'Wi-Fi': [address('192.168.1.5')], 'Ethernet': [address('10.1.1.5')],
        'Docker': [address('172.17.0.1')], 'VPN': [address('10.2.2.1')],
        'Loopback': [address('127.0.0.1')], 'disconnected': [address('192.168.2.5')]})
    monkeypatch.setattr(psutil, 'net_if_stats', lambda: {name: SimpleNamespace(isup=name != 'disconnected')
        for name in ('Wi-Fi','Ethernet','Docker','VPN','Loopback','disconnected')})
    probe = Mock()
    probe.getsockname.return_value = ('192.168.1.5', 0)
    context = Mock()
    context.__enter__ = Mock(return_value=probe)
    context.__exit__ = Mock(return_value=None)
    monkeypatch.setattr(socket, 'socket', lambda *args: context)
    assert lan_addresses() == [('Wi-Fi', '192.168.1.5'), ('Ethernet', '10.1.1.5')]
    assert probe.connect.call_args.args[0] == ('192.168.1.5', 9)
    probe.send.assert_not_called()


def test_network_failure_preserves_localhost(monkeypatch):
    psutil = pytest.importorskip('psutil')
    monkeypatch.setattr(psutil, 'net_if_stats', Mock(side_effect=OSError()))
    assert lan_addresses() == []


def test_user_paths_and_resources(tmp_path, monkeypatch):
    paths = application_paths({'LOCALAPPDATA': str(tmp_path)})
    paths.prepare()
    assert paths.config == tmp_path / 'corrigiAi/config/settings.dpapi'
    assert paths.logs.is_dir() and paths.work.is_dir()
    with pytest.raises(ValueError): application_paths({})
    assert resource_path('app','omr','reference.png').is_file()
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert resource_path('ocr-models') == tmp_path / 'ocr-models'
    assert paths.models == tmp_path / 'ocr-models'


def test_new_configuration_hashes_password():
    config = new_config('postgresql+psycopg://user:password@host/db', 'admin', 'test-password')
    assert check_password_hash(config['ADMIN_PASSWORD_HASH'], 'test-password')
    assert 'test-password' not in json.dumps(config)
    assert len(config['SECRET_KEY']) >= 32
    assert set(config) == {'SQLALCHEMY_DATABASE_URI','ADMIN_USERNAME','ADMIN_PASSWORD_HASH','SECRET_KEY'}


@pytest.mark.parametrize('url', ['sqlite:///file.db','broken','postgresql://host/db','postgresql://user@host/db'])
def test_bad_configuration(url):
    with pytest.raises(ConfigurationError): new_config(url,'admin','test-password')


def test_dpapi_roundtrip_and_no_cleartext(tmp_path, monkeypatch):
    config = new_config('postgresql://user:secret@host/db', 'admin', 'test-password')
    # A test double verifies API usage; real DPAPI is checked on clean Windows.
    api = SimpleNamespace(CryptProtectData=Mock(return_value=b'windows-encrypted'),
        CryptUnprotectData=Mock(return_value=('corrigiAi', json.dumps(config).encode())))
    monkeypatch.setitem(sys.modules, 'win32crypt', api)
    path = tmp_path / 'settings.dpapi'
    save_config(path, config)
    assert path.read_bytes() == b'windows-encrypted'
    assert load_config(path) == config
    assert api.CryptProtectData.call_args.args[-1] == 1  # UI forbidden; user scope
    api.CryptUnprotectData.side_effect = RuntimeError('secret')
    with pytest.raises(ConfigurationError, match='usuário'): load_config(path)


def test_safe_logs_never_include_driver_exception():
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(SafeFormatter())
    logger = logging.getLogger('desktop')
    logger.addHandler(handler)
    try:
        log_failure('db_failed', RuntimeError('postgresql://user:secret@host/db CPF 12345678909'))
        third_party = logging.LogRecord('sqlalchemy.engine', logging.ERROR, '', 1, 'password=secret', (), None)
        handler.handle(third_party)
    finally: logger.removeHandler(handler)
    assert 'RuntimeError' in output.getvalue()
    assert 'secret' not in output.getvalue() and '12345678909' not in output.getvalue()


def test_database_initialization_only_owns_three_tables(tmp_path):
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI':'sqlite://',
        'SECRET_KEY':'test-secret', 'ADMIN_PASSWORD_HASH':'pbkdf2:sha256:1$salt$hash',
        'WORK_DIR': str(tmp_path / 'work')})
    with app.app_context():
        initialize_database()
        initialize_database()
        assert set(inspect(db.engine).get_table_names()) == {'exam','answer_key','correction'}


@pytest.mark.parametrize('exists,columns,message', [(False, [], 'não foi encontrada'),
    (True, [{'name':'cpf'}], 'não é compatível')])
def test_database_preflight_never_initializes_bad_external_schema(monkeypatch, exists, columns, message):
    import desktop.database as module
    application = Mock()
    application.app_context.return_value.__enter__ = Mock()
    application.app_context.return_value.__exit__ = Mock(return_value=False)
    connection = Mock()
    engine = Mock()
    engine.connect.return_value.__enter__ = Mock(return_value=connection)
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(module, 'db', SimpleNamespace(engine=engine))
    inspector = Mock()
    inspector.has_table.return_value = exists
    inspector.get_columns.return_value = columns
    monkeypatch.setattr(module, 'inspect', lambda conn: inspector)
    initializer = Mock()
    monkeypatch.setattr(module, 'initialize_database', initializer)
    with pytest.raises(DatabaseSetupError, match=message): prepare_database(application)
    initializer.assert_not_called()
    inspector.has_table.assert_called_once_with('participants', schema='public')


def test_waitress_lifecycle_without_socket(monkeypatch):
    waitress = pytest.importorskip('waitress')
    import desktop.server as module
    monkeypatch.setattr(module, 'check_port', Mock())
    app = Mock()
    waitress_server = Mock()
    waitress_server.task_dispatcher.threads = set()
    create = Mock(return_value=waitress_server)
    monkeypatch.setattr(waitress, 'create_server', create)
    server = LocalServer(app)
    server.start()
    server.thread.join()
    server.stop()
    assert create.call_args.kwargs['host'] == '0.0.0.0'
    assert create.call_args.kwargs['port'] == DEFAULT_PORT
    waitress_server.task_dispatcher.shutdown.assert_called_once()
    assert not server.thread.is_alive()


def test_port_busy_is_friendly_without_killing_process(monkeypatch):
    import errno
    probe = Mock()
    probe.bind.side_effect = OSError(errno.EADDRINUSE, 'occupied')
    context = Mock()
    context.__enter__ = Mock(return_value=probe)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(socket, 'socket', lambda *args: context)
    with pytest.raises(PortInUseError, match='já está em uso'): check_port()
    probe.bind.assert_called_once_with(('0.0.0.0', DEFAULT_PORT))


def test_desktop_paths_override_environment_without_dotenv(tmp_path, monkeypatch):
    # No GUI import is needed to construct the application.
    from desktop.application import desktop_app
    from app.services.cpf_detector import get_digit_recognizer
    monkeypatch.setenv('WORK_DIR', '/wrong')
    monkeypatch.setenv('OCR_MODEL_DIR', '/wrong')
    monkeypatch.setenv('DEBUG_OMR', 'true')
    monkeypatch.setattr('app.load_dotenv', Mock(side_effect=AssertionError('desktop read .env')))
    config = new_config('postgresql+psycopg://user:password@localhost/db', 'admin', 'test-password')
    paths = application_paths({'LOCALAPPDATA': str(tmp_path)})
    monkeypatch.setattr(type(paths), 'models', property(lambda self: tmp_path / 'bundled-models'))
    paths.prepare()
    from sqlalchemy import create_engine
    # Replace only the test engine factory: no PostgreSQL driver or connection needed.
    monkeypatch.setattr(db, '_make_engine', lambda *args: create_engine('sqlite://'))
    application = desktop_app(config, paths)
    assert application.instance_path == str(paths.root)
    assert application.config['WORK_DIR'] == str(paths.work)
    assert application.config['OCR_MODEL_DIR'] == str(paths.models)
    assert not application.debug and not application.config['DEBUG_OMR']
    recognizer = get_digit_recognizer(application)
    assert recognizer.user_network_directory == str(paths.root / 'ocr-user-network')
    assert application.test_client().get('/health').status_code == 200
    with application.app_context(): db.engine.dispose()


def test_payload_inventory_and_secrets_rejected(tmp_path):
    import xml.etree.ElementTree as ET
    from scripts.windows_payload import generate_payload
    root = tmp_path / 'dist'
    for relative in ('corrigiAi.exe', '_internal/app/templates/base.html', '_internal/app/static/js/app.js',
                     '_internal/app/omr/reference.png', '_internal/app/omr/templates/opi_fundamental_2026.json',
                     '_internal/ocr-models/english_g2.pth'):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'test fixture')
    output = tmp_path / 'Payload.wxs'
    generate_payload(root, output)
    ns = {'w': 'http://wixtoolset.org/schemas/v4/wxs'}
    files = ET.parse(output).findall('.//w:File', ns)
    assert len(files) == 5  # EXE is defined by Package.wxs, not duplicated
    (root / '.env').write_text('private')
    with pytest.raises(ValueError, match='não permitido'): generate_payload(root, output)


@pytest.mark.parametrize('state,detail,expected', [
    ('28P01', 'sensitive password', 'recusou as credenciais'),
    (None, 'password authentication failed for user private', 'recusou as credenciais'),
    (None, 'Tenant or user not found', 'não reconheceu'),
    ('42501', 'sensitive statement', 'permissões necessárias'),
    ('3D000', 'sensitive database name', 'não existe'),
    (None, 'could not translate host name private-host', 'localizar o servidor'),
    (None, 'SSL certificate verify failed private-host', 'conexão SSL'),
    (None, 'connection timed out private-host', 'não respondeu'),
    (None, 'unexpected sensitive detail', 'Não foi possível acessar'),
])
def test_database_failure_messages_never_reveal_driver_details(state, detail, expected):
    from desktop.database import database_failure
    from sqlalchemy.exc import OperationalError
    driver = RuntimeError(detail + ' postgresql://user:private-password@private-host/db')
    driver.sqlstate = state
    reason, message = database_failure(OperationalError('SELECT private', {}, driver), 'connect')
    assert expected in message
    assert 'private-password' not in message and 'private-host' not in message
    assert 'SELECT private' not in message
    assert reason in ('authentication', 'pooler_identity', 'permissions', 'database_name', 'dns', 'ssl', 'network', 'unknown')


def test_database_initialization_error_distinguished_from_connection_error():
    from desktop.database import database_failure
    reason, message = database_failure(RuntimeError('permission denied'), 'initialize')
    assert reason == 'permissions'
    assert 'A conexão foi estabelecida' in message
