# main.py (修正版)
from m5stack import *
from m5stack_ui import *
from uiflow import *

import urequests
import wifiCfg
import json
import ntptime
import time
import gc
import _thread
import imu
import math
import machine
import ubinascii

screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0xFFFFFF)

time_label = M5Label('00:00', x=230, y=10, color=0x000, font=FONT_MONT_26, parent=None)
week = M5Label('week', x=125, y=10, color=0x000, font=FONT_MONT_26, parent=None)
is_connected = M5Label('wifi : none', x=9, y=64, color=0x000, font=FONT_MONT_14, parent=None)

slider = M5Slider(x=35, y=153, w=250, h=12, min=0, max=3000, bg_c=0xa0a0a0, color=0x08A2B0, parent=None)
start = M5Btn(text='                             .', x=110, y=180, w=100, h=50, bg_c=0xFFFFFF, text_c=0x000000, font=FONT_UNICODE_24, parent=None)
pomo_time_label = M5Label('00:00', x=106, y=110, color=0x000, font=FONT_MONT_38, parent=None)

today = M5Label('00/00', x=15, y=10, color=0x000, font=FONT_MONT_26, parent=None)
line1 = M5Line(x1=5, y1=50, x2=315, y2=50, color=0x000, width=3, parent=None)

reset = M5Btn(text='◼︎', x=56, y=185, w=40, h=40, bg_c=0xffffff, text_c=0x000000, font=FONT_UNICODE_24, parent=None)
is_work = M5Label('work', x=137, y=90, color=0x000, font=FONT_MONT_18, parent=None)
label0 = M5Label('▶︎', x=148, y=193, color=0x000, font=FONT_UNICODE_24, parent=None)

task_checkbox = M5Checkbox(text='Task', x=35, y=121, text_c=0x000000, check_c=0x000000, font=FONT_UNICODE_24, parent=None)
done = M5Btn(text='完了', x=110, y=180, w=100, h=40, bg_c=0xFFFFFF, text_c=0x000000, font=FONT_UNICODE_24, parent=None)

# ===== リロードボタン（常時表示）=====
reload_btn = M5Btn(text='R', x=270, y=55, w=40, h=40,
                   bg_c=0xFFFFFF, text_c=0x000000,
                   font=FONT_MONT_26, parent=None)

# ===== UID 表示用（初期は非表示） =====
uid_val = M5Label('', x=9, y=78, color=0x000000, font=FONT_MONT_14, parent=None)
uid_val.set_hidden(True)

# 表示用（Tues表記のままにする）
Week = ['Sun', 'Mon', 'Tues', 'Wed', 'Thu', 'Fri', 'Sat']

# ボタンクリック時の背景色
BTN_BG_NORMAL = 0xFFFFFF
BTN_BG_PRESSED = 0xC0C0C0  # 灰色

# グローバル初期値（明示）
imu0 = imu.IMU()
pomodoro_flag = False
toDo_flag = False
change_mode_flag = True
is_stopped = True
restart_thread_running = False
reload_running = False

# ポモドーロの状態
work_time = 1500
break_time = 300
remain_time = work_time
is_break = False

# --- スライダー負荷対策 ---
slider_ignore_event = False
slider_last_move_ms = 0
slider_pending_snap = None

# スレッド多重起動防止
count_down_thread_running = False

mode = 0
task = {}
check_flag = False

uid = None

# --- 押下→通信をメインループで実行するためのフラグ ---
reload_request = False
reload_request_ms = 0

done_request = False
done_request_ms = 0

done_running = False

# BASE_URL = "http://172.20.10.4:5001"
BASE_URL = "https://tickstackm5.pythonanywhere.com"


### uid の取得
def set_uid():
    global uid
    CONFIG_PATH = '/flash/config.txt'
    try:
        with open(CONFIG_PATH, 'r') as f:
            uid = f.read().strip()
        if not uid:
            raise Exception('empty uid')
        print('[DBG] Unique ID Found:', uid)
    except:
        uid = ubinascii.hexlify(machine.unique_id()).decode()
        try:
            with open(CONFIG_PATH, 'w') as f:
                f.write(uid)
            print('[DBG] Unique ID Initialized:', uid)
        except Exception as e:
            print('[ERR] Unique ID save failed:', e)

def _set_uid_overlay(visible, uid_text=''):
    """未紐づけ時だけUIDを画面に出す。紐づいたら隠す。"""
    if visible:
        uid_val.set_text('UID : ' + str(uid_text))
        uid_val.set_hidden(False)
    else:
        uid_val.set_hidden(True)


def check_uid_linked_from_server(uid):
    """
    サーバにUIDを送って linked 判定を取る。
    True=紐づいてる / False=未紐づけ（または判定不能）
    """
    req = None
    try:
        url = BASE_URL + "/api/uid_link_status?uid=" + str(uid)
        req = urequests.request(method='GET', url=url, headers={})

        txt = req.text if req else ''
        res = json.loads(txt) if txt else {}
        linked = res.get('linked', False)

        # linkedが "true"/"false" の文字列でも耐える
        if isinstance(linked, str):
            linked = (linked.lower() == 'true')

        return bool(linked)

    except Exception as e:
        print('[ERR] check_uid_linked_from_server:', e)
        # 通信失敗時は「未紐づけ扱い」にして表示（登録できるように）
        return False

    finally:
        try:
            if req:
                req.close()
        except:
            pass
        gc.collect()


def boot_uid_handshake():
    """起動時：UID送信→未紐づけなら表示／紐づいてたら非表示"""
    # Wi-Fiが無いなら送れないので表示に倒す
    if not wifiCfg.wlan_sta.isconnected():
        _set_uid_overlay(True, uid)
        return

    linked = check_uid_linked_from_server(uid)
    if linked:
        _set_uid_overlay(False)
    else:
        _set_uid_overlay(True, uid)


### 初期設定
def init():
    print('[DBG] init start')
    set_uid()
    change_mode()
    # 最低限、タイマー表示を初期化
    draw_pomodoro_timer()
    draw_tDo_list()


### WiFi設定
def connect_wifi():
    print('[DBG] connect_wifi start')
    if not wifiCfg.wlan_sta.isconnected():
        is_connected.set_text('wifi : searching')
        # ※ここはあなたのSSID/PWのまま
        wifiCfg.doConnect('wifi-name', 'wifi-password')

    if wifiCfg.wlan_sta.isconnected():
        is_connected.set_text('wifi : connected')

        # NTP同期（失敗しても落とさない）
        try:
            ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9)

            # weekday の表記ゆれ対策
            wstr = ntp.weekday()
            w_map = {
                'Sun': 0, 'Mon': 1, 'Tue': 2, 'Tues': 2,
                'Wed': 3, 'Thu': 4, 'Fri': 5, 'Sat': 6
            }
            w_int = w_map.get(wstr, 0)

            year_val = ntp.year()          # ★/100 をやめる
            month_val = ntp.month()
            day_val = ntp.day()
            hour_val = ntp.hour()
            minute_val = ntp.minute()
            second_val = ntp.second()

            rtc.datetime((year_val, month_val, day_val, w_int, hour_val, minute_val, second_val, 0))
            print('[DBG] rtc set:', year_val, month_val, day_val, w_int, hour_val, minute_val, second_val)
        except Exception as e:
            print('[ERR] ntp/rtc set failed:', e)

        # サーバ設定取得（落ちてもfallback）
        try:
            get_pomodoro_timer_setting()
        except Exception as e:
            print('[ERR] get_pomodoro_timer_setting failed:', e)
        try:
            get_todo_list_setting()
        except Exception as e:
            print('[ERR] get_todo_list_setting failed:', e)

    else:
        is_connected.set_text('wifi : failed')
        print('[DBG] wifi connect failed')
    
    try:
        boot_uid_handshake()
    except Exception as e:
        print('[ERR] boot_uid_handshake failed:', e)

def reload_from_server():
    """表示中のページに応じて必要なものだけリロードする"""
    global reload_running, mode

    if reload_running:
        return
    reload_running = True

    try:
        is_connected.set_text('wifi : reload...')

        # Wi-Fiが切れてたら再接続
        if not wifiCfg.wlan_sta.isconnected():
            try:
                connect_wifi()
            except Exception as e:
                print('[ERR] reload_from_server: connect_wifi failed', e)
                is_connected.set_text('wifi : reload failed')
                return

        # ---- ページごとに必要なものだけ取得 ----
        # mode: 0=時計(何も表示なし) / 1=Timer / 2=ToDo
        if mode == 1:
            # Timerページなら Timer_Settings だけ
            try:
                get_pomodoro_timer_setting()
            except Exception as e:
                print('[ERR] reload_from_server: get_pomodoro_timer_setting', e)

        elif mode == 2:
            # ToDoページなら ToDo だけ
            try:
                get_todo_list_setting()
            except Exception as e:
                print('[ERR] reload_from_server: get_todo_list_setting', e)

        else:
            # 時計ページ中に押されたとき：好みで決めてOK
            # ここでは「両方」更新にしておく（不要なら消してOK）
            try:
                get_pomodoro_timer_setting()
            except Exception as e:
                print('[ERR] reload_from_server: get_pomodoro_timer_setting', e)
            try:
                get_todo_list_setting()
            except Exception as e:
                print('[ERR] reload_from_server: get_todo_list_setting', e)

        # UID紐づけ表示はついでに更新（不要なら消してOK）
        try:
            boot_uid_handshake()
        except Exception as e:
            print('[ERR] reload_from_server: boot_uid_handshake', e)

        is_connected.set_text('wifi : connected')

    finally:
        reload_running = False


def z(num):
    try:
        n = int(num)
    except Exception:
        n = 0
    return ('0' + str(n)) if n < 10 else str(n)


### 時刻表示
def clock_thread():
    print('[DBG] clock_thread started')

    last_date = None
    last_week = None
    last_time = None

    while True:
        dt = rtc.datetime()

        # 日付
        date_str = z(dt[1]) + '/' + z(dt[2])
        if date_str != last_date:
            last_date = date_str
            today.set_text(date_str)

        # 曜日
        w = dt[3]
        try:
            wi = int(w)
        except Exception:
            wi = 0
        if wi < 0 or wi > 6:
            wi = 0
        week_str = Week[wi]
        if week_str != last_week:
            last_week = week_str
            week.set_text(week_str)

        # 時刻（分が変わった時だけ更新）
        time_str = z(dt[4]) + ':' + z(dt[5])
        if time_str != last_time:
            last_time = time_str
            time_label.set_text(time_str)

        time.sleep(1)


### ポモドーロタイマー
def pomodoro_timer():
    global pomodoro_flag
    if pomodoro_flag:
        pomo_time_label.set_hidden(False)
        is_work.set_hidden(False)
        start.set_hidden(False)
        reset.set_hidden(False)
        slider.set_hidden(False)
        label0.set_hidden(False)
    else:
        pomo_time_label.set_hidden(True)
        is_work.set_hidden(True)
        start.set_hidden(True)
        reset.set_hidden(True)
        slider.set_hidden(True)
        label0.set_hidden(True)


def get_pomodoro_timer_setting():
    global work_time, break_time, remain_time, is_break
    print('[DBG] get_pomodoro_timer_setting')

    req = None
    try:
        req = urequests.request(
            method='GET',
            url=BASE_URL + "/api/timer_setting?uid=" + str(uid),
            headers={}
        )
        timer_setting = json.loads(req.text) if (req and req.text) else {}

        work_time = int(timer_setting.get('work_time', 600))
        break_time = int(timer_setting.get('break_time', 300))
        print('[DBG] get_pomodoro_timer_setting: success', work_time, break_time)

    except Exception as e:
        print('[DBG] get_pomodoro_timer_setting: fallback', e)
        work_time = 600
        break_time = 300

    finally:
        try:
            if req:
                req.close()
        except:
            pass
        gc.collect()

    slider.set_range(0, work_time)
    is_work.set_text('work')
    remain_time = work_time
    is_break = False
    draw_pomodoro_timer()


def draw_pomodoro_timer():
    global remain_time
    try:
        r = int(remain_time)
    except Exception:
        r = 0
    if r < 0:
        r = 0

    minutes = r // 60
    sec = r % 60
    pomo_time_label.set_text(z(minutes) + ':' + z(sec))

    if slider_pending_snap is None:
        try:
            slider.set_value(r)
        except Exception:
            pass


def break_switch():
    global is_break, remain_time, work_time, break_time
    if is_break:
        is_break = False
        remain_time = work_time
        state = 'work'
    else:
        is_break = True
        remain_time = break_time
        state = 'break'

    is_work.set_text(state)
    try:
        slider.set_range(0, remain_time)
        slider.set_value(remain_time)
    except Exception:
        pass
    draw_pomodoro_timer()


def count_down():
    global remain_time, is_stopped, pomodoro_flag, count_down_thread_running
    try:
        while not is_stopped:
            if isinstance(remain_time, int) and remain_time > 0:
                remain_time -= 1
            else:
                break_switch()
            if pomodoro_flag:
                draw_pomodoro_timer()
            time.sleep(1)
    finally:
        count_down_thread_running = False


def start_pressed():
    global is_stopped, count_down_thread_running
    if is_stopped:
        is_stopped = False
        start.set_btn_text('⏸')
        if not count_down_thread_running:
            count_down_thread_running = True
            try:
                _thread.start_new_thread(count_down, ())
            except Exception as e:
                print('[ERR] start_pressed: thread start failed', e)
                count_down_thread_running = False
    else:
        is_stopped = True
        start.set_btn_text('▶︎')


start.pressed(start_pressed)


def reset_pressed():
    global is_stopped, is_break
    is_stopped = True
    is_break = True
    start.set_btn_text('▶︎')
    break_switch()


reset.pressed(reset_pressed)


def slider_changed(value):
    global remain_time, is_stopped
    global slider_ignore_event, slider_last_move_ms, slider_pending_snap

    # set_value() 由来の changed は無視（再帰/連鎖防止）
    if slider_ignore_event:
        return

    # 60秒単位に丸める（内部値）
    try:
        r = int(value // 60) * 60
    except Exception:
        r = 0

    remain_time = r
    is_stopped = True
    start.set_btn_text('▶︎')

    # ★重い draw_pomodoro_timer() は呼ばない（ドラッグ中はラベルだけ更新）
    pomo_time_label.set_text(z(r // 60) + ':' + z(r % 60))

    # スナップ予約（「しばらく動かなかったら slider を r に合わせる」）
    slider_pending_snap = r
    slider_last_move_ms = time.ticks_ms()


slider.changed(slider_changed)

def process_slider_snap():
    global slider_pending_snap, slider_last_move_ms, slider_ignore_event

    if slider_pending_snap is None:
        return

    # 250ms 動きが無ければ「指を離した扱い」でスナップ
    if time.ticks_diff(time.ticks_ms(), slider_last_move_ms) < 250:
        return

    target = slider_pending_snap
    slider_pending_snap = None

    slider_ignore_event = True
    try:
        slider.set_value(target)  # ここで changed が発火しても ignore で無視される
    finally:
        slider_ignore_event = False

### ToDo リスト
def todo_list():
    global toDo_flag, check_flag
    if toDo_flag:
        task_checkbox.set_hidden(False)
        done.set_hidden(True)  # 未チェックの間は隠す
        check_flag = False
        try:
            task_checkbox.set_checked(False)
        except Exception:
            pass
    else:
        task_checkbox.set_hidden(True)
        done.set_hidden(True)


def get_todo_list_setting():
    global task, check_flag
    print('[DBG] get_todo_list_setting')

    task = {}
    check_flag = False

    req = None
    try:
        req = urequests.request(
            method='GET',
            url=BASE_URL + "/api/next_todo?uid=" + str(uid),
            headers={}
        )
        res = json.loads(req.text) if (req and req.text) else {}

        # サーバの返しが {"0": {...}} 想定
        task = res.get('0', {})
        print('[DBG] get_todo_list_setting: success')

    except Exception as e:
        print('[ERR] get_todo_list_setting: fallback', e)
        task = {
            "id": "12345",
            "title": "title",
            "duedate": "01/01"
        }

    finally:
        try:
            if req:
                req.close()
        except:
            pass
        gc.collect()

    draw_tDo_list()


def draw_tDo_list():
    global task, check_flag
    if not task:
        text = 'toDo リストが空です'
    else:
        dd = task.get("duedate", "--/--")
        tt = task.get("title", "")
        if tt == "Congraturations!":
            text = tt;
        else:
            text = dd + ': ' + tt

    task_checkbox.set_text(text)

    # ToDoモード中はチェックボックスは表示（ただし change_mode() 側で隠されることはある）
    if toDo_flag:
        task_checkbox.set_hidden(False)

    # チェックされたら完了ボタンを出す
    if check_flag and toDo_flag:
        done.set_hidden(False)
        done.set_btn_text('完了')
    else:
        done.set_hidden(True)


def task_checkbox_checked():
    global check_flag
    check_flag = True
    draw_tDo_list()


def task_checkbox_unchecked():
    global check_flag
    check_flag = False
    draw_tDo_list()


def submit_task():
    global task, check_flag
    if not task:
        print('[DBG] submit_task: no task to submit')
        return

    task_id = task.get("id", "")
    if not task_id:
        print('[ERR] submit_task: task has no id')
        return

    url = BASE_URL + "/api/next_todo?uid=" + str(uid) + "&id=" + str(task_id)

    req = None
    try:
        req = urequests.request(method='POST', url=url, headers={})
        print('[DBG] submit_task: success')

        # 表示更新
        check_flag = False
        try:
            task_checkbox.set_checked(False)
        except Exception:
            pass
        get_todo_list_setting()

    except Exception as e:
        print('[ERR] submit error: ', e)

    finally:
        try:
            if req:
                req.close()
        except:
            pass
        gc.collect()


task_checkbox.checked(task_checkbox_checked)
task_checkbox.unchecked(task_checkbox_unchecked)

def btn_set_bg(btn, color):
    # FW差分対策（set_bg_colorが無い環境もあるので保険）
    try:
        btn.set_bg_color(color)
    except Exception:
        try:
            btn.set_bg_c(color)
        except Exception:
            pass

def done_pressed():
    global done_request, done_request_ms, done_running
    if done_running or done_request:
        return
    btn_set_bg(done, BTN_BG_PRESSED)     # まず灰色にして
    done_request = True                  # 通信は後で
    done_request_ms = time.ticks_ms()
    
done.pressed(done_pressed)

def reload_pressed():
    global reload_request, reload_request_ms
    if reload_running or reload_request:
        return
    btn_set_bg(reload_btn, BTN_BG_PRESSED)
    reload_request = True
    reload_request_ms = time.ticks_ms()

reload_btn.pressed(reload_pressed)

def change_mode():
    global mode, pomodoro_flag, toDo_flag
    pomodoro_flag = (mode == 1)
    toDo_flag = (mode == 2)

    pomodoro_timer()
    todo_list()

    if pomodoro_flag:
        draw_pomodoro_timer()
    if toDo_flag:
        draw_tDo_list()


def delayed_restart():
    global change_mode_flag, restart_thread_running
    try:
        time.sleep(1.5)
        change_mode_flag = True
    finally:
        restart_thread_running = False


def set_mode():
    global change_mode_flag, mode, restart_thread_running
    if change_mode_flag:
        try:
            angle = imu0.ypr[2]
        except Exception:
            angle = 0

        if 75 <= math.fabs(angle):
            change_mode_flag = False

            if not restart_thread_running:
                restart_thread_running = True
                try:
                    _thread.start_new_thread(delayed_restart, ())
                except Exception:
                    restart_thread_running = False

            if angle < 0:
                mode = (mode + 2) % 3
            else:
                mode = (mode + 1) % 3

            change_mode()
    wait_ms(20)


# ===== 起動処理 =====
init()
connect_wifi()
time.sleep(0.2)

# 時計スレッド開始
try:
    _thread.start_new_thread(clock_thread, ())
except Exception as e:
    print('[ERR] clock thread start failed', e)

# メインループ
while True:
    process_slider_snap()

    # UIが描画される時間を作ってから通信（ここがキモ）
    if reload_request and time.ticks_diff(time.ticks_ms(), reload_request_ms) > 60:
        reload_request = False
        try:
            reload_from_server()
        finally:
            btn_set_bg(reload_btn, BTN_BG_NORMAL)

    if done_request and time.ticks_diff(time.ticks_ms(), done_request_ms) > 60:
        done_request = False
        done_running = True
        try:
            submit_task()
        finally:
            done_running = False
            btn_set_bg(done, BTN_BG_NORMAL)

    set_mode()
