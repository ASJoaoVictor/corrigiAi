"""Isolated browser smoke test. Run with: python scripts/check_mobile.py.
Development dependencies: playwright; uses locally installed Google Chrome.
"""
import io
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
from app import create_app
from app.models import db,Exam,AnswerKey

with tempfile.TemporaryDirectory(prefix='opi-browser-') as directory:
    app=create_app(dict(TESTING=True,SECRET_KEY='browser-test-only',ADMIN_PASSWORD_HASH=generate_password_hash('browser-test-password'),SQLALCHEMY_DATABASE_URI='sqlite:///'+directory+'/test.sqlite',WORK_DIR=directory+'/work',DEBUG_OMR=False))
    with app.app_context():
        db.create_all();e=Exam(name='OPI Fundamental 2026');db.session.add(e);db.session.flush();db.session.add(AnswerKey(exam_id=e.id,answers_json={str(i):'A' for i in range(1,31)}));db.session.commit()
    server=make_server('127.0.0.1',5087,app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
            for width,height in [(360,800),(390,844),(412,915)]:
                context=browser.new_context(viewport={'width':width,'height':height},is_mobile=True,has_touch=True)
                page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                def check(name):
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'Overflow: {name} {width}'
                    assert not errors,errors
                page.goto('http://127.0.0.1:5087/login');check('login')
                page.get_by_label('Usuário').fill('admin');page.get_by_label('Senha',exact=True).fill('browser-test-password');page.get_by_role('button',name='Entrar').click();check('home')
                page.get_by_role('link',name='Tirar foto de cartão',exact=True).click();check('capture')
                page.locator('#photo').set_input_files('app/omr/reference.png')
                page.get_by_role('button',name='Conferir foto').click();check('preview')
                page.get_by_role('button',name='Usar foto e processar cartão').click();page.wait_for_url('**/review');check('review')
                page.locator('#cpf').fill('12345678909')
                row=page.locator('fieldset').first
                row.locator('input[value=A]').check();assert page.locator('#score').inner_text()=='1 / 30 acertos'
                assert 'Correção manual' in row.inner_text()
                page.screenshot(path=f'docs/mobile-{width}.png',full_page=False)
                page.get_by_role('button',name='Revisar confirmação').click();page.wait_for_url('**/confirm');check('confirmation')
                assert '12345678909' not in page.inner_text('body')
                if page.locator('input[name=ack_duplicate]').count():page.locator('input[name=ack_duplicate]').check()
                page.get_by_role('button',name='Confirmar correção',exact=True).click();page.wait_for_url('**/history/*');check('detail')
                page.get_by_role('link',name='Histórico',exact=True).click();check('history')
                page.get_by_role('link',name='Gabaritos',exact=True).click();check('keys')
                page.get_by_role('link',name='Editar gabarito').click();check('key editor')
                print(f'OK: {width}x{height}, mobile workflow and live score',flush=True)
                context.close()
            browser.close()
    finally:server.shutdown()
