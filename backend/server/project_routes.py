from fastapi import APIRouter


def create_project_router(dependencies: dict):
    """Build project, render, report, and delivery routes."""
    router = APIRouter()
    def _project_store():
        return dependencies["PROJECT_STORE"]
    AiRenderNotConfigured = dependencies["AiRenderNotConfigured"]
    AiRenderReferenceMissing = dependencies["AiRenderReferenceMissing"]
    DeliveryNotConfigured = dependencies["DeliveryNotConfigured"]
    DesignManualError = dependencies["DesignManualError"]
    FLOORPLAN_EXTENSIONS = dependencies["FLOORPLAN_EXTENSIONS"]
    File = dependencies["File"]
    FileResponse = dependencies["FileResponse"]
    Form = dependencies["Form"]
    GenPicFailure = dependencies["GenPicFailure"]
    HTTPException = dependencies["HTTPException"]
    Image = dependencies["Image"]
    MAX_RENDER_BYTES = dependencies["MAX_RENDER_BYTES"]
    PROJECT_DIR = dependencies["PROJECT_DIR"]
    Path = dependencies["Path"]
    ProjectVersionConflict = dependencies["ProjectVersionConflict"]
    RenderProviderRejected = dependencies["RenderProviderRejected"]
    RenderProviderUnavailable = dependencies["RenderProviderUnavailable"]
    Response = dependencies["Response"]
    STATIC_DIR = dependencies["STATIC_DIR"]
    UploadFile = dependencies["UploadFile"]
    WORKFLOW_STEPS = dependencies["WORKFLOW_STEPS"]
    WorkflowTooLargeError = dependencies["WorkflowTooLargeError"]
    _delivery_amount_twd = dependencies["_delivery_amount_twd"]
    def _floorplan_ocr_provider():
        return dependencies["_floorplan_ocr_provider"]()
    _layout_json_from_analysis = dependencies["_layout_json_from_analysis"]
    _merged_furniture_catalog_cached = dependencies["_merged_furniture_catalog_cached"]
    _price_lookup_keys = dependencies["_price_lookup_keys"]
    ai_render_status = dependencies["ai_render_status"]
    analyze_floorplan_image = dependencies["analyze_floorplan_image"]
    base64 = dependencies["base64"]
    binascii = dependencies["binascii"]
    build_design_delivery_package = dependencies["build_design_delivery_package"]
    build_engineering_estimate = dependencies["build_engineering_estimate"]
    catalog_provider_mode = dependencies["catalog_provider_mode"]
    create_delivery_proposal = dependencies["create_delivery_proposal"]
    create_design_manual = dependencies["create_design_manual"]
    delivery_proposal_status = dependencies["delivery_proposal_status"]
    edit_room_image = dependencies["edit_room_image"]
    generate_palette_images = dependencies["generate_palette_images"]
    generate_room_images = dependencies["generate_room_images"]
    io = dependencies["io"]
    load_postgres_price_index = dependencies["load_postgres_price_index"]
    lru_cache = dependencies["lru_cache"]
    parse_floorplan_with_engine = dependencies["parse_floorplan_with_engine"]
    render_provider_status = dependencies["render_provider_status"]
    submit_render_jobs = dependencies["submit_render_jobs"]

    def _page(name: str) -> FileResponse:
        return FileResponse(STATIC_DIR / name)


    @router.get("/")
    def home() -> FileResponse:
        return _page("index.html")


    @router.get("/styles")
    def styles_page() -> FileResponse:
        return _page("styles.html")


    @router.get("/library")
    def library_page() -> FileResponse:
        return _page("library.html")


    @router.get("/scene")
    def scene_page() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "scene.html",
            headers={"Cache-Control": "no-store"},
        )


    def _stored_project(project_id: str) -> dict:
        try:
            return _project_store().get_project(project_id)
        except KeyError as exc:
            raise HTTPException(
                404,
                {
                    "code": "project_not_found",
                    "message": "找不到這個專案，請返回專案列表重新選擇。",
                },
            ) from exc


    def _stored_floorplan(project_id: str) -> dict:
        _stored_project(project_id)
        try:
            upload = _project_store().get_upload(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                409,
                {
                    "code": "floorplan_missing",
                    "message": "尚未上傳平面圖，請先選擇 DXF、PNG、JPG 或 JPEG 檔案。",
                    "focus": "floorplan-file",
                },
            ) from exc
        if not upload["path"].is_file():
            raise HTTPException(
                410,
                {
                    "code": "floorplan_source_missing",
                    "message": "原始平面圖已遺失，請重新上傳。",
                    "focus": "floorplan-file",
                },
            )
        return upload


    def _validate_floorplan_bytes(extension: str, content: bytes) -> str:
        if not content:
            raise HTTPException(
                422,
                {
                    "code": "empty_floorplan",
                    "message": "檔案沒有內容，請重新選擇平面圖。",
                    "focus": "floorplan-file",
                },
            )
        if extension == ".dxf":
            return "application/dxf"
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise HTTPException(
                422,
                {
                    "code": "invalid_floorplan_image",
                    "message": "檔案副檔名正確，但內容不是可讀取的 PNG 或 JPG 圖片。",
                    "focus": "floorplan-file",
                },
            ) from exc
        return "image/png" if extension == ".png" else "image/jpeg"


    def _unresolved_recognition_review(workflow: dict) -> list[dict]:
        """宣告空間確認完成、卻仍有辨識複核房間未經人工確認的清單。

        對應 ``confirmation.py`` 的 ``targeted_room_review_required`` 閘門：正式
        前端不走 ``/api/floorplan/confirm``，所以在 workflow 宣告
        ``space_confirmation`` 完成時做等值檢查。房間 id 已不存在視為已處理——
        刪除、合併、切割都是人工介入。已完成的舊專案房間全數 confirmed，不受
        影響。
        """
        flow = workflow.get("_flow")
        completed = flow.get("completed") if isinstance(flow, dict) else None
        if not isinstance(completed, list) or "space_confirmation" not in completed:
            return []
        recognition = workflow.get("recognition")
        spatial = (
            recognition.get("spatial_report") if isinstance(recognition, dict) else None
        )
        items = spatial.get("review_items") if isinstance(spatial, dict) else None
        if not isinstance(items, list) or not items:
            return []
        space = workflow.get("space_confirmation")
        rooms = space.get("rooms") if isinstance(space, dict) else None
        rooms_by_id: dict[str, dict] = {}
        if isinstance(rooms, list):
            for room in rooms:
                if isinstance(room, dict) and room.get("id") is not None:
                    rooms_by_id[str(room["id"])] = room
        unresolved: list[dict] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            room_id = str(item.get("room_id"))
            room = rooms_by_id.get(room_id)
            if room is None or room.get("confirmed") is True or room_id in seen:
                continue
            seen.add(room_id)
            unresolved.append(
                {
                    "room_id": room_id,
                    "label": room.get("label"),
                    "reason": item.get("reason"),
                }
            )
        return unresolved


    @router.post("/api/projects", status_code=201)
    def create_project(payload: dict) -> dict:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(
                422,
                {
                    "code": "project_name_required",
                    "message": "請輸入專案名稱。",
                    "focus": "project-name",
                },
            )
        notes = str(payload.get("notes") or "").strip()
        return {"project": _project_store().create_project(name=name, notes=notes)}


    @router.get("/api/projects/{project_id}")
    def get_project(project_id: str, response: Response) -> dict:
        response.headers["Cache-Control"] = "no-store"
        return {"project": _stored_project(project_id)}


    @router.put("/api/projects/{project_id}/workflow")
    def save_project_workflow(project_id: str, payload: dict) -> dict:
        _stored_project(project_id)
        current_step = str(payload.get("current_step") or "").strip() or None
        if current_step and current_step not in WORKFLOW_STEPS:
            raise HTTPException(422, "invalid_workflow_step")
        workflow = payload.get("workflow")
        if workflow is not None and not isinstance(workflow, dict):
            raise HTTPException(422, "workflow_must_be_an_object")
        unresolved_review = _unresolved_recognition_review(workflow or {})
        if unresolved_review:
            raise HTTPException(
                422,
                {
                    "code": "recognition_review_unresolved",
                    "message": (
                        "系統標記需人工複核的房間尚未逐一確認，"
                        "無法將空間確認標為完成；請回到第 4 步處理。"
                    ),
                    "rooms": unresolved_review,
                },
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise HTTPException(422, "expected_revision_must_be_a_non_negative_integer")
        expected_updated_at = None
        if payload.get("replay_pending") is True:
            expected_updated_at = str(payload.get("base_updated_at") or "").strip()
            if not expected_updated_at:
                raise HTTPException(422, "pending_save_base_version_required")
        try:
            project = _project_store().update_workflow(
                project_id,
                current_step=current_step,
                workflow=workflow or {},
                expected_revision=expected_revision,
                expected_updated_at=expected_updated_at,
            )
        except ProjectVersionConflict as exc:
            if expected_revision is not None:
                raise HTTPException(
                    409,
                    {
                        "code": "project_revision_conflict",
                        "message": "專案已在另一個分頁更新，請載入最新版本後再儲存。",
                        "project": exc.project,
                    },
                ) from exc
            raise HTTPException(409, "project_version_conflict") from exc
        except WorkflowTooLargeError as exc:
            raise HTTPException(
                413,
                {
                    "code": "workflow_too_large",
                    "message": "專案草稿內容超過 2 MB，請移除大型暫存資料後再儲存。",
                },
            ) from exc
        return {"project": project}


    @router.post("/api/projects/{project_id}/floorplan", status_code=201)
    async def save_project_floorplan(
        project_id: str,
        file: UploadFile = File(...),
        expected_revision: int | None = Form(None),
    ) -> dict:
        _stored_project(project_id)
        filename = Path(file.filename or "").name
        extension = Path(filename).suffix.lower()
        if extension not in FLOORPLAN_EXTENSIONS:
            raise HTTPException(
                415,
                {
                    "code": "unsupported_floorplan_type",
                    "message": "只支援 DXF、PNG、JPG 或 JPEG 平面圖。",
                    "allowed_extensions": list(FLOORPLAN_EXTENSIONS),
                },
            )
        content = await file.read()
        mime_type = _validate_floorplan_bytes(extension, content)
        try:
            upload = _project_store().save_upload(
                project_id,
                filename=filename,
                extension=extension,
                mime_type=mime_type,
                content=content,
                expected_revision=expected_revision,
            )
        except ProjectVersionConflict as exc:
            raise HTTPException(
                409,
                {
                    "code": "project_revision_conflict",
                    "message": "專案已在另一個分頁更新，請載入最新版本後再上傳。",
                    "project": exc.project,
                },
            ) from exc
        return {
            "project": _project_store().get_project(project_id),
            "upload": {
                "filename": upload["filename"],
                "extension": upload["extension"],
                "mime_type": upload["mime_type"],
                "source_url": f"/api/projects/{project_id}/floorplan/source",
            }
        }


    @router.get("/api/projects/{project_id}/floorplan/source")
    def get_project_floorplan_source(project_id: str) -> FileResponse:
        upload = _stored_floorplan(project_id)
        return FileResponse(
            upload["path"],
            media_type=upload["mime_type"],
            filename=upload["filename"],
        )


    def _public_render_record(record: dict) -> dict:
        payload = {key: value for key, value in record.items() if key != "path"}
        payload["download_url"] = (
            f"/api/projects/{record['project_id']}/renders/{record['render_id']}/png"
        )
        return payload


    @router.post("/api/projects/{project_id}/renders", status_code=201)
    async def create_project_render(
        project_id: str,
        file: UploadFile = File(...),
        expected_revision: int = Form(...),
        white_model_version: int = Form(0),
        viewpoint_version: int = Form(0),
        style_version: int = Form(0),
        style_card_id: str = Form("unassigned"),
        provider: str = Form("browser_capture"),
    ) -> dict:
        _stored_project(project_id)
        if expected_revision < 0:
            raise HTTPException(422, "expected_revision_must_be_a_non_negative_integer")
        if min(white_model_version, viewpoint_version, style_version) < 0:
            raise HTTPException(422, "render_versions_must_be_non_negative")
        if provider != "browser_capture":
            raise HTTPException(
                422,
                {"code": "unsupported_render_provider", "message": "目前只接受瀏覽器場景 PNG。"},
            )
        content = await file.read(MAX_RENDER_BYTES + 1)
        if len(content) > MAX_RENDER_BYTES:
            raise HTTPException(
                413,
                {"code": "render_too_large", "message": "最終 PNG 不可超過 20 MB。"},
            )
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(
                415,
                {"code": "invalid_render_png", "message": "最終輸出必須是 PNG。"},
            )
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise HTTPException(
                422,
                {"code": "invalid_render_png", "message": "PNG 檔案已損壞。"},
            ) from exc
        try:
            render, project = _project_store().save_render(
                project_id,
                expected_revision=expected_revision,
                content=content,
                white_model_version=white_model_version,
                viewpoint_version=viewpoint_version,
                style_version=style_version,
                style_card_id=style_card_id,
                provider=provider,
            )
        except ProjectVersionConflict as exc:
            raise HTTPException(
                409,
                {
                    "code": "project_revision_conflict",
                    "message": "專案已更新，請重新載入後再輸出 PNG。",
                    "project": exc.project,
                },
            ) from exc
        return {"project": project, "render": _public_render_record(render)}


    @router.get("/api/projects/{project_id}/renders")
    def list_project_renders(project_id: str) -> dict:
        try:
            renders = _project_store().list_renders(project_id)
        except KeyError as exc:
            raise HTTPException(
                404, {"code": "project_not_found", "message": "找不到專案。"}
            ) from exc
        return {"renders": [_public_render_record(record) for record in renders]}


    @router.get("/api/projects/{project_id}/renders/{render_id}/png")
    def download_project_render(project_id: str, render_id: str) -> FileResponse:
        try:
            render = _project_store().get_render(project_id, render_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                404, {"code": "render_not_found", "message": "找不到這張 PNG。"}
            ) from exc
        path = render["path"]
        if not path.is_file():
            raise HTTPException(
                410,
                {"code": "render_file_missing", "message": "PNG 紀錄存在，但檔案已遺失。"},
            )
        return FileResponse(path, media_type="image/png", filename=render["filename"])


    @router.get("/api/render-provider/status")
    def get_render_provider_status() -> dict:
        return render_provider_status()


    @router.post("/api/projects/{project_id}/render-jobs", status_code=202)
    async def create_project_render_jobs(project_id: str, payload: dict) -> dict:
        _stored_project(project_id)
        if payload.get("project_id") != project_id:
            raise HTTPException(
                422,
                {"code": "render_project_mismatch", "message": "渲染資料與目前專案不一致。"},
            )
        try:
            return await submit_render_jobs(payload)
        except ValueError as exc:
            raise HTTPException(
                422,
                {"code": str(exc), "message": "渲染資料不完整，請回到第 9 步重新確認。"},
            ) from exc
        except RenderProviderUnavailable as exc:
            raise HTTPException(
                503,
                {"code": str(exc), "message": "遠端渲染服務尚未設定或目前無法連線。"},
            ) from exc
        except RenderProviderRejected as exc:
            raise HTTPException(
                502,
                {"code": str(exc), "message": "遠端渲染服務拒絕了這次任務。"},
            ) from exc


    def _looks_like_png_data_url(value: object) -> bool:
        """image data URL 且 base64 內容解得開、非空。

        只檢查前綴不夠：``data:image/png;base64,``（沒有內容）會一路過關到生圖 adapter，
        在那裡被真值判斷靜默丟掉，最後送出一個沒有參考圖的純文字請求——模型照樣回一張
        圖，但已經不是使用者鎖定的那個空間，而且回應裡看不出來。故在入口就擋掉。
        """
        text = str(value or "")
        if not text.startswith("data:image/") or ";base64," not in text:
            return False
        try:
            return bool(base64.b64decode(text.split(",", 1)[1], validate=True))
        except (binascii.Error, ValueError):
            return False


    @router.get("/api/ai-render/status")
    def get_ai_render_status() -> dict:
        """第 8 步 AI 生圖服務（OpenRouter nano banana）是否可用；不外洩 token。"""
        return ai_render_status()


    @router.post("/api/projects/{project_id}/ai-renders", status_code=201)
    def create_project_ai_renders(project_id: str, payload: dict) -> dict:
        """逐房視角經 OpenRouter nano banana 生成寫實室內圖（不移動擺設）。

        前端送 ``scene``（state.sceneData）＋逐房 ``rooms``（含第 7 步鎖定視角的 3D
        截圖）。伺服器補充需求/材質/家電/色卡資訊、逐房呼叫 Gen_Pic Agent，並把每房
        鎖定清單存進 project workflow，供整批一次改圖使用。未設定金鑰回 503。
        """
        _stored_project(project_id)
        if payload.get("project_id") not in (None, project_id):
            raise HTTPException(
                422,
                {"code": "render_project_mismatch", "message": "生圖資料與目前專案不一致。"},
            )
        scene = payload.get("scene")
        if not isinstance(scene, dict) or not scene.get("scene_objects"):
            raise HTTPException(
                422,
                {"code": "scene_required", "message": "缺少場景資料，請先完成第 6 步配置。"},
            )
        rooms = payload.get("rooms")
        if not isinstance(rooms, list) or not rooms:
            raise HTTPException(
                422,
                {"code": "room_views_required", "message": "缺少逐房視角，請先在第 7 步鎖定視角。"},
            )
        for room in rooms:
            if not isinstance(room, dict) or not str(room.get("room_id") or "").strip():
                raise HTTPException(
                    422,
                    {"code": "room_id_required", "message": "每個房間視角都需要 room_id。"},
                )
            if not _looks_like_png_data_url(room.get("reference_png_data_url")):
                raise HTTPException(
                    422,
                    {"code": "reference_png_required", "message": "每個房間視角都需要 3D 視角截圖。"},
                )
        try:
            outcome = generate_room_images(scene, rooms)
        except AiRenderReferenceMissing as exc:
            raise HTTPException(
                422,
                {"code": "reference_png_required", "message": f"每個房間視角都需要 3D 視角截圖（{exc}）。"},
            ) from exc
        except AiRenderNotConfigured as exc:
            raise HTTPException(
                503,
                {
                    "code": str(exc),
                    "message": "尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。",
                },
            ) from exc
        project = _project_store().update_workflow(
            project_id,
            workflow={
                "ai_render": {
                    "edit_used": 0,
                    # 逐房各自一次改圖額度（指南 §3E：每房可在初圖後提出一次修改）。
                    "rooms": [{**room, "edit_used": 0} for room in outcome["rooms"]],
                }
            },
        )
        return {
            "results": outcome["results"],
            "edit_remaining": 1,
            "revision": project["revision"],
            "updated_at": project["updated_at"],
        }


    @router.post("/api/projects/{project_id}/palette-renders", status_code=201)
    def create_project_palette_renders(project_id: str, payload: dict) -> dict:
        """第 7 步代表房「色卡比較」:同一代表房 × 多張色卡,一次併發呼叫 Gen_Pic Agent
        (Nano Banana Pro)。**每個專案只能成功生成一次** —— 已生成過回 409,不再呼叫模型;
        全部失敗則不鎖定,允許重試。base64 不入 workflow(2MB 上限),只存旗標與各卡狀態。
        """
        project = _stored_project(project_id)
        if payload.get("project_id") not in (None, project_id):
            raise HTTPException(
                422,
                {"code": "render_project_mismatch", "message": "生圖資料與目前專案不一致。"},
            )
        palette_state = (project.get("workflow") or {}).get("palette_render") or {}
        if palette_state.get("generated"):
            raise HTTPException(
                409,
                {
                    "code": "palette_already_generated",
                    "message": "此專案的代表房色卡比較圖已生成過，每個專案只能生成一次。",
                },
            )
        scene = payload.get("scene")
        if not isinstance(scene, dict) or not scene.get("scene_objects"):
            raise HTTPException(
                422,
                {"code": "scene_required", "message": "缺少場景資料，請先完成第 6 步配置。"},
            )
        room = payload.get("room")
        if not isinstance(room, dict) or not str(room.get("room_id") or "").strip():
            raise HTTPException(
                422,
                {"code": "room_required", "message": "缺少代表房，請先在第 7 步選定代表房與視角。"},
            )
        if not _looks_like_png_data_url(room.get("reference_png_data_url")):
            raise HTTPException(
                422,
                {"code": "reference_png_required", "message": "代表房需要 3D 視角截圖。"},
            )
        style_card_ids = payload.get("style_card_ids")
        if not isinstance(style_card_ids, list) or not [
            card for card in style_card_ids if str(card or "").strip()
        ]:
            raise HTTPException(
                422,
                {"code": "style_card_ids_required", "message": "缺少色卡清單。"},
            )
        try:
            outcome = generate_palette_images(scene, room, style_card_ids)
        except AiRenderReferenceMissing as exc:
            raise HTTPException(
                422,
                {"code": "reference_png_required", "message": f"代表房需要 3D 視角截圖（{exc}）。"},
            ) from exc
        except AiRenderNotConfigured as exc:
            raise HTTPException(
                503,
                {
                    "code": str(exc),
                    "message": "尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。",
                },
            ) from exc
        any_completed = any(item.get("status") == "completed" for item in outcome["results"])
        if not any_completed:
            # 全部失敗:不鎖定,讓使用者可重試;回失敗結果供前端顯示原因。
            return {
                "results": outcome["results"],
                "already_generated": False,
                "room_id": outcome["room_id"],
            }
        project = _project_store().update_workflow(
            project_id,
            workflow={
                "palette_render": {
                    "generated": True,
                    "room_id": outcome["room_id"],
                    "cards": [
                        {
                            "style_card_id": item.get("style_card_id"),
                            "status": item.get("status"),
                        }
                        for item in outcome["results"]
                    ],
                }
            },
        )
        return {
            "results": outcome["results"],
            "already_generated": False,
            "room_id": outcome["room_id"],
            "revision": project["revision"],
            "updated_at": project["updated_at"],
        }


    @router.post("/api/projects/{project_id}/ai-renders/{room_id}/edit", status_code=201)
    def edit_project_ai_render(project_id: str, room_id: str, payload: dict) -> dict:
        """整批一次改圖：只改使用者指定內容、其餘鎖定不動；額度用完回 409。"""
        project = _stored_project(project_id)
        ai_render = (project.get("workflow") or {}).get("ai_render") or {}
        room_state = next(
            (
                row
                for row in ai_render.get("rooms") or []
                if str(row.get("room_id")) == room_id
            ),
            None,
        )
        if not room_state or not room_state.get("lock_manifest"):
            raise HTTPException(
                409,
                {"code": "room_not_generated", "message": "這個房間尚未生圖，無法修改。"},
            )
        # ponytail: 單一使用者流程，read-check-write 的競態可忽略；額度仍由伺服器強制。
        # 逐房各一次改圖（指南 §3E）；只有這個房間的額度用完才回 409，不影響其他房間。
        if int(room_state.get("edit_used") or 0) >= 1:
            raise HTTPException(
                409,
                {"code": "ai_edit_budget_exhausted", "message": "這個房間只能修改一次，額度已用完。"},
            )
        feedback = str(payload.get("feedback") or "").strip()
        if not feedback:
            raise HTTPException(
                422, {"code": "feedback_required", "message": "請描述想修改的內容。"}
            )
        if not _looks_like_png_data_url(payload.get("image_data_url")):
            raise HTTPException(
                422, {"code": "base_image_required", "message": "缺少要修改的原圖。"}
            )
        try:
            result = edit_room_image(
                room_id, feedback, payload["image_data_url"], room_state["lock_manifest"]
            )
        except AiRenderNotConfigured as exc:
            raise HTTPException(
                503,
                {
                    "code": str(exc),
                    "message": "尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。",
                },
            ) from exc
        except GenPicFailure as exc:
            raise HTTPException(
                502,
                {"code": "ai_edit_failed", "message": "；".join(exc.notices) or "改圖失敗。"},
            ) from exc
        updated_rooms = [
            {**row, "edit_used": 1} if str(row.get("room_id")) == room_id else row
            for row in ai_render.get("rooms") or []
        ]
        project = _project_store().update_workflow(
            project_id, workflow={"ai_render": {"rooms": updated_rooms}}
        )
        return {
            "result": result,
            "edit_remaining": 0,
            "revision": project["revision"],
            "updated_at": project["updated_at"],
        }


    def _design_manual_dir(project_id: str) -> Path:
        return _project_store().runtime_dir / "manuals" / project_id


    def _public_design_manual(project_id: str, record: dict) -> dict:
        payload = {key: value for key, value in record.items() if key != "filename"}
        payload["download_url"] = f"/api/projects/{project_id}/design-manual/pdf"
        return payload


    @router.post("/api/projects/{project_id}/design-manual", status_code=201)
    def create_project_design_manual(project_id: str, payload: dict) -> dict:
        """第 8 步收尾：由 Report Agent 統整需求、配置、家具、色卡與生圖成果，
        輸出九章設計手冊 PDF。

        前端送 ``scene``（state.sceneData）＋逐房 ``rooms``（含房間尺寸與目前最新
        的生圖 data URL；改圖後前端已就地更新）。LLM 只潤飾前言與設計理念，未設定
        OPENROUTER_API_KEY 時走 deterministic 底稿照樣輸出。重新產出會覆蓋 workflow
        紀錄並提高 revision；舊 PDF 檔保留於 runtime 目錄。
        """
        project = _stored_project(project_id)
        scene, rooms = _validated_report_payload(project_id, payload)
        try:
            manual, record = create_design_manual(
                project_id,
                scene,
                rooms,
                _design_manual_dir(project_id),
                design_revision=project["revision"],
            )
        except DesignManualError as exc:
            raise HTTPException(
                502, {"code": "design_manual_failed", "message": str(exc)}
            ) from exc
        updated = _project_store().update_workflow(
            project_id, workflow={"design_manual": record}
        )
        return {
            "manual": _public_design_manual(project_id, record),
            "revision": updated["revision"],
            "updated_at": updated["updated_at"],
        }


    @router.get("/api/projects/{project_id}/design-manual/pdf")
    def download_project_design_manual(project_id: str) -> FileResponse:
        project = _stored_project(project_id)
        record = (project.get("workflow") or {}).get("design_manual") or {}
        filename = str(record.get("filename") or "")
        if not filename:
            raise HTTPException(
                404,
                {"code": "design_manual_not_found", "message": "尚未產出設計手冊。"},
            )
        path = _design_manual_dir(project_id) / filename
        if not path.is_file():
            raise HTTPException(
                410,
                {"code": "design_manual_file_missing", "message": "設計手冊紀錄存在，但檔案已遺失，請重新產出。"},
            )
        return FileResponse(path, media_type="application/pdf", filename=filename)


    def _validated_report_payload(project_id: str, payload: dict) -> tuple[dict, list[dict]]:
        """設計手冊與交付提案共用的 payload 驗證（scene＋rooms）。"""
        if payload.get("project_id") not in (None, project_id):
            raise HTTPException(
                422,
                {"code": "manual_project_mismatch", "message": "報告資料與目前專案不一致。"},
            )
        scene = payload.get("scene")
        if not isinstance(scene, dict) or not scene.get("scene_objects"):
            raise HTTPException(
                422,
                {"code": "scene_required", "message": "缺少場景資料，請先完成第 6 步配置。"},
            )
        rooms = payload.get("rooms")
        if not isinstance(rooms, list) or not any(
            isinstance(room, dict) and str(room.get("room_id") or "").strip()
            for room in rooms
        ):
            raise HTTPException(
                422,
                {"code": "rooms_required", "message": "缺少房間資料，無法組成果報告。"},
            )
        scene = {**scene, "scene_objects": _with_catalog_prices(scene["scene_objects"])}
        return scene, rooms


    @router.get("/api/delivery-proposal/status")
    def get_delivery_proposal_status() -> dict:
        """交付提案排版引擎（playwright Chromium）是否可用；未安裝時回報安裝指引。"""
        return delivery_proposal_status()


    @router.post("/api/projects/{project_id}/delivery-proposal", status_code=201)
    def create_project_delivery_proposal(project_id: str, payload: dict) -> dict:
        """第 8 步收尾第二版報告：roompilot-delivery-pdf 打包 skill 排版的品牌
        交付提案 PDF，與九章設計手冊吃同一份 payload，供兩版比較。"""
        project = _stored_project(project_id)
        scene, rooms = _validated_report_payload(project_id, payload)
        try:
            _, record = create_delivery_proposal(
                project_id,
                project.get("name") or "RoomPilot 專案",
                scene,
                rooms,
                _design_manual_dir(project_id),
                design_revision=project["revision"],
            )
        except DeliveryNotConfigured as exc:
            raise HTTPException(
                503, {"code": "delivery_engine_not_configured", "message": str(exc)}
            ) from exc
        except DesignManualError as exc:
            raise HTTPException(
                502, {"code": "delivery_proposal_failed", "message": str(exc)}
            ) from exc
        # 同一顆按鈕、同一次請求出兩份檔：PDF 之外再落一份工程估價與排程 XLSX。
        # 放在 PDF 成功之後，PDF 掛了就不做白工。
        record = {
            **record,
            "engineering": build_engineering_estimate(
                project_id,
                str(project["revision"]),
                project.get("workflow") or {},
                _project_store().runtime_dir / "manuals",
            ),
        }
        updated = _project_store().update_workflow(
            project_id, workflow={"delivery_proposal": record}
        )
        payload_record = {key: value for key, value in record.items() if key != "filename"}
        payload_record["download_url"] = (
            f"/api/projects/{project_id}/delivery-proposal/pdf"
        )
        return {
            "proposal": payload_record,
            "revision": updated["revision"],
            "updated_at": updated["updated_at"],
        }


    @router.get("/api/projects/{project_id}/delivery-proposal/pdf")
    def download_project_delivery_proposal(project_id: str) -> FileResponse:
        project = _stored_project(project_id)
        record = (project.get("workflow") or {}).get("delivery_proposal") or {}
        filename = str(record.get("filename") or "")
        if not filename:
            raise HTTPException(
                404,
                {"code": "delivery_proposal_not_found", "message": "尚未產出交付提案。"},
            )
        path = _design_manual_dir(project_id) / filename
        if not path.is_file():
            raise HTTPException(
                410,
                {"code": "delivery_proposal_file_missing", "message": "交付提案紀錄存在，但檔案已遺失，請重新產出。"},
            )
        return FileResponse(path, media_type="application/pdf", filename=filename)


    @router.get("/api/projects/{project_id}/delivery-proposal/xlsx")
    def download_project_engineering_estimate(project_id: str) -> FileResponse:
        """與交付提案 PDF 同一次產出的工程估價與初步排程 XLSX。"""
        project = _stored_project(project_id)
        proposal = (project.get("workflow") or {}).get("delivery_proposal") or {}
        engineering = proposal.get("engineering") or {}
        relative = str(engineering.get("file") or "")
        base = (_project_store().runtime_dir / "manuals").resolve()
        # workflow 內容前端可寫，組完路徑一定要確認還在 manuals 目錄內。
        path = (base / relative).resolve() if relative else base
        if not relative or not path.is_relative_to(base) or not path.is_file():
            raise HTTPException(
                404,
                {
                    "code": "engineering_estimate_not_found",
                    "message": "尚未產出工程估價，或檔案已遺失，請重新產出設計提案。",
                },
            )
        # 示範單價的警語只寫在儲存格裡，檔案一轉寄出去就看不到了；檔名帶著走。
        demo = "DEMO-" if engineering.get("demo_mode") else ""
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"roompilot-estimate-{demo}{project_id[:8]}.xlsx",
        )


    # ---- 第 8 步成果包（design-delivery）----
    # 由 bella-new 分支移植：把全屋簡報、逐房成果、工程報告、資安審核與預算書
    # 打包成單一 JSON；並依本分支定案把設計提案 PDF（delivery-proposal）紀錄
    # 一併帶出，讓前端在同一個成果包對話框內產出與下載 PDF。

    @lru_cache(maxsize=1)
    def _catalog_price_index() -> dict[str, int]:
        """型錄單價表（家具 id → 元），只在第 8 步報價階段建立。

        單價刻意不進 site_payload、scene_objects 與生圖 context——選件與擺位不該
        看到價格；報告要出報價單時才用 furniture_id 回查這張表。PostgreSQL 是定
        價權威，連不上就退回已驗證 JSON 型錄（缺價的列照樣印「待報價」，不推估）。
        """
        if catalog_provider_mode(PROJECT_DIR) == "postgres":
            try:
                index = load_postgres_price_index(PROJECT_DIR)
            except Exception:  # noqa: BLE001 - 報價缺價可降級，報告不該因 DB 斷線中止
                index = {}
            if index:
                return index
        return {
            str(item["furniture_id"]): round(price)
            for item in _merged_furniture_catalog_cached()
            if item.get("furniture_id") and (price := _delivery_amount_twd(item))
        }


    # 報價回查用的 id 鍵。這幾把常常全部落空：``furniture_id`` 是引擎擺位 id
    # （engine/rules.py 產的 ``room-1-bed-1``），``catalog_furniture_id`` 可能是前端
    # 候選槽 id（scene_v2.js 的 ``room-1-bed-double-candidate-1``），兩者都不是型錄
    # id。真正的型錄 id 只剩 GLB 檔名認得，見 _price_lookup_keys()。
    def _with_catalog_prices(items: list) -> list[dict]:
        """報價入口補上 ``price_twd``；已帶價的列不覆蓋。"""
        index = _catalog_price_index()
        priced: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if _delivery_amount_twd(item) is not None:
                priced.append(item)
                continue
            price = next(
                (index[key] for key in _price_lookup_keys(item) if key in index),
                None,
            )
            priced.append({**item, "price_twd": price} if price else item)
        return priced


    @router.post("/api/projects/{project_id}/design-delivery")
    def create_project_design_delivery(project_id: str, payload: dict) -> dict:
        """第 8 步成果包：五章 JSON 打包，並依本分支定案把 delivery-proposal
        的產出紀錄與下載位置併入同一份回應。"""
        project = _stored_project(project_id)
        if payload.get("project_id") not in (None, project_id):
            raise HTTPException(422, {"code": "delivery_project_mismatch"})
        record = (project.get("workflow") or {}).get("delivery_proposal") or {}
        proposal = {key: value for key, value in record.items() if key != "filename"}
        if proposal:
            proposal["status"] = "generated"
            proposal["download_url"] = f"/api/projects/{project_id}/delivery-proposal/pdf"
        else:
            proposal = {
                "status": "not_generated",
                "hint": "可在成果包視窗直接產出設計提案 PDF。",
            }
        return build_design_delivery_package(
            project_id,
            payload,
            delivery_proposal=proposal,
            with_catalog_prices=_with_catalog_prices,
        )


    def _floorplan_is_confirmed(project: dict) -> bool:
        confirmation = project.get("workflow", {}).get("floorplan_confirmation", {})
        if confirmation.get("confirmed") is True:
            return True

        # Existing projects used the former privacy-shaped confirmation contract.
        privacy = project.get("workflow", {}).get("privacy", {})
        return (
            privacy.get("accepted") is True
            and (privacy.get("project_only") is True or privacy.get("projectOnly") is True)
            and (privacy.get("no_training") is True or privacy.get("noTraining") is True)
        )


    @router.post("/api/projects/{project_id}/floorplan/analyze")
    def analyze_project_floorplan(project_id: str) -> dict:
        project = _stored_project(project_id)
        upload = _stored_floorplan(project_id)
        if not _floorplan_is_confirmed(project):
            raise HTTPException(
                409,
                {
                    "code": "floorplan_confirmation_required",
                    "message": "請先確認圖檔內容正確，才能開始辨識。",
                    "focus": "project-floorplan-confirmation",
                },
            )

        content = upload["path"].read_bytes()
        if upload["extension"] == ".dxf":
            try:
                parsed, _ = parse_floorplan_with_engine(
                    content.decode("utf-8", errors="ignore")
                )
                if not parsed:
                    raise ValueError("DXF 中沒有可建立房間的牆體幾何")
            except Exception as exc:
                raise HTTPException(
                    422,
                    {
                        "code": "dxf_parse_failed",
                        "message": f"DXF 無法解析：{exc}",
                        "focus": "floorplan-file",
                    },
                ) from exc
            analysis = {
                "recognition_engine": "dxf",
                "source_type": "dxf",
                "floorplan": parsed,
            }
            geometry_engine = "dxf"
        else:
            try:
                analysis = analyze_floorplan_image(
                    content,
                    filename=upload["filename"],
                    ocr_provider=_floorplan_ocr_provider(),
                )
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    422,
                    {
                        "code": "cody_recognition_failed",
                        "message": f"Cody 無法辨識這張平面圖：{exc}",
                        "focus": "floorplan-file",
                    },
                ) from exc
            geometry_engine = "cody"

        _project_store().update_workflow(
            project_id,
            current_step="recognition",
            workflow={
                "recognition": analysis,
                "confirmed_floorplan": None,
                "calibration": None,
                "space_confirmation": None,
                "requirements": None,
                "layout_2d": None,
                "white_model_3d": None,
                "realistic_3d": None,
                "_flow": {
                    "currentStep": "recognition",
                    "completed": ["project", "upload", "recognition"],
                    "staleFrom": "calibration",
                    "data": {
                        "recognition": {"engine": geometry_engine},
                        "calibration": None,
                        "space_confirmation": None,
                        "requirements": None,
                        "layout_2d": None,
                        "white_model_3d": None,
                        "realistic_3d": None,
                    },
                },
            },
        )
        layout_json = _layout_json_from_analysis(analysis)
        return {
            "analysis": analysis,
            "layout_json": layout_json,
            "geometry_engine": geometry_engine,
        }

    return router, {
        "_page": _page,
        "home": home,
        "styles_page": styles_page,
        "library_page": library_page,
        "scene_page": scene_page,
        "_stored_project": _stored_project,
        "_stored_floorplan": _stored_floorplan,
        "_validate_floorplan_bytes": _validate_floorplan_bytes,
        "_unresolved_recognition_review": _unresolved_recognition_review,
        "create_project": create_project,
        "get_project": get_project,
        "save_project_workflow": save_project_workflow,
        "save_project_floorplan": save_project_floorplan,
        "get_project_floorplan_source": get_project_floorplan_source,
        "_public_render_record": _public_render_record,
        "create_project_render": create_project_render,
        "list_project_renders": list_project_renders,
        "download_project_render": download_project_render,
        "get_render_provider_status": get_render_provider_status,
        "create_project_render_jobs": create_project_render_jobs,
        "_looks_like_png_data_url": _looks_like_png_data_url,
        "get_ai_render_status": get_ai_render_status,
        "create_project_ai_renders": create_project_ai_renders,
        "create_project_palette_renders": create_project_palette_renders,
        "edit_project_ai_render": edit_project_ai_render,
        "_design_manual_dir": _design_manual_dir,
        "_public_design_manual": _public_design_manual,
        "create_project_design_manual": create_project_design_manual,
        "download_project_design_manual": download_project_design_manual,
        "_validated_report_payload": _validated_report_payload,
        "get_delivery_proposal_status": get_delivery_proposal_status,
        "create_project_delivery_proposal": create_project_delivery_proposal,
        "download_project_delivery_proposal": download_project_delivery_proposal,
        "download_project_engineering_estimate": download_project_engineering_estimate,
        "_catalog_price_index": _catalog_price_index,
        "_with_catalog_prices": _with_catalog_prices,
        "create_project_design_delivery": create_project_design_delivery,
        "_floorplan_is_confirmed": _floorplan_is_confirmed,
        "analyze_project_floorplan": analyze_project_floorplan,
    }
