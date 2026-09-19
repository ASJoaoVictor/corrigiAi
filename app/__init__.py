import logging
import os
import secrets
import shutil
import time
import threading
from datetime import timedelta
from pathlib import Path
import click
from dotenv import load_dotenv
from flask import Flask, session, request, abort, render_template, flash
from .models import db, Exam
from .services.cpf_validator import mask_cpf
from sqlalchemy.exc import OperationalError, ProgrammingError
from .services.integrations.student_provider import MockStudentProvider
from .services.integrations.result_integration import NoOpResultIntegration


def create_app(test_config=None):
    load_dotenv()
    app=Flask(__name__,instance_relative_config=True)
    is_vercel = bool(os.getenv('VERCEL'))
    base_dir = Path('/tmp') if is_vercel else Path(app.instance_path)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        if is_vercel and not (test_config or {}).get('SQLALCHEMY_DATABASE_URI'):
            raise RuntimeError('Configure DATABASE_URL na Vercel; para teste temporário use sqlite:////tmp/database.db.')
        database_url = f"sqlite:///{Path(app.instance_path) / 'database.db'}"
    app.config.from_mapping(
        DEBUG=False,
        SECRET_KEY=os.getenv('SECRET_KEY'),
        ADMIN_USERNAME=os.getenv('ADMIN_USERNAME','admin'),
        ADMIN_PASSWORD_HASH=os.getenv('ADMIN_PASSWORD_HASH',''),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={'hide_parameters':True},
        MAX_CONTENT_LENGTH=4*1024*1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        DEBUG_OMR=os.getenv('DEBUG_OMR','false').lower()=='true',
        WORK_DIR=os.getenv('WORK_DIR') or str(base_dir/'work'),
        OCR_MODEL_DIR=os.getenv('OCR_MODEL_DIR') or str(base_dir/'ocr-models')
    )
    if test_config: app.config.update(test_config)
    if not app.config['SECRET_KEY'] or app.config['SECRET_KEY']=='change-me':
        raise RuntimeError('Configure SECRET_KEY aleatória no .env antes de iniciar.')
    if not app.config['ADMIN_PASSWORD_HASH'].startswith(('scrypt:','pbkdf2:')):
        raise RuntimeError('Configure ADMIN_PASSWORD_HASH com um hash Werkzeug no .env.')
    if not is_vercel:
        Path(app.instance_path).mkdir(parents=True,exist_ok=True)
    Path(app.config['WORK_DIR']).mkdir(parents=True,exist_ok=True,mode=0o700)
    Path(app.config['OCR_MODEL_DIR']).mkdir(parents=True,exist_ok=True)
    db.init_app(app)
    app.extensions['digit_recognizer']=None
    app.extensions['digit_recognizer_lock']=threading.Lock()
    app.extensions['student_provider']=MockStudentProvider()
    app.extensions['result_integration']=NoOpResultIntegration()
    logging.basicConfig(level=logging.INFO)
    from .routes.auth import bp as auth
    from .routes.main import bp as main
    from .routes.answer_key import bp as keys
    from .routes.correction import bp as correction
    for bp in (auth,main,keys,correction): app.register_blueprint(bp)
    app.jinja_env.filters['mask_cpf']=mask_cpf
    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.context_processor
    def csrf_context():
        if 'csrf_token' not in session: session['csrf_token']=secrets.token_hex(32)
        return dict(csrf_token=session['csrf_token'])
    @app.before_request
    def security():
        if request.method=='POST' and (not session.get('csrf_token') or not secrets.compare_digest(session['csrf_token'].encode(),request.form.get('csrf_token','').encode())):
            abort(400,description='Sessão expirada. Atualize a página e tente novamente.')
        cleanup_work(app)
    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response
    @app.errorhandler(413)
    def too_large(error): return render_template('error.html',message='Arquivo grande demais. Envie uma foto menor que 4 MB.'),413
    @app.errorhandler(400)
    @app.errorhandler(404)
    def client_error(error): return render_template('error.html',message=error.description),error.code
    @app.errorhandler(OperationalError)
    @app.errorhandler(ProgrammingError)
    def database_error(error):
        db.session.rollback()
        return render_template('error.html',message='Banco de dados indisponível. Verifique DATABASE_URL e inicialize as tabelas com flask --app index init-db.'),503
    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template('error.html',message='Não foi possível concluir. Tente novamente; se persistir, contate a organização.'),500
    @app.cli.command('init-db')
    def init_db():
        db.create_all()
        click.echo('Banco de dados inicializado. Cadastre uma prova em Gabaritos.')
    @app.cli.command('cleanup-temp')
    def cleanup_command():
        cleanup_work(app)
        click.echo('Temporários expirados removidos.')
    return app


def cleanup_work(app):
    work_dir = Path(app.config['WORK_DIR'])
    try:
        for path in work_dir.iterdir():
            try:
                if time.time()-path.stat().st_mtime > 3600:
                    if path.is_dir():
                        shutil.rmtree(path,ignore_errors=True)
                    else:
                        path.unlink(missing_ok=True)
            except OSError:
                continue
    except OSError:
        # Temporary directories may disappear between requests.
        return
