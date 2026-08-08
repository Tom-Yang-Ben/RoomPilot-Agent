# RoomPilot 正式 web app（backend/server + frontend 八步流程）的執行映像。
#
#   建置：docker compose build
#   啟動：docker compose up -d
#
# 六個 stage：
#   builder   裝 Python 套件（含 opencv 還原與建置期 assert）
#   hf-fetch  只裝 huggingface-hub，負責抓 4.5GB 的 RAG 權重（自成一層，快取鍵最穩）
#   models    把權重收下來、當場驗證載得起來，並預抓 DINOv2 骨幹
#   nodedeps  用 node:20-slim 跑 npm ci，產出第 9 步 XLSX 需要的 exceljs
#   runtime   最終映像：非 root、tini、healthcheck
#   test      runtime 之上加 tests/ 與 pytest，供在容器內跑測試
#
# 體積取捨與決策理由見 docs/DOCKER.md。

# WITH_RAG=0 可建出不含家具 RAG 的精簡映像（少約 6GB），供 CI 或
# 只跑八步流程的場合使用。預設 1：容器內 RAG 可用，權重烘進映像。
ARG WITH_RAG=1

# ---------------------------------------------------------------------------
# builder：只負責裝套件，本身不進最終映像
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ARG WITH_RAG

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-container.txt requirements-container-rag.txt ./
RUN pip install -r requirements-container.txt

# torch 走官方 CPU index。走 PyPI 的話 linux wheel 會把 nvidia CUDA runtime
# 一起拉進來（多約 2.5GB），而 backend/floorplan 的房型語意層與 spatial_data/rag
# 都只做推論，用不到 GPU。版本需與 requirements-rag.txt 的 torch pin 一致。
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.13.0

RUN if [ "$WITH_RAG" = "1" ]; then \
        pip install -r requirements-container-rag.txt ; \
    else \
        echo "[build] WITH_RAG=0 — 跳過 sentence-transformers／openai／anthropic" ; \
    fi

# rapidocr-onnxruntime 1.4.4 的 metadata 硬性依賴 opencv-python 且未鎖版本，
# pip 會解析成 5.0.0.93 裝進來，蓋掉 headless 的 cv2/ 目錄。後果有兩層：
#   1. GUI build 連結 libGL/libxcb，slim 映像沒有，容器啟動即 ImportError；
#   2. 就算補上那些 X 函式庫讓它開得起來，跑的也是 OpenCV 5.0——
#      requirements.txt:22 已寫明 5.0 改了 HoughLinesP 回傳 shape，
#      門偵測會當場失效。第 2 層不會報錯，比第 1 層危險。
# 所以裝完後把 GUI build 拔掉，並強制還原 headless 的 cv2/。rapidocr 只做
# `import cv2`，拿到 headless 同樣能跑；它的 metadata 會顯示未滿足，是預期的。
#
# ⚠ 這一步必須放在所有 pip install 之後：任何後續安裝都可能再把 opencv-python
#   拉回來。改動上面任一份 requirements 時，請重新確認這條依賴鏈。
RUN pip uninstall -y opencv-python \
 && pip install --no-deps --force-reinstall opencv-python-headless==4.13.0.92

# 建置期就擋下回歸：cv2 必須 import 得動且主版本 <5。這兩件事任一失守都會在
# 執行期變成難查的門偵測錯誤，不如在這裡直接讓 build 失敗。
RUN python -c "import cv2, sys; v=cv2.__version__; print('[check] cv2', v); sys.exit(0 if int(v.split('.')[0]) < 5 else 1)"

# ---------------------------------------------------------------------------
# hf-fetch：只裝 huggingface-hub，負責下載 BGE-M3 與 reranker
#
# 刻意不從 builder 繼承：這一層要下載 4.5GB，快取鍵越穩越好。改
# requirements-container.txt 不該害你重抓一次權重。
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS hf-fetch

ARG WITH_RAG

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    ROOMPILOT_RAG_MODEL_CACHE=/opt/rag-models \
    HF_HUB_DISABLE_TELEMETRY=1

COPY requirements-container-rag.txt ./
COPY scripts/docker/fetch_rag_models.py /tmp/fetch_rag_models.py

# 版本從 requirements-container-rag.txt 讀，不在這裡二次硬編碼。
RUN mkdir -p /opt/rag-models \
 && if [ "$WITH_RAG" = "1" ]; then \
        pip install "$(grep -E '^huggingface-hub==' requirements-container-rag.txt)" \
     && python /tmp/fetch_rag_models.py download ; \
    else \
        echo "[build] WITH_RAG=0 — 不下載 RAG 權重，/opt/rag-models 留空" ; \
    fi

# ---------------------------------------------------------------------------
# models：驗證權重真的載得起來，並預抓 DINOv2 骨幹
# ---------------------------------------------------------------------------
FROM builder AS models

ARG WITH_RAG

ENV TORCH_HOME=/opt/torch \
    ROOMPILOT_RAG_MODEL_CACHE=/opt/rag-models \
    HF_HUB_DISABLE_TELEMETRY=1

COPY --from=hf-fetch /opt/rag-models /opt/rag-models
COPY scripts/docker/fetch_rag_models.py /tmp/fetch_rag_models.py

# 抓得到檔 != 載得起來。這一步會真的 encode 一句中文並跑一次 rerank，
# 失敗就讓 build 當場失敗，不拖到使用者按下第 6 步才發現。
RUN if [ "$WITH_RAG" = "1" ]; then \
        python /tmp/fetch_rag_models.py verify ; \
    else \
        echo "[build] WITH_RAG=0 — 跳過 RAG 權重驗證" ; \
    fi

# DINOv2 骨幹 88MB 在建置期預抓，執行期就不必連 torch.hub（離線部署前提）。
# 抓不到不擋建置：backend/floorplan 會印警告並把房型判斷退回面積規則，
# 服務照常起得來，只是 own_eval 72 房準確度從 90.3% 掉下來。
#
# 先 mkdir 是因為預抓失敗時 /opt/torch 不會被建出來，runtime stage 的
# COPY --from=models /opt/torch 就會整個 build 失敗——用不到的東西不該
# 變成建置阻塞。
RUN mkdir -p /opt/torch \
 && (python -c "import torch; torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14', trust_repo=True)" \
     || echo "[warn] DINOv2 backbone prefetch failed; room typing falls back to area rules")

# ---------------------------------------------------------------------------
# nodedeps：第 9 步工程報告的 XLSX 匯出相依
#
# tools/artifact_tool_local 是 @oai/artifact-tool 的 exceljs 相容層（真品是私有
# 套件，公開 npm 404）。@oai/ 那份已進版控，exceljs 走 npm ci 在映像內重裝——
# 不搬本機 node_modules，那是 Windows 上裝的。
# ---------------------------------------------------------------------------
FROM node:20-slim AS nodedeps

WORKDIR /opt/artifact-tool
COPY tools/artifact_tool_local/package.json tools/artifact_tool_local/package-lock.json ./
RUN npm ci --omit=dev
COPY tools/artifact_tool_local/@oai ./@oai

# ---------------------------------------------------------------------------
# nodetest：tests/static 的 jsdom DOM 測試相依
#
# 只給下面的 test stage 用。沒有它，test_scene_pending_actions_dom.py 這類
# 測試會安靜 skip——skip 看起來很像通過，但其實沒驗到。
# ---------------------------------------------------------------------------
FROM node:20-slim AS nodetest

WORKDIR /opt/static-tests
COPY tests/static/package.json tests/static/package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------------
# runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ARG WITH_RAG

# libglib2.0-0：opencv-python-headless 的執行期動態依賴（headless 不需要 libGL，
#               但仍連結 glib）。
# libgomp1：torch CPU wheel 的 OpenMP 執行期。
# tini：讓 uvicorn 直接收得到 SIGTERM，否則 docker stop 每次都要空等 10 秒。
RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 tini \
 && rm -rf /var/lib/apt/lists/*

# Node 20：第 9 步工程報告的 XLSX 匯出。只搬 binary，不裝整套發行版與 npm。
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=nodedeps /opt/artifact-tool /opt/artifact-tool

COPY --from=builder /opt/venv /opt/venv
COPY --from=models /opt/torch /opt/torch

# --chown 而不是之後再 chown -R：後者會把 4.3GB 權重整份複製成新的一層，
# 映像直接翻倍。COPY 時順手改擁有者，成本是零。
#
# 為什麼權重目錄要可寫：huggingface_hub 載入時會在
# <cache>/models--*/trees/<rev>.json 寫一份 tree cache。root 擁有的話每次載入
# 都會印
#   Ignoring corrupted tree cache file ...: [Errno 13] Permission denied
# ——訊息還說成 corrupted，會把人帶去查錯方向。功能不受影響，但沒理由留著。
#
# 用數字 10001:10001 而不是名稱：useradd 在這行之後才執行，
# 這時 roompilot 這個名字還不存在，寫名稱會直接 build 失敗。
COPY --from=models --chown=10001:10001 /opt/rag-models /opt/rag-models

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/roompilot \
    TORCH_HOME=/opt/torch

# ⚠ 執行資料刻意放在 /app/.runtime，不是 /data/runtime。
#
# 原因：backend/server/engineering/api.py:77 把第 9 步工程文件的產出目錄寫死成
#   generated_dir = project_dir / ".runtime" / "engineering"
# 它「不吃」ROOMPILOT_RUNTIME_DIR。若把 runtime dir 指到 /data/runtime，
# 工程文件會去寫 /app/.runtime/engineering——那層由 root 擁有，非 root 的
# uid 10001 寫不進去，第 9 步會在產生報告時失敗，而且 /api/health 是綠的，
# 完全看不出來。
#
# 讓兩者指向同一個目錄，就不必為了容器去改 Bella 的程式碼。
ENV ROOMPILOT_RUNTIME_DIR=/app/.runtime

# RAG 權重烘在映像裡。
#
# ⚠ 用 HF_HUB_CACHE 而不是 HF_HOME，因為兩者的層級語意差一層：
#   HF_HOME=/x   →  hub 快取在 /x/hub
#   HF_HUB_CACHE=/x → hub 快取就是 /x
# 而 model_runtime.py:113 是把 ROOMPILOT_RAG_MODEL_CACHE 直接當
# SentenceTransformer 的 cache_folder 用（= 直接含 models--BAAI--* 的那層）。
# 設 HF_HOME 會讓兩邊差一層：model_runtime.py:23 的 _repo_is_cached 因為同時
# 接受 <cache>/hub/models--* 而回報「已快取」，實際載入卻失敗——狀態端點說
# 好，功能是壞的，這是最難查的一種。
ENV ROOMPILOT_RAG_MODEL_CACHE=/opt/rag-models \
    HF_HUB_CACHE=/opt/rag-models

# 權重已經在映像內，執行期不該再連 HuggingFace。少了這幾行，網路不通時
# 每次載入都會先卡一輪連線逾時才走 local_files_only。
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

# 第 9 步 XLSX。workbook_builder.mjs:16 會組出
# <modulesRoot>/@oai/artifact-tool/dist/artifact_tool.mjs，
# 該檔再由 Node 沿目錄往上找 /opt/artifact-tool/node_modules/exceljs。
ENV ROOMPILOT_ARTIFACT_NODE=node \
    ROOMPILOT_ARTIFACT_TOOL_MODULES=/opt/artifact-tool

# backend/paths.py 的 REPO_ROOT 是 backend/ 的上一層，STATIC_DIR 由它推出
# frontend/；backend/server/main.py 的 PROJECT_DIR 同理。所以 /app 這個佈局
# 是契約的一部分，不能把 backend 搬到別層。
WORKDIR /app
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY pyproject.toml /app/pyproject.toml

# 非 root 執行。
#   /app/.runtime  唯一需要寫入的位置（compose 會在這裡掛 named volume）。
#                  裡面有 auth_secret.key、uploads/、renders/、indexes/、
#                  doc-report/、engineering/。main.py:165 在 import 階段就會
#                  mkdir，寫不進去是「啟動失敗」不是「請求失敗」。
#   /opt/torch     torch.hub 載入 DINOv2 時會 touch hub/trusted_list，
#                  root 擁有的話非 root 會 EROFS/EACCES。權重已預抓，
#                  正常不會觸發，但 chown 的成本是零，不賭。
RUN useradd --create-home --uid 10001 roompilot \
 && mkdir -p /app/.runtime \
 && chown -R roompilot:roompilot /app/.runtime /opt/torch
USER roompilot

EXPOSE 8002

# 探針沿用既有的 backend/server/main.py:1103 /api/health，不需為容器加端點。
#
# ⚠ 只判 HTTP 200 是不夠的：離線形態（型錄退 JSON、專案退 SQLite）時 formal
#   為 false，該端點會回「200 + status=offline」。那種容器是活著但不是正式
#   組態，判成 healthy 等於把降級當正常。所以這裡直接看 payload 的 ready。
#
# start-period 給到 240 秒：RAG 開啟時 backend/server/main.py:292 的背景預載要
# 把 bge-m3 與 reranker 兩份 2.3GB 權重讀進記憶體，CPU 上實測 34 秒起跳，
# 冷啟磁碟未熱時更久。這段期間探針失敗不計入 retries。
HEALTHCHECK --interval=30s --timeout=10s --start-period=240s --retries=3 \
  CMD python -c "import sys, httpx; r=httpx.get('http://127.0.0.1:8002/api/health', timeout=8.0); sys.exit(0 if r.status_code==200 and r.json().get('ready') is True else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
# --host 0.0.0.0：dev.ps1 與 README 的 127.0.0.1 在容器裡會讓外部連不進來。
# 不加 --reload：那是開發旗標，會多開一個 watcher 行程，且容器內的程式碼是
# 烘進映像的，改 repo 檔案不會生效（見 docs/DOCKER.md「改了程式沒生效」）。
CMD ["uvicorn", "backend.server.main:app", "--host", "0.0.0.0", "--port", "8002"]

# ---------------------------------------------------------------------------
# test：在容器內跑團隊測試套件
#
#   .\scripts\docker\roompilot.ps1 test
# 或
#   docker build --target test -t roompilot-app:test .
#   docker run --rm --env-file .env -v "$PWD/JSON:/app/JSON:ro" roompilot-app:test
#
# 這一層的東西都不進 runtime 映像。每一項都有非帶不可的理由：
#   tests/     測試本體。
#   scripts/   test_official_catalog_sql.py 等四支 `from scripts.sql import ...`，
#              少了它是 collection error 而非 skip。
#   testdata/  test_floorplan_vision.py 的辨識測資與 ground truth。
#   docs/      多支測試讀 docs/contracts/ 的契約文件做斷言。
#   .env.example  test_env_example_contract.py 逐欄斷言範本檔內容。
#              ⚠ 它斷言的是「範本檔長什麼樣」（例如 DB_HOST=localhost），
#              與容器實際組態相反是正常的，不要為了容器去改範本。
#   根目錄 md 與 requirements  文件同步類測試會讀。
#   tests/static/node_modules  jsdom；沒有它 DOM 測試會 skip。
#
# JSON/（224M）刻意不 COPY：conftest.py:16 預設把型錄 provider 壓成 json，
# 而 json provider 讀的是 JSON/ 底下兩個大檔（main.py:150、:158）。
# 走執行期唯讀掛載，映像不必為了測試胖 224MB。
# ---------------------------------------------------------------------------
FROM runtime AS test

USER root
RUN pip install --no-cache-dir pytest==9.1.1

COPY --chown=roompilot:roompilot tests/ /app/tests/
COPY --chown=roompilot:roompilot scripts/ /app/scripts/
COPY --chown=roompilot:roompilot testdata/ /app/testdata/
COPY --chown=roompilot:roompilot docs/ /app/docs/
COPY --chown=roompilot:roompilot tools/ /app/tools/
COPY --chown=roompilot:roompilot .env.example README.md AGENTS.md CLAUDE.md \
     requirements.txt requirements-ocr.txt requirements-rag.txt /app/
COPY --from=nodetest --chown=roompilot:roompilot /opt/static-tests/node_modules /app/tests/static/node_modules

# ⚠ 這裡必須把 ROOMPILOT_RUNTIME_DIR 清空，不能沿用 runtime stage 的
#   /app/.runtime，也不能改指到 /tmp。
#
#   tests/test_project_workflow_api.py::test_worktree_uses_the_main_repository_runtime_directory
#   驗的正是「沒設這個變數時，worktree 會回推到主 repo 的 .runtime」。
#   只要這個變數有值，runtime_paths.py:22 就直接回傳它，該測試必紅。
#   （2026-08-09 實測：設成 /tmp/roompilot-runtime 時這支就是這樣掛的。）
#
#   清空後 conftest 會把專案 store 導到臨時目錄，engineering 那條寫死路徑
#   落在 /app/.runtime——那層在 runtime stage 已經 chown 給 uid 10001，可寫。
ENV ROOMPILOT_RUNTIME_DIR=""

USER roompilot

CMD ["pytest", "-q"]
