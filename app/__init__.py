import logging
import os
import secrets
import shutil
import time
from datetime import timedelta
from pathlib import Path
import click
from dotenv import load_dotenv
from flask import Flask, session, request, abort, render_template, flash
from .models import db, Exam
from .services.cpf_validator import mask_cpf
from .services.cpf_detector import EasyOCRDigitRecognizer
from .services.integrations.student_provider import MockStudentProvider
from .services.integrations.result_integration import NoOpResultIntegration


def create_app(test_config=None):
    load_dotenv()
    app=Flask(__name__,instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        ADMIN_USERNAME=os.getenv('ADMIN_USERNAME','admin'),
        ADMIN_PASSWORD_HASH=os.getenv('ADMIN_PASSWORD_HASH',''),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={'hide_parameters':True},
        MAX_CONTENT_LENGTH=12*1024*1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        DEBUG_OMR=os.getenv('DEBUG_OMR','false').lower()=='true',
        WORK_DIR=str(Path(app.instance_path)/'work'),
        OCR_MODEL_DIR=str(Path(app.instance_path)/'ocr-models')
    )
    if test_config: app.config.update(test_config)
    if not app.config['SECRET_KEY'] or app.config['SECRET_KEY']=='change-me':
        raise RuntimeError('Configure SECRET_KEY aleatória no .env antes de iniciar.')
    if not app.config['ADMIN_PASSWORD_HASH'].startswith(('scrypt:','pbkdf2:')):
        raise RuntimeError('Configure ADMIN_PASSWORD_HASH com um hash Werkzeug no .env.')
    Path(app.instance_path).mkdir(exist_ok=True)
    Path(app.config['WORK_DIR']).mkdir(parents=True,exist_ok=True,mode=0o700)
    db.init_app(app)
    app.extensions['digit_recognizer']=EasyOCRDigitRecognizer(app.config['OCR_MODEL_DIR'])
    app.extensions['student_provider']=MockStudentProvider()
    app.extensions['result_integration']=NoOpResultIntegration()
    logging.basicConfig(level=logging.INFO)
    from .routes.auth import bp as auth
    from .routes.main import bp as main
    from .routes.answer_key import bp as keys
    from .routes.correction import bp as correction
    for bp in (auth,main,keys,correction): app.register_blueprint(bp)
    app.jinja_env.filters['mask_cpf']=mask_cpf
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
    def too_large(error): return render_template('error.html',message='Arquivo grande demais. Envie uma foto de até 12 MB.'),413
    @app.errorhandler(400)
    @app.errorhandler(404)
    def client_error(error): return render_template('error.html',message=error.description),error.code
    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template('error.html',message='Não foi possível concluir. Tente novamente; se persistir, contate a organização.'),500
    @app.cli.command('init-db')
    def init_db():
        db.create_all()
        click.echo('SQLite inicializado. Cadastre uma prova em Gabaritos.')
    @app.cli.command('cleanup-temp')
    def cleanup_command():
        cleanup_work(app)
        click.echo('Temporários expirados removidos.')
    return app


def cleanup_work(app):
    for path in Path(app.config['WORK_DIR']).iterdir():
        if path.is_dir() and time.time()-path.stat().st_mtime>3600:
            shutil.rmtree(path,ignore_errors=True)
