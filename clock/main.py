from flask import Flask, render_template, request, redirect, url_for
from api.timer import timer_api
import pymysql
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash
from pymysql import err as pymysql_err

# 2. PythonAnywhere 固定パス（存在すればこちらを優先）
pa_env_path = Path("/home/TickStackM5/RWC25-group06/.env")

# 3. 実際に存在する .env を選んで読み込む
env_path = pa_env_path if pa_env_path.exists() else Path.cwd() / ".env"

load_dotenv(env_path)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config["JSON_AS_ASCII"] = False
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.register_blueprint(timer_api)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


class User(UserMixin):
    def __init__(self, user_id, username, display_name):
        self.id = str(user_id)
        self.username = username
        self.display_name = display_name or username


def _build_user(row):
    if not row:
        return None
    return User(row["id"], row["username"], row.get("display_name"))


def fetch_user_by_id(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, display_name, password_hash FROM users WHERE id = %s",
                (user_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def fetch_user_by_username(username):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, display_name, password_hash FROM users WHERE username = %s",
                (username,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


@login_manager.user_loader
def load_user(user_id):
    row = fetch_user_by_id(user_id)
    return _build_user(row)

def get_db_connection():
    """共通のDB接続を返す"""
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip() or username
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password:
            error = "ユーザー名とパスワードを入力してください"
        elif password != confirm_password:
            error = "パスワードが一致しません"
        else:
            password_hash = generate_password_hash(password)
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (username, display_name, password_hash)
                        VALUES (%s, %s, %s)
                        """,
                        (username, display_name, password_hash),
                    )
                    conn.commit()
                    user_id = cursor.lastrowid
                user = User(user_id, username, display_name)
                login_user(user)
                return redirect(url_for("index"))
            except pymysql_err.IntegrityError:
                error = "そのユーザー名は既に使われています"
            finally:
                conn.close()

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = fetch_user_by_username(username)
        user = _build_user(row)
        if user and check_password_hash(row["password_hash"], password):
            login_user(user)
            next_url = request.args.get("next")
            return redirect(next_url or url_for("index"))
        else:
            error = "ユーザー名またはパスワードが違います"

    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# index.htmlを開く関数
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/submit_uid', methods=['POST'])
@login_required
def submit_uid():
    uid = request.form.get('UID', '').strip()
    if not uid:
        return redirect(url_for('index'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET device_uid = %s WHERE id = %s",
                (uid, int(current_user.id))
            )
            conn.commit()
    except pymysql_err.IntegrityError:
        conn.rollback()
        return "その UID は既に使われています", 400
    finally:
        conn.close()

    return redirect(url_for('index'))

# todo.htmlでタスクリストを表示
@app.route('/todo')
@login_required
def open_todo():
    user_id = int(current_user.id)
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM todos WHERE user_id = %s AND is_done = FALSE ORDER BY created_at DESC",
            (user_id,),
        )
        tasks_list = cursor.fetchall()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM todos WHERE user_id = %s AND is_done = TRUE ORDER BY created_at DESC",
            (user_id,),
        )
        completed_list = cursor.fetchall()
    conn.close()
    return render_template('todo.html', tasks_list=tasks_list, completed_list=completed_list)

@app.route('/todo/category/<int:category_id>')
@login_required
def open_todo_by_category(category_id):
    user_id = int(current_user.id)
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM todos
            WHERE user_id = %s AND is_done = FALSE AND category = %s
            ORDER BY created_at DESC
            """,
            (user_id, category_id),
        )
        tasks_list = cursor.fetchall()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM todos
            WHERE user_id = %s AND is_done = TRUE AND category = %s
            ORDER BY created_at DESC
            """,
            (user_id, category_id),
        )
        completed_list = cursor.fetchall()
    conn.close()
    return render_template('todo.html', tasks_list=tasks_list, completed_list=completed_list, category_id=category_id)

# @app.route('/set_todo', methods=['POST'])
# def set_todo():
#     add_task = request.form['add_task']
#     date_str = request.form['task_date']
#     try:
#         date_obj = datetime.strptime(date_str, '%Y-%m-%d')
#     except ValueError:
#         return "日付の形式が不正です", 400
#     formatted_date = date_obj.strftime('%Y-%m-%d')
#     conn = get_db_connection()
#     with conn.cursor() as cursor:
#         cursor.execute("INSERT INTO todos (title, due_date) VALUES (%s, %s)", (add_task, formatted_date))
#         conn.commit()
#     conn.close()
#     return redirect(url_for('open_todo'))

@app.route('/set_todo', methods=['POST'])
@login_required
def set_todo():
    add_task = request.form['add_task']
    date_str = request.form['task_date']
    category = int(request.form['category'])  # ←カテゴリを取得

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return "日付の形式が不正です", 400
    formatted_date = date_obj.strftime('%Y-%m-%d')

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO todos (user_id, title, due_date, category) VALUES (%s, %s, %s, %s)",
            (int(current_user.id), add_task, formatted_date, category)
        )
        conn.commit()
    conn.close()
    return redirect(url_for('open_todo'))

@app.route('/todo/<int:todo_id>/status', methods=['POST'])
@login_required
def update_todo_status(todo_id):
    requested_status = request.form.get('is_done')
    if requested_status not in {'true', 'false'}:
        return "不正な完了状態です", 400

    is_done = (requested_status == 'true')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE todos SET is_done = %s WHERE id = %s AND user_id = %s",
                (is_done, todo_id, int(current_user.id))
            )
            conn.commit()
    finally:
        conn.close()

    return redirect(url_for('open_todo'))

@app.route('/todo/<int:todo_id>/delete', methods=['POST'])
@login_required
def delete_todo(todo_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM todos WHERE id = %s AND user_id = %s",
            (todo_id, int(current_user.id))
        )
        conn.commit()
    conn.close()
    return redirect(url_for('open_todo'))

# timer_db内のデータを取得して表示する関数
@app.route("/time")
@login_required
def open_time():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM pomo_settings WHERE user_id = %s ORDER BY created_at DESC",
            (int(current_user.id),)
        )
        settings_list = cursor.fetchall()
    conn.close()
    return render_template("time.html", settings_list=settings_list)

# time.htmlで設定されたwork_timeとbreak_timeをtimer_dbに保存する関数
@app.route("/set_timer", methods=["POST"])
@login_required
def set_timer():
    work_time = int(request.form["work_time"])
    break_time = int(request.form["break_time"])

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO pomo_settings (user_id, work_time, break_time) VALUES (%s, %s, %s)",
            (int(current_user.id), work_time, break_time)
        )
        conn.commit()
    conn.close()
    return redirect(url_for("open_time"))

# 表示しておいたwork_timeとbreak_timeが選択された時current_timer_settingsに保存する関数（未完成）
@app.route('/select_timer/<int:setting_id>')
@login_required
def select_timer(setting_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pomo_settings
                SET selected_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (setting_id, int(current_user.id))
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"[select_timer] タイマー更新中にエラー: {exc}")
    finally:
        conn.close()

    return redirect(url_for('open_time'))

# time.htmlで選択されたタイマー設定を削除する関数
@app.route("/delete_timer", methods=["POST"])
@login_required
def delete_timer():
    ids = [int(i) for i in request.form.getlist("delete_ids") if i.isdigit()]
    if ids:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            format_strings = ','.join(['%s'] * len(ids))
            params = [int(current_user.id)] + ids
            cursor.execute(
                f"DELETE FROM pomo_settings WHERE user_id = %s AND id IN ({format_strings})",
                tuple(params)
            )
            conn.commit()
        conn.close()
    return redirect(url_for("open_time"))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
