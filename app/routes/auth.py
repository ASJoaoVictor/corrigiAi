from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template, current_app, flash
from werkzeug.security import check_password_hash
bp=Blueprint('auth',__name__)

def login_required(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        if not session.get('authenticated'): return redirect(url_for('auth.login'))
        return view(*args,**kwargs)
    return wrapped

@bp.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        valid=check_password_hash(current_app.config['ADMIN_PASSWORD_HASH'],request.form.get('password',''))
        if request.form.get('username')==current_app.config['ADMIN_USERNAME'] and valid:
            session.clear();session['authenticated']=True;session.permanent=True
            return redirect(url_for('main.index'))
        flash('Usuário ou senha incorretos.','error')
    return render_template('login.html')

@bp.post('/logout')
@login_required
def logout():
    from .correction import discard_work
    discard_work();session.clear()
    return redirect(url_for('auth.login'))
