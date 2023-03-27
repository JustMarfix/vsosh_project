from flask import Flask, render_template, redirect, url_for, flash, make_response, session, Request, request
from flask_limiter import Limiter, RateLimitExceeded
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from time import time
from services import mailer

import mariadb
import hashlib

import uuid

conn = mariadb.connect(
    host='host', # mariadb server ip/domain
    port=3306, # mariadb server port
    user='user', # mariadb server user
    password='password', # mariadb user password
    database='db_name' # mariadb database
)
cursor = conn.cursor()

app = Flask(__name__, template_folder="templates", static_folder="static")

app.secret_key = b's3cret' # secret key for cookie signing
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

def get_username():
    if 'j_username' not in request.form:
        return get_remote_address()
    else:
        return request.form["j_username"]

limiter = Limiter(key_func=get_username, app=app, default_limits=["100000/day"])

@app.route('/')
def index():
    return render_template('index.html')
app.add_url_rule('/index.html', view_func=index)
app.add_url_rule('/index.php', view_func=index)
app.add_url_rule('/index/', view_func=index)

@app.route('/menu')
def menu():
    if 'username' not in session:
        return render_template('index.html', error="Вы не вошли в систему.")
    cookie = session['is_admin']
    return render_template('menu.html', cookie=cookie)
app.add_url_rule('/menu.html', view_func=menu)
app.add_url_rule('/menu.php', view_func=menu)
app.add_url_rule('/menu/', view_func=menu)

@app.route('/j_security_check', methods=['POST'])
@limiter.limit("10/5minutes")
def login():
    login = request.form['j_username']
    if '\'' in login or 'SELECT' in login or '--' in login or ';' in login:
        return render_template('index.html', error="Указан неверный логин или пароль. Попробуйте ещё раз.")
    password = hashlib.sha256(request.form["j_password"].encode(encoding = 'UTF-8', errors = 'strict')).hexdigest()
    cursor.execute(f"SELECT login, is_admin FROM users WHERE login = '{login}' AND password = '{password}'")
    user = cursor.fetchone()
    if not user:
        return render_template('index.html', error="Указан неверный логин или пароль. Попробуйте ещё раз.")
    session['username'] = user[0]
    session['is_admin'] = user[1]
    return redirect(url_for('menu'))
app.add_url_rule('/j_security_check.html', view_func=login)
app.add_url_rule('/j_security_check.php', view_func=login)
app.add_url_rule('/j_security_check/', view_func=login)

@app.route('/registration', methods=['GET', 'POST'])
def register():
    if 'is_admin' not in session or session['is_admin'] == 0:
        return render_template('index.html', error="Вы не вошли в систему, или вошли с недостаточными правами.")
    elif request.method == 'GET':
        return render_template('register.html')
    elif request.method == 'POST':
        cursor.execute(f'''SELECT id FROM users WHERE login = "{request.form['j_username']}"''')
        in_base = cursor.fetchone()
        if in_base:
            return render_template('register.html', error='Пользователь с таким именем уже существует.')
        if request.form["j_password"] != request.form["second_password"]:
            return render_template('register.html', error='Пароли не совпадают.')
        login = request.form['j_username']
        psw = hashlib.sha256(request.form["j_password"].encode(encoding = 'UTF-8', errors = 'strict')).hexdigest()
        email = request.form['email']
        cursor.execute('SELECT count(*) FROM users')
        id = cursor.fetchone()[0]
        cursor.execute(f"INSERT INTO `users` (`id`, `login`, `password`, `email`, `is_admin`) VALUES ('{id}', '{login}', '{psw}', '{email}', '0'); ")
        conn.commit()
        return render_template('register.html', info='Пользователь успешно зарегистрирован!')
app.add_url_rule('/registration.html', view_func=register)
app.add_url_rule('/registration.php', view_func=register)
app.add_url_rule('/registration/', view_func=register)

@app.route('/restore-password', methods=['GET', 'POST'])
def restore_password():
    if 'info' in request.args:
        return render_template('restore-password.html', info=request.args['info'])
    if request.method == 'GET':
        return render_template('restore-password.html')
    elif request.method == 'POST':
        cursor.execute(f'''SELECT login, email FROM users WHERE email = "{request.form['email']}"''')
        user = cursor.fetchone()
        if not user:
            return render_template('restore-password.html', info='Если такая почта привязана к пользователю, мы отправили письмо на неё.')
        cursor.execute(f'SELECT valid_until FROM tokens WHERE username = "{user[0]}"')
        in_base = cursor.fetchone()
        if in_base and in_base[0] > int(time()):
            return render_template('restore-password.html', info='Если такая почта привязана к пользователю, мы отправили письмо на неё.')
        token = uuid.uuid4()
        valid = int(time())+900
        cursor.execute(f'''INSERT INTO tokens (token, valid_until, username) VALUES ("{token}", "{valid}", "{user[0]}")''')
        conn.commit()
        mailer.send_email(user[0], user[1], token)
        return render_template('restore-password.html', info='Если такая почта привязана к пользователю, мы отправили письмо на неё.')
app.add_url_rule('/restore-password/', view_func=restore_password)

@app.route('/restore-password/<token>', methods=['GET', 'POST'])
def restore_by_token(token):
    cursor.execute(f'SELECT username, valid_until FROM tokens WHERE token = "{token}"')
    in_base = cursor.fetchone()
    if not in_base or in_base[1] < int(time()):
        return render_template('restore-password.html', error='Такого токена не существует, или он истёк!')
    else:
        if request.method == 'GET':
            return render_template('new-password.html', token=token)
        elif request.method == 'POST':
            username = in_base[0]
            password = request.form["password"]
            double_password = request.form["double_password"]
            if password != double_password:
                return render_template('new-password.html', error='Пароли не совпадают!')
            cursor.execute(f'''UPDATE users SET password = "{hashlib.sha256(password.encode(encoding = 'UTF-8', errors = 'strict')).hexdigest()}" WHERE login = "{username}"''')
            conn.commit()
            cursor.execute(f'''DELETE FROM tokens WHERE token = "{token}"''')
            conn.commit()
            return redirect(url_for('restore_password', info='Вы успешно сменили пароль!'))
    

@app.route('/logout')
def logout():
    if 'username' not in session:
        return render_template('index.html', error="Вы не вошли в систему.")
    session.pop('username')
    session.pop('is_admin')
    return render_template('index.html', info="Вы успешно вышли.")
app.add_url_rule('/logout.html', view_func=logout)
app.add_url_rule('/logout.php', view_func=logout)
app.add_url_rule('/logout', view_func=logout)

@app.errorhandler(RateLimitExceeded)
def handler(response):
    return render_template('index.html', error="Указан неверный логин или пароль. Попробуйте ещё раз.")
