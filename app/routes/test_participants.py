"""Local test data entry, registered exclusively by the SQLite test edition."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from sqlalchemy import MetaData, Table, select
from app.models import db
from app.services.cpf_validator import validate_cpf, format_cpf
from .auth import login_required

bp = Blueprint('test_participants', __name__)


@bp.route('/test-participants', methods=['GET', 'POST'])
@login_required
def index():
    if db.engine.dialect.name != 'sqlite': abort(404)
    table = Table('participants', MetaData(), autoload_with=db.engine)
    if request.method == 'POST':
        cpf = request.form.get('cpf', '')
        if not validate_cpf(cpf):
            flash('Informe um CPF fictício com dígitos verificadores válidos.', 'error')
        else:
            formatted = format_cpf(cpf)
            if db.session.execute(select(table.c.cpf).where(table.c.cpf == formatted)).first():
                flash('Este CPF já está cadastrado para testes.', 'error')
            else:
                db.session.execute(table.insert().values(cpf=formatted, grade=None))
                db.session.commit()
                flash('CPF de teste cadastrado.', 'success')
                return redirect(url_for('test_participants.index'))
    return render_template('test_participants.html')
