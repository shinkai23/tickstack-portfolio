# ベースイメージ
FROM python:3.11-slim

# 作業ディレクトリを作成
WORKDIR /app

# 必要ファイルをコピー
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# docker-compose.ymlで指定したボリュームをマウントするためCOPYはコメントアウト
COPY clock/ ./clock/
COPY api/ ./api/

# アプリ起動
ENV FLASK_APP=clock/main.py
ENV FLASK_RUN_HOST=0.0.0.0
CMD ["flask", "run"]