# 04. API設計

このページでは、公開コード上で確認できるエンドポイントのみを整理しています。

## Web画面向けルーティング

| Method | Path | 用途 | 実装箇所 |
|---|---|---|---|
| GET / POST | `/signup` | ユーザー登録 | `clock/main.py` |
| GET / POST | `/login` | ログイン | `clock/main.py` |
| GET | `/logout` | ログアウト | `clock/main.py` |
| GET | `/` | トップページ表示 | `clock/main.py` |
| POST | `/submit_uid` | M5Stack UIDをログインユーザーに紐づける | `clock/main.py` |
| GET | `/todo` | ToDo一覧表示 | `clock/main.py` |
| GET | `/todo/category/<category_id>` | カテゴリ別ToDo一覧表示 | `clock/main.py` |
| POST | `/set_todo` | ToDo登録 | `clock/main.py` |
| POST | `/todo/<todo_id>/status` | ToDoの完了状態更新 | `clock/main.py` |
| POST | `/todo/<todo_id>/delete` | ToDo削除 | `clock/main.py` |
| GET | `/time` | タイマー設定一覧表示 | `clock/main.py` |
| POST | `/set_timer` | タイマー設定登録 | `clock/main.py` |
| GET | `/select_timer/<setting_id>` | 使用するタイマー設定の選択 | `clock/main.py` |
| POST | `/delete_timer` | タイマー設定削除 | `clock/main.py` |

## M5Stack向けAPI

| Method | Path | 用途 | 主なレスポンス |
|---|---|---|---|
| GET | `/api/timer_setting` | UIDに紐づく最新のタイマー設定を取得 | `work_time`, `break_time` |
| GET | `/api/uid_link_status` | UIDがWebユーザーに紐づいているか確認 | `linked` |
| GET | `/api/next_todo` | UIDに紐づく次の未完了ToDoを取得 | `id`, `title`, `duedate` |
| POST | `/api/next_todo` | M5Stack側からToDoを完了にする | `true` / `false` |
| GET | `/api` | API疎通確認用 | `message` |

## API設計で意識した点

- M5Stack側はログインセッションを持たないため、UIDでユーザーを解決する
- M5Stack側の実装を単純にするため、JSONの項目数を絞る
- 通信失敗時でもM5Stack側が停止しないよう、デフォルト値を返す処理を用意する

## 今後改善したい点

- `/select_timer/<setting_id>` はDB更新を行うため、GETではなくPOSTにする
- 入力値の範囲チェックをサーバ側にも追加する
- API仕様をREADMEとは別に最初から固定し、M5Stack担当とサーバ担当の認識ずれを減らす
