import sys
import os
import json
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import Blueprint, Response, request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# PythonAnywhere 上の固定パスを優先し、なければカレントの .env を読む
pa_env_path = Path("/home/TickStackM5/RWC25-group06/.env")
env_path = pa_env_path if pa_env_path.exists() else Path.cwd() / ".env"
load_dotenv(env_path)

timer_api = Blueprint("timer_api", __name__)
DEFAULT_WORK_TIME = 1500
DEFAULT_BREAK_TIME = 300
DEFAULT_TODO_TITLE = "Congraturations!"
DEFAULT_TODO_DUEDATE = ""


def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def json_response(payload, status=200):
    return Response(
        json.dumps(payload, ensure_ascii=False, default=str),
        status=status,
        mimetype="application/json; charset=utf-8",
    )


def resolve_user_id(uid: str):
    if not uid:
        return None

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE device_uid = %s LIMIT 1",
                (uid,),
            )
            row = cursor.fetchone()
            if row:
                return int(row["id"])
    except Exception as exc:
        print(f"[timer_api] uid resolve failed: {exc}")
    finally:
        if conn:
            conn.close()
    return None


def parse_uid_and_task_id():
    uid = request.args.get("uid", "").strip()
    task_id = request.args.get("id", "").strip()
    if not task_id and uid and "id=" in uid:
        uid_part, _, id_part = uid.partition("id=")
        uid = uid_part
        task_id = id_part
    if task_id and "&" in task_id:
        task_id = task_id.split("&", 1)[0]
    return uid, task_id


def default_todo_payload():
    return {
        "0": {
            "id": -1,
            "title": DEFAULT_TODO_TITLE,
            "duedate": DEFAULT_TODO_DUEDATE,
        }
    }


def fetch_latest_timer_setting(user_id: int):
    conn = None
    print("[timer_api] DBからタイマー設定を取得開始", flush=True)
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT work_time, break_time
                FROM pomo_settings
                WHERE user_id = %s
                ORDER BY selected_at DESC
                LIMIT 1
                """
                ,
                (user_id,)
            )
            return cursor.fetchone()
    except Exception as exc:
        # APIの返却自体は継続し、ログだけ残す
        print(f"[timer_api] DBからタイマー設定取得に失敗: {exc}")
        return None
    finally:
        if conn:
            conn.close()


@timer_api.route("/api/timer_setting", methods=["GET"])
def get_timer_settings():
    uid = request.args.get("uid", "").strip()
    user_id = resolve_user_id(uid)
    if user_id is None:
        return json_response(
            {
                "work_time": DEFAULT_WORK_TIME,
                "break_time": DEFAULT_BREAK_TIME,
            }
        )

    latest_setting = fetch_latest_timer_setting(user_id)
    if latest_setting:
        try:
            work_minutes = int(latest_setting["work_time"])
            break_minutes = int(latest_setting["break_time"])
        except (TypeError, ValueError):
            return json_response(
                {
                    "work_time": DEFAULT_WORK_TIME,
                    "break_time": DEFAULT_BREAK_TIME,
                }
            )

        return json_response(
            {
                "work_time": work_minutes * 60,
                "break_time": break_minutes * 60,
            }
        )

    return json_response(
        {
            "work_time": DEFAULT_WORK_TIME,
            "break_time": DEFAULT_BREAK_TIME,
        }
    )

@timer_api.route("/api/uid_link_status", methods=["GET"])
def uid_link_status():
    uid = request.args.get("uid", "").strip()
    uid = uid.lower()

    user_id = resolve_user_id(uid)
    return json_response({"linked": user_id is not None})

@timer_api.route("/api/next_todo", methods=["GET", "POST"])
def get_next_todo():
    if request.method == "POST":
        uid, task_id = parse_uid_and_task_id()
        user_id = resolve_user_id(uid)
        if user_id is None:
            return json_response(False)

        try:
            task_id_int = int(task_id)
        except (TypeError, ValueError):
            return json_response(False)

        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE todos
                    SET is_done = TRUE
                    WHERE id = %s AND user_id = %s
                    """,
                    (task_id_int, user_id),
                )
                conn.commit()
                return json_response(cursor.rowcount > 0)
        except Exception as exc:
            if conn:
                conn.rollback()
            print(f"[timer_api] TODO完了更新に失敗: {exc}")
            return json_response(False)
        finally:
            if conn:
                conn.close()

    conn = None
    print("[timer_api] DBから次のTODOを取得開始", flush=True)
    uid, _ = parse_uid_and_task_id()
    user_id = resolve_user_id(uid)
    if user_id is None:
        return json_response(default_todo_payload())
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, due_date
                FROM todos
                WHERE user_id = %s AND is_done = FALSE
                ORDER BY due_date ASC
                LIMIT 1
                """
                ,
                (user_id,)
            )
            todo = cursor.fetchone()
            if todo:
                due_date = todo.get("due_date")
                if hasattr(due_date, "strftime"):
                    due_date_str = due_date.strftime("%Y-%m-%d")
                else:
                    due_date_str = str(due_date) if due_date else DEFAULT_TODO_DUEDATE
                return json_response(
                    {
                        "0": {
                            "id": todo["id"],
                            "title": todo["title"],
                            "duedate": due_date_str,
                        }
                    }
                )
            else:
                return json_response(default_todo_payload())
    except Exception as exc:
        print(f"[timer_api] DBから次のTODO取得に失敗: {exc}")
        return json_response(default_todo_payload())
    finally:
        if conn:
            conn.close()


@timer_api.route("/api", methods=["GET"])
def api_index():
    return json_response({"message": "Welcome to the Timer API"})
