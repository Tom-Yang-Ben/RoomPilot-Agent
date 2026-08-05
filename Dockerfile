# RoomPilot 正式 web app（backend/server + frontend 八步流程）的執行映像。
#
#   建置：docker compose build
#   啟動：docker compose up
#
# 體積取捨與四個決策的理由見 docs/DOCKER.md。

# ---------------------------------------------------------------------------
# builder：只負責裝套件與預抓權重，本身不進最終映像
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TORCH_HOME=/opt/torch

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-container.txt ./
RUN pip install -r requirements-container.txt

# torch 走官方 CPU index。走 PyPI 的話 linux wheel 會把 nvidia CUDA runtime
# 一起拉進來（多約 2.5GB），而 backend/floorplan 與 spatial_data/rag 都只做
# 推論，用不到 GPU。版本需與 requirements-rag.txt 的 torch pin 一致。
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.13.0

# rapidocr-onnxruntime 1.4.4 的 metadata 硬性依賴 opencv-python 且未鎖版本，
# pip 會解析成 5.0.0.93 裝進來，蓋掉 headless 的 cv2/ 目錄。後果有兩層：
#   1. GUI build 連結 libGL/libxcb，slim 映像沒有，容器啟動即 ImportError；
#   2. 就算補上那些 X 函式庫讓它開得起來，跑的也是 OpenCV 5.0——
#      requirements.txt:22 已寫明 5.0 改了 HoughLinesP 回傳 shape，
#      門偵測會當場失效。第 2 層不會報錯，比第 1 層危險。
# 所以裝完後把 GUI build 拔掉，並強制還原 headless 的 cv2/。rapidocr 只做
# `import cv2`，拿到 headless 同樣能跑；它的 metadata 會顯示未滿足，是預期的。
RUN pip uninstall -y opencv-python \
 && pip install --no-deps --force-reinstall opencv-python-headless==4.13.0.92

# 建置期就擋下回歸：cv2 必須 import 得動且主版本 <5。這兩件事任一失守都會在
# 執行期變成難查的門偵測錯誤，不如在這裡直接讓 build 失敗。
RUN python -c "import cv2, sys; v=cv2.__version__; print('[check] cv2', v); sys.exit(0 if int(v.split('.')[0]) < 5 else 1)"

# DINOv2 骨幹 88MB 在建置期預抓，執行期就不必連 torch.hub（離線部署前提）。
# 抓不到不擋建置：backend/floorplan/room_classifier.py 會印警告並把房型判斷
# 退回面積規則，服務照常起得來，只是 own_eval 72 房準確度從 90.3% 掉下來。
RUN python -c "import torch; torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14', trust_repo=True)" \
 || echo "[warn] DINOv2 backbone prefetch failed; room typing falls back to area rules"

# ---------------------------------------------------------------------------
# runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# libglib2.0-0：opencv-python-headless 的執行期動態依賴（headless 不需要 libGL，
#               但仍連結 glib）。
# tini：讓 uvicorn 直接收得到 SIGTERM，否則 docker stop 每次都要空等 10 秒。
RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 tini \
 && rm -rf /var/lib/apt/lists/*

# Node 20：第 8 步工程報告的 XLSX 匯出。只搬 binary，不裝整套發行版與 npm。
#
# ⚠ 裝了 node 只是讓 backend/server/engineering/documents.py:142 的
#   shutil.which("node") 找得到執行檔。workbook_builder.mjs 還會動態 import
#   npm 模組 @oai/artifact-tool，那份不在 repo、不在公開 registry，且本機
#   .env 的 ROOMPILOT_ARTIFACT_TOOL_MODULES 是空的——所以 XLSX 匯出在本機
#   現況也是回 WorkbookGenerationUnavailable。模組到位後把它掛進來並設定
#   ROOMPILOT_ARTIFACT_TOOL_MODULES 即可，不必改程式。
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/torch /opt/torch

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TORCH_HOME=/opt/torch \
    ROOMPILOT_RUNTIME_DIR=/data/runtime

# backend/paths.py 的 REPO_ROOT 是 backend/ 的上一層，STATIC_DIR 由它推出
# frontend/；backend/server/main.py 的 PROJECT_DIR 同理。所以 /app 這個佈局
# 是契約的一部分，不能把 backend 搬到別層。
WORKDIR /app
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY pyproject.toml /app/pyproject.toml

# 非 root 執行。/data 是唯一需要寫入的位置（.runtime 的替身）。
RUN useradd --create-home --uid 10001 roompilot \
 && mkdir -p /data/runtime \
 && chown -R roompilot:roompilot /data
USER roompilot

EXPOSE 8002

# 探針沿用既有的 backend/server/main.py:1103 /api/health，不需為容器加端點。
# start-period 給到 60 秒：冷啟含首次 shader 之外的模組載入，實測 30 秒起跳。
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import sys, httpx; sys.exit(0 if httpx.get('http://127.0.0.1:8002/api/health', timeout=4.0).status_code == 200 else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
# --host 0.0.0.0：dev.ps1 與 README 的 127.0.0.1 在容器裡會讓外部連不進來。
# 不加 --reload：那是開發旗標，會多開一個 watcher 行程。
CMD ["uvicorn", "backend.server.main:app", "--host", "0.0.0.0", "--port", "8002"]
