# syntax=docker/dockerfile:1
#
# RoomPilot 的功能容器映像。一份 Dockerfile、多個 target，由 docker-compose.yml 選用。
#
#   base      共用系統層（opencv 的 libGL、glib）
#   web       唯一的 FastAPI（backend.server.main:app）+ 八步靜態前端
#   rag       BGE-M3 embed/rerank sidecar（torch 只裝在這裡）
#   chromium  第 8 步交付 PDF 的排版瀏覽器（官方 playwright 映像 + 中文字型）
#
# db 直接用 pgvector 官方映像，不在這裡建。
# 程式碼不 COPY 進映像：compose 用 bind mount 掛進來，改檔即熱重載。
# ponytail: dev stack。要出貨不可變映像時，在 web target 末端加一層 COPY backend/ 即可。

########################  base  ########################
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# opencv-python（非 headless）在 import 時就要 libGL.so.1 與 glib。
# shapely/psycopg2-binary/pillow 的 wheel 自帶原生庫，不必額外裝。
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


########################  web  ########################
FROM base AS web

# 團隊唯一的依賴正本仍是根目錄 requirements.txt。這裡用 grep 濾掉只有 rag
# sidecar 才需要的重依賴，避免維護第二份清單造成版本漂移。
# torch + sentence-transformers 約 2.5GB，濾掉後 web 映像才回得到 ~1GB。
COPY requirements.txt /tmp/requirements.txt
RUN grep -vE '^(torch|sentence-transformers)==' /tmp/requirements.txt > /tmp/web.txt \
    && pip install -r /tmp/web.txt

# 第 8 步交付提案：playwright 的 Python client 留在 web（要下 page.pdf 指令），
# 但 Chromium 本體不裝——瀏覽器跑在 chromium 容器，見 docker/README.md。
COPY requirements-delivery.txt /tmp/requirements-delivery.txt
RUN pip install -r /tmp/requirements-delivery.txt

EXPOSE 8002

# requirements.txt 釘的是純 uvicorn（不是 uvicorn[standard]），沒有 watchfiles，
# 所以 --reload 實際走 StatReload：比對 mtime，正好是 Windows/WSL2 bind mount
# 唯一可靠的偵測方式（inotify 事件不穿過掛載點）。backend/ 下 166 個 .py，成本可忽略。
# 這行是保險：日後若有人裝了 uvicorn[standard]，watchfiles 會被優先選用，
# 屆時不強制輪詢就會完全收不到主機的存檔。
ENV WATCHFILES_FORCE_POLLING=true

HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=5 \
    CMD python -c "import socket;socket.create_connection(('127.0.0.1',8002),2)"

CMD ["uvicorn", "backend.server.main:app", \
     "--host", "0.0.0.0", "--port", "8002", \
     "--reload", "--reload-dir", "backend"]


########################  rag  ########################
FROM base AS rag

# 預設裝 CPU 版 torch（約 200MB，而非 CUDA 版的 2.5GB+）。
# 有 GPU 時：docker compose build --build-arg TORCH_INDEX=https://pypi.org/simple rag
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

COPY requirements.txt /tmp/requirements.txt
RUN grep -E '^(torch|sentence-transformers|numpy|fastapi|uvicorn|python-dotenv|certifi)==' \
        /tmp/requirements.txt > /tmp/rag.txt \
    && pip install --extra-index-url "${TORCH_INDEX}" -r /tmp/rag.txt

EXPOSE 8009

ENV WATCHFILES_FORCE_POLLING=true

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
    CMD python -c "import socket;socket.create_connection(('127.0.0.1',8009),2)"

CMD ["uvicorn", "docker.rag_sidecar:app", \
     "--host", "0.0.0.0", "--port", "8009", \
     "--reload", "--reload-dir", "backend/spatial_data/rag"]


########################  chromium  ########################
# 版本必須與 requirements-delivery.txt 的 playwright client 一致，
# 否則 chromium.connect() 會被協定版本擋下。
FROM mcr.microsoft.com/playwright:v1.62.0-noble AS chromium

# assets/tokens.css 指名 "Noto Serif CJK TC"。官方 playwright 映像沒有 CJK 字型，
# 少了這層，第 8 步 PDF 的中文會整份變成豆腐方塊（版面正常、字看不到）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 3000

# run-server：官方 Docker 遠端連線做法，client 端用 chromium.connect(ws://…)。
CMD ["npx", "-y", "playwright@1.62.0", "run-server", "--port", "3000", "--host", "0.0.0.0"]
