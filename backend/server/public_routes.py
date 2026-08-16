from fastapi import APIRouter


def create_public_router(dependencies: dict):
    """Build public catalog, agent, scene, and floor-plan routes."""
    router = APIRouter()
    def _project_store():
        return dependencies["PROJECT_STORE"]
    File = dependencies["File"]
    FileResponse = dependencies["FileResponse"]
    Form = dependencies["Form"]
    HTTPException = dependencies["HTTPException"]
    JSONResponse = dependencies["JSONResponse"]
    PROJECT_DIR = dependencies["PROJECT_DIR"]
    Path = dependencies["Path"]
    PipelineNotStarted = dependencies["PipelineNotStarted"]
    QUESTIONNAIRE_VISUAL_CATALOG = dependencies["QUESTIONNAIRE_VISUAL_CATALOG"]
    Query = dependencies["Query"]
    RedirectResponse = dependencies["RedirectResponse"]
    Response = dependencies["Response"]
    SAMPLE_FLOORPLAN = dependencies["SAMPLE_FLOORPLAN"]
    SelectionParseError = dependencies["SelectionParseError"]
    SelectionUnavailableError = dependencies["SelectionUnavailableError"]
    UploadFile = dependencies["UploadFile"]
    _catalog_count_summary = dependencies["_catalog_count_summary"]
    _category_groups_for = dependencies["_category_groups_for"]
    _filter_furniture_payload = dependencies["_filter_furniture_payload"]
    def _floorplan_ocr_provider():
        return dependencies["_floorplan_ocr_provider"]()
    _furniture_card_payload = dependencies["_furniture_card_payload"]
    _furniture_filter_options = dependencies["_furniture_filter_options"]
    _furniture_payload_cache = dependencies["_furniture_payload_cache"]
    _furniture_payload_item = dependencies["_furniture_payload_item"]
    _get_furniture_by_id = dependencies["_get_furniture_by_id"]
    _get_merged_furniture_by_id = dependencies["_get_merged_furniture_by_id"]
    _get_model_path_for_furniture = dependencies["_get_model_path_for_furniture"]
    _gltf_payload_for_web = dependencies["_gltf_payload_for_web"]
    _image_bytes_from_glb = dependencies["_image_bytes_from_glb"]
    _largest_region_boundary = dependencies["_largest_region_boundary"]
    _model_response_for_merged_furniture = dependencies["_model_response_for_merged_furniture"]
    _parse_glb = dependencies["_parse_glb"]
    _questionnaire_visual_store = dependencies["_questionnaire_visual_store"]
    _region_boundary_by_id = dependencies["_region_boundary_by_id"]
    _regions_boundary = dependencies["_regions_boundary"]
    _style_filter_options = dependencies["_style_filter_options"]
    _style_payloads = dependencies["_style_payloads"]
    _type_options_for = dependencies["_type_options_for"]
    advance_intake = dependencies["advance_intake"]
    analyze_floorplan_image = dependencies["analyze_floorplan_image"]
    build_scene_payload = dependencies["build_scene_payload"]
    build_site_payload = dependencies["build_site_payload"]
    catalog_provider_status = dependencies["catalog_provider_status"]
    cloudfront_required = dependencies["cloudfront_required"]
    confirm_floorplan_analysis = dependencies["confirm_floorplan_analysis"]
    current_profile = dependencies["current_profile"]
    deepcopy = dependencies["deepcopy"]
    estimate_project_cost = dependencies["estimate_project_cost"]
    family_of = dependencies["family_of"]
    floorplan_from_editor_payload = dependencies["floorplan_from_editor_payload"]
    generate_layout = dependencies["generate_layout"]
    get_pipeline = dependencies["get_pipeline"]
    image_manifest_status = dependencies["image_manifest_status"]
    infer_room_requirements = dependencies["infer_room_requirements"]
    json = dependencies["json"]
    load_default_cost_catalog = dependencies["load_default_cost_catalog"]
    load_surface_catalog = dependencies["load_surface_catalog"]
    load_taiwan_style_cards = dependencies["load_taiwan_style_cards"]
    manifest_status = dependencies["manifest_status"]
    parse_selections = dependencies["parse_selections"]
    pipeline_enabled = dependencies["pipeline_enabled"]
    pipeline_status = dependencies["pipeline_status"]
    placement_hints = dependencies["placement_hints"]
    reconcile_room = dependencies["reconcile_room"]
    request_selections = dependencies["request_selections"]
    room_from_payload = dependencies["room_from_payload"]
    start_intake = dependencies["start_intake"]
    start_pipeline = dependencies["start_pipeline"]
    submit_pipeline = dependencies["submit_pipeline"]
    undo_pipeline = dependencies["undo_pipeline"]
    validate_single_placement = dependencies["validate_single_placement"]

    @router.get("/api/floorplan/sample/public")
    def floorplan_sample_public() -> FileResponse:
        if not SAMPLE_FLOORPLAN.is_file():
            raise HTTPException(404, "sample_floorplan_not_found")
        return FileResponse(
            SAMPLE_FLOORPLAN,
            media_type="image/png",
            filename="public_floorplan.png",
        )


    @router.get("/api/site-data")
    def site_data() -> dict:
        payload = dict(build_site_payload())
        payload["furniture"] = []
        payload["featured_models"] = []
        payload["catalog_merge_summary"] = {
            **payload.get("catalog_merge_summary", {}),
            "delivery": "請使用 /api/furniture 分頁取得家具資料。",
        }
        return payload


    def catalog_status() -> dict:
        """Describe active catalog providers without exposing credentials."""
        provider = catalog_provider_status(PROJECT_DIR)
        if provider.get("provider") == "portable_fixture":
            furniture = {
                "provider": "portable_fixture",
                "manifest_ready": True,
                "verified_model_count": int(provider.get("count") or 0),
                "catalog_count": int(provider.get("count") or 0),
                "source_of_truth": "project_authored_fixture",
                "render_mode": "procedural_fixture",
            }
            furniture_images = {
                "provider": "none",
                "manifest_ready": True,
                "verified_item_count": 0,
                "verified_image_count": 0,
                "source_of_truth": "procedural",
            }
        elif provider.get("provider") == "postgres" and provider.get("available"):
            assets = provider.get("assets") or {}
            furniture = {
                "provider": "postgres",
                "manifest_ready": True,
                "verified_model_count": int(assets.get("model_count") or 0),
                "catalog_count": int(provider.get("count") or 0),
                "source_of_truth": "postgresql",
            }
            furniture_images = {
                "provider": "postgres",
                "manifest_ready": True,
                "verified_item_count": int(assets.get("complete_image_item_count") or 0),
                "verified_image_count": sum(
                    int(assets.get(key) or 0)
                    for key in ("front_image_count", "side_image_count", "angle_45_image_count")
                ),
                "source_of_truth": "postgresql",
            }
        else:
            furniture = dict(manifest_status())
            furniture.pop("mode", None)
            furniture_images = image_manifest_status()
        surfaces = load_surface_catalog().get("surfaces") or []
        wall_count = sum("wall" in (item.get("usage") or []) for item in surfaces)
        floor_count = sum("floor" in (item.get("usage") or []) for item in surfaces)
        profile = current_profile()
        return {
            "profile": profile,
            "data_source": (
                "project_authored_fixture"
                if provider.get("provider") == "portable_fixture"
                else provider.get("source_of_truth", "configured_provider")
            ),
            "fixture": provider.get("provider") == "portable_fixture",
            "catalog_provider": provider,
            "furniture": furniture,
            "furniture_images": furniture_images,
            "surfaces": {
                "provider": "local_pending_aws_manifest",
                "wall_count": wall_count,
                "floor_count": floor_count,
            },
            "doors": {
                "provider": "procedural_pending_aws_catalog",
                "catalog_count": 0,
            },
            "style_cards": {
                "provider": "local_allowed",
                "count": len(load_taiwan_style_cards()),
            },
        }


    @router.get("/api/catalog/status")
    def catalog_status_api() -> dict:
        return catalog_status()


    @router.get("/api/home-data")
    def home_data() -> dict:
        summary = _catalog_count_summary()
        return {
            "project": {
                "title": "RoomPilot",
                "subtitle": "AI 室內配置與 3D 場景提案",
            },
            "summary": {
                "total_furniture": summary.get("total_furniture", 0),
                "styled_furniture": summary.get("styled_furniture", 0),
            },
            "styles": _style_payloads()[:6],
            "taiwan_style_cards": load_taiwan_style_cards()[:6],
            "catalog_status": catalog_status(),
        }


    @router.get("/api/styles")
    def styles_data() -> dict:
        summary = _catalog_count_summary()
        return {
            "styles": _style_payloads(),
            "taiwan_style_cards": load_taiwan_style_cards(),
            "surface_catalog": load_surface_catalog(),
            "summary": {
                "total_furniture": summary.get("total_furniture", 0),
                "styled_furniture": summary.get("styled_furniture", 0),
                "fallback_furniture": summary.get("fallback_furniture", 0),
            },
            "style_furniture_counts": summary.get("style_furniture_counts", {}),
            "style_type_counts": summary.get("style_type_counts", {}),
            "catalog_status": catalog_status(),
        }


    @router.get("/api/scene/bootstrap")
    def scene_bootstrap() -> dict:
        return {
            "styles": _style_payloads(),
            "taiwan_style_cards": load_taiwan_style_cards(),
            "surface_catalog": load_surface_catalog(),
            "catalog_status": catalog_status(),
        }


    @router.get("/api/questionnaire/visual-catalog")
    def questionnaire_visual_catalog_api(
        space_type: str | None = Query(None),
        ready_only: bool = Query(False),
    ) -> dict:
        questions = _questionnaire_visual_store().list_questions(
            space_type=space_type,
            ready_only=ready_only,
        )
        return {
            "version": QUESTIONNAIRE_VISUAL_CATALOG["version"],
            "notice_zh": QUESTIONNAIRE_VISUAL_CATALOG["notice_zh"],
            "question_count": QUESTIONNAIRE_VISUAL_CATALOG["question_count"],
            "image_count": QUESTIONNAIRE_VISUAL_CATALOG["image_count"],
            "ready_image_count": sum(
                option["generation_status"] == "ready"
                for question in QUESTIONNAIRE_VISUAL_CATALOG["questions"]
                for option in question["options"]
            ),
            "questions": questions,
        }


    @router.get("/api/questionnaire/visual-images/{image_id}")
    def questionnaire_visual_image_api(image_id: str) -> dict:
        try:
            return _questionnaire_visual_store().get_image(image_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="questionnaire_image_not_found",
            ) from exc


    @router.get("/api/furniture")
    def furniture_catalog(
        style: str | None = Query(None),
        group: str | None = Query(None),
        item_type: str | None = Query(None, alias="type"),
        q: str | None = Query(None),
        page: int = Query(1, ge=1),
        page_size: int = Query(24, ge=1, le=80),
        has_model: bool | None = Query(None),
        detail: str = Query("card"),
        color: str | None = None,
        material: str | None = None,
        size: str | None = None,
    ) -> dict:
        facet_items = _filter_furniture_payload(
            style=style,
            group=group,
            item_type=item_type,
            q=q,
            has_model=has_model,
        )
        filtered = _filter_furniture_payload(
            style=style,
            group=group,
            item_type=item_type,
            q=q,
            has_model=has_model,
            color=color,
            material=material,
            size=size,
        )
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": [
                item if detail == "scene" else _furniture_card_payload(item)
                for item in filtered[start:end]
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next_page": end < total,
            "styles": _style_filter_options(),
            "type_options": _type_options_for(style, group, has_model),
            "category_groups": _category_groups_for(style, has_model),
            "filter_options": _furniture_filter_options(facet_items),
            "catalog_status": catalog_status(),
        }


    def _furniture_detail_payload(furniture_id: str) -> dict:
        item = next(
            (
                candidate
                for candidate in _furniture_payload_cache()
                if str(candidate.get("furniture_id")) == str(furniture_id)
            ),
            None,
        )
        if item is None:
            item = _furniture_payload_item(_get_merged_furniture_by_id(furniture_id))
        payload = dict(item)
        payload.update(
            {
                "merged_furniture_ids": item.get("merged_furniture_ids", []),
                "model_priority_ids": item.get("model_priority_ids", []),
                "catalog_merge_key": item.get("catalog_merge_key"),
                "source_count": item.get("source_count"),
            }
        )
        return payload


    @router.post("/api/agent/intake/start")
    async def agent_intake_start(payload: dict | None = None) -> dict:
        """Start the Agent-ready intake contract without calling an LLM yet."""
        payload = payload or {}
        return start_intake(str(payload.get("session_id") or "roompilot-local"))


    @router.post("/api/agent/intake/answer")
    async def agent_intake_answer(payload: dict) -> dict:
        """Advance one guided intake turn; future LLM adapters keep this shape."""
        step = str(payload.get("step") or "")
        answer = str(payload.get("answer") or "").strip()
        if not step or not answer:
            raise HTTPException(status_code=422, detail="step 與 answer 皆為必要欄位。")
        return advance_intake(
            session_id=str(payload.get("session_id") or "roompilot-local"),
            step=step,
            answer=answer,
            brief=payload.get("client_brief"),
        )


    def _normalize_selection_offers(raw_offers: object) -> dict[str, list[dict]]:
        if not isinstance(raw_offers, dict):
            return {}
        offers: dict[str, list[dict]] = {}
        for room_id, raw_items in raw_offers.items():
            if not isinstance(raw_items, list):
                continue
            normalized_items: list[dict] = []
            for index, raw_item in enumerate(raw_items):
                if not isinstance(raw_item, dict):
                    continue
                item_type = str(raw_item.get("normalized_type") or raw_item.get("type") or "")
                variant_id = str(raw_item.get("variant_id") or raw_item.get("variantId") or "standard")
                furniture_id = str(
                    raw_item.get("furniture_id")
                    or raw_item.get("id")
                    or f"{room_id}:{item_type}:{variant_id}:{index + 1}"
                )
                if not item_type or not furniture_id:
                    continue
                item = dict(raw_item)
                item["furniture_id"] = furniture_id
                item["normalized_type"] = item_type
                item["variant_id"] = variant_id
                item["selection_source"] = str(item.get("selection_source") or "local_rules")
                normalized_items.append(item)
            offers[str(room_id)] = normalized_items
        return offers


    def _local_selection_raw(rooms: list[dict], offers: dict[str, list[dict]]) -> dict:
        selections: list[dict] = []
        for room in rooms:
            room_id = str(room.get("room_id") or room.get("id") or "")
            used_families: set[str] = set()
            items: list[dict] = []
            for item in offers.get(room_id, []):
                family = family_of(item.get("normalized_type"))
                if family in used_families:
                    continue
                used_families.add(family)
                try:
                    count = int(item.get("count") or 1)
                except (TypeError, ValueError):
                    count = 1
                items.append({
                    "furniture_id": item.get("furniture_id"),
                    "count": max(1, min(6, count)),
                })
            if items:
                selections.append({"room_id": room_id, "items": items})
        return {"selections": selections}


    def _selection_response(
        selected: dict[str, list],
        *,
        source: str,
        model: str | None = None,
        warnings: list[str] | None = None,
    ) -> dict:
        return {
            "source": source,
            "model": model,
            "warnings": warnings or [],
            "rooms": [
                {
                    "room_id": room_id,
                    "items": [
                        {
                            **entry.item,
                            "count": entry.count,
                            "selection_source": entry.item.get("selection_source") or source,
                        }
                        for entry in entries
                    ],
                }
                for room_id, entries in selected.items()
            ],
        }


    @router.post("/api/agent/furniture/select")
    async def agent_furniture_select(payload: dict) -> dict:
        """Server-side furniture selection gate for Yen selection discipline."""
        raw_rooms = payload.get("rooms") or []
        if not isinstance(raw_rooms, list):
            raise HTTPException(status_code=422, detail="rooms must be a list")
        rooms = []
        for room in raw_rooms:
            if not isinstance(room, dict):
                continue
            room_type = str(room.get("room_type") or room.get("type") or "")
            if room_type in {"default", "unknown", "other"}:
                room_type = ""
            rooms.append({
                **room,
                "room_id": str(room.get("room_id") or room.get("id") or ""),
                "room_type": room_type,
            })
        offers = _normalize_selection_offers(payload.get("offers"))
        style_id = payload.get("style_id")
        context = payload.get("context") if isinstance(payload.get("context"), dict) else None
        llm_selection = payload.get("llm_selection")
        warnings: list[str] = []

        if isinstance(llm_selection, dict):
            try:
                selected, model = request_selections(
                    rooms,
                    offers,
                    str(style_id) if style_id else None,
                    complete=lambda _messages: ("payload/llm_selection", llm_selection),
                    context=context,
                )
                return _selection_response(selected, source="openrouter", model=model)
            except (SelectionParseError, SelectionUnavailableError) as exc:
                warnings.append(f"LLM 選擇未通過規則驗證，已改用本地規則：{exc}")

        try:
            selected = parse_selections(_local_selection_raw(rooms, offers), rooms, offers)
            return _selection_response(selected, source="local_rules", warnings=warnings)
        except SelectionParseError as exc:
            warnings.append(f"本地規則無法完整驗證候選家具，已保留第一批候選：{exc}")
            return {
                "source": "local_rules_unvalidated",
                "model": None,
                "warnings": warnings,
                "rooms": [
                    {
                        "room_id": room_id,
                        "items": [
                            {
                                **item,
                                "count": int(item.get("count") or 1),
                                "selection_source": item.get("selection_source") or "local_rules_unvalidated",
                            }
                            for item in items[:8]
                        ],
                    }
                    for room_id, items in offers.items()
                    if items
                ],
            }


    @router.get("/api/agent/pipeline/status")
    def agent_pipeline_status_route() -> dict:
        """MasterAgent 並存管線的開關與 gateway 狀態（永遠可查，即使未啟用）。"""
        return pipeline_status()


    def _require_pipeline_enabled() -> None:
        if not pipeline_enabled():
            raise HTTPException(
                status_code=404,
                detail="Agent 管線未啟用；設定環境變數 ROOMPILOT_AGENT_PIPELINE=1 後重啟服務。",
            )


    @router.post("/api/agent/pipeline/{project_id}/start")
    async def agent_pipeline_start_route(project_id: str, payload: dict) -> dict:
        """並存管線：載入室內架構與規則，進入等待問卷狀態。不影響正式 step 6。"""
        _require_pipeline_enabled()
        layout_json = payload.get("layout_json") or payload.get("layout")
        if not isinstance(layout_json, dict):
            raise HTTPException(
                status_code=422,
                detail="layout_json 為必要欄位（辨識步驟輸出的室內架構）。",
            )
        rules_json = payload.get("rules_json") if isinstance(payload.get("rules_json"), dict) else None
        try:
            return start_pipeline(
                _project_store().runtime_dir, PROJECT_DIR, project_id, layout_json, rules_json
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))


    @router.post("/api/agent/pipeline/{project_id}/submit")
    async def agent_pipeline_submit_route(project_id: str, payload: dict | None = None) -> dict:
        """並存管線：在目前 HITL 決策點提交輸入並推進（問卷→A/B 擺放+驗證→…）。"""
        _require_pipeline_enabled()
        try:
            return submit_pipeline(
                _project_store().runtime_dir, PROJECT_DIR, project_id, payload or {}
            )
        except PipelineNotStarted as exc:
            raise HTTPException(status_code=409, detail=str(exc))


    @router.post("/api/agent/pipeline/{project_id}/undo")
    async def agent_pipeline_undo_route(project_id: str) -> dict:
        """並存管線：回復上一次 submit 之前的完整狀態。"""
        _require_pipeline_enabled()
        try:
            return undo_pipeline(_project_store().runtime_dir, PROJECT_DIR, project_id)
        except PipelineNotStarted as exc:
            raise HTTPException(status_code=409, detail=str(exc))


    @router.get("/api/agent/pipeline/{project_id}")
    def agent_pipeline_get_route(project_id: str) -> dict:
        """並存管線：查詢目前暫停點、期望輸入與最近一次階段產物。"""
        _require_pipeline_enabled()
        try:
            return get_pipeline(_project_store().runtime_dir, PROJECT_DIR, project_id)
        except PipelineNotStarted as exc:
            raise HTTPException(status_code=404, detail=str(exc))


    @router.post("/api/agent/pipeline/reconcile")
    async def agent_pipeline_reconcile_route(payload: dict) -> dict:
        """對帳：同一批 step6 選定家具，比對 step6 擺放 vs agent 管線擺放的覆蓋率＋合法性。"""
        _require_pipeline_enabled()
        room_id = str(payload.get("room_id") or "room")
        try:
            width_cm = float(payload.get("width_cm"))
            depth_cm = float(payload.get("depth_cm"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="width_cm 與 depth_cm 為必要數值（公分）。")
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise HTTPException(
                status_code=422,
                detail="items 為必要（step6 選定的家具清單，server 物件格式）。",
            )
        try:
            return reconcile_room(room_id, width_cm, depth_cm, items)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))


    @router.post("/api/scene/generate")
    async def generate_scene(payload: dict) -> dict:
        site_payload = build_site_payload()

        client_brief = payload.get("client_brief") or {}
        brief_space = client_brief.get("space") or {}
        brief_style = client_brief.get("style") or {}
        brief_occupants = client_brief.get("occupants") or {}
        test2_questionnaire = payload.get("questionnaire") or {}

        questionnaire = {
            "space_type": payload.get("space_type") or brief_space.get("type") or "living_room",
            "style_preference": payload.get("style_preference") or (brief_style.get("preferred") or ["auto"])[0],
            "style_card_id": payload.get("style_card_id"),
            "required_furniture": payload.get("required_furniture", []),
            "selected_furniture": payload.get("selected_furniture", []),
            "selected_furniture_exact": payload.get("selected_furniture_exact") is True,
            "custom_furniture": payload.get("custom_furniture", []),
            "preferred_colors": payload.get("preferred_colors") or brief_style.get("colors", []),
            "custom_colors": payload.get("custom_colors", []),
            "personal_notes": payload.get("personal_notes", ""),
            "test2_questionnaire": test2_questionnaire,
            "keep_window_clear": bool(payload.get("keep_window_clear", "keep_window_clear" in client_brief.get("constraints", []))),
            "keep_door_clear": bool(payload.get("keep_door_clear", "keep_door_clear" in client_brief.get("constraints", []))),
            "need_storage": bool(payload.get("need_storage", "storage" in client_brief.get("needs", []))),
            "prefer_low_saturation": bool(payload.get("prefer_low_saturation", "low_saturation" in brief_style.get("colors", []))),
            "client_brief": client_brief,
            "occupants": brief_occupants,
            "preferred_materials": brief_style.get("materials", []),
            "floorplan_filename": payload.get("floorplan_filename"),
            "floorplan_dxf_text": payload.get("floorplan_dxf_text"),
            "layout_json": payload.get("layout_json"),
            "floorplan_editor": payload.get("floorplan_editor"),
            "wall_option": payload.get("wall_option", "auto"),
            "floor_option": payload.get("floor_option", "auto"),
            "furniture_random_seed": payload.get("furniture_random_seed"),
        }

        # 方案 A/B 白模生成走各自的 variant；不帶就預設 A（單方案專案不受影響）。
        placement_variant = str(payload.get("placement_variant") or "A").upper()
        if placement_variant not in {"A", "B"}:
            placement_variant = "A"
        scene_payload = build_scene_payload(
            site_payload=site_payload,
            questionnaire=questionnaire,
            floorplan_path=payload.get("floorplan_filename"),
            room_width_cm=float(payload.get("room_width_cm") or brief_space.get("width_cm") or 420),
            room_depth_cm=float(payload.get("room_depth_cm") or brief_space.get("depth_cm") or 360),
            placement_variant=placement_variant,
        )
        return {
            **scene_payload,
            "scene_json": deepcopy(scene_payload),
        }


    @router.post("/api/scene/layout")
    async def scene_layout(payload: dict) -> dict:
        """前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。

        傳 floorplan(含 wall_segments)可重建 DXF 房間形狀;
        scene_objects 帶 position_locked 的項目(使用者拖曳過)位置仍合法就不重排。
        """
        objects = payload.get("scene_objects", [])
        editor_floorplan = payload.get("floorplan_editor")
        if isinstance(editor_floorplan, dict) and editor_floorplan:
            floorplan, room = floorplan_from_editor_payload(editor_floorplan)
        else:
            floorplan = payload.get("floorplan") or {}
            room = room_from_payload(floorplan)
        placement_room_id = payload.get("placement_room_id")
        placement_variant = str(payload.get("placement_variant") or "A").upper()
        if placement_variant not in {"A", "B"}:
            placement_variant = "A"
        # 指定房間 → 該房邊界;整屋呼叫(最終確認驗證、全屋鎖定覆核)→ 所有房
        # 的聯集。柵格對「格外」一律視為阻擋,聯集才不會把最大房以外的家具
        # 全數誤殺;無房型資料才退回最大區域(手動矩形模式)。
        place_boundary = (
            _region_boundary_by_id(floorplan, room, placement_room_id)
            or _regions_boundary(floorplan, room)
            or _largest_region_boundary(floorplan, room)
        )
        # 單房呼叫不得動別房家具:標了別房 id 的一律原樣通過,不進重排。
        # 單房柵格對房外一律視為阻擋,整屋清單塞進來會讓別房鎖定件檢查失敗、
        # 掉進自動重排 —— 無論哪個前端版本怎麼呼叫,伺服器都不再讓這發生。
        passthrough: list[dict] = []
        if placement_room_id:
            target_room_id = str(placement_room_id)
            active_objects: list[dict] = []
            for item in objects:
                assigned = str(
                    item.get("placement_room_id") or item.get("auto_decor_room_id") or ""
                )
                if assigned and assigned != target_room_id:
                    passthrough.append(item)
                else:
                    active_objects.append(item)
            objects = active_objects
        return {
            "floorplan": floorplan,
            "scene_objects": [*passthrough, *generate_layout(
                room.width,
                room.depth,
                objects,
                room=room,
                regions_boundary=_regions_boundary(floorplan, room),
                place_boundary=place_boundary,
                floorplan=floorplan,
                placement_variant=placement_variant,
                # 重排/替換/新增/逐房操作也要有 agent 擺位紀律:沒有 hints 時
                # generate_layout 不登記 neighbors,成組配對(電視櫃對面、茶几
                # 沙發前)與自由座椅後置整條路是死的 —— 首次產生正確,一按
                # 重排就退化(feedback:躺椅回到沙發前、茶几被擠走)。
                hints=placement_hints(objects),
                # 最終確認(進入即時寫實)只驗不排:信任已鎖定的配置,座標照舊,
                # 避免嚴格重排把合法家具塌成 (0,0) 並擋住進入下一步。
                validate_only=bool(payload.get("validate_only")),
            )]
        }


    @router.post("/api/scene/validate")
    async def scene_validate(payload: dict) -> dict:
        """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
        editor_floorplan = payload.get("floorplan_editor")
        floorplan = payload.get("floorplan")
        if isinstance(editor_floorplan, dict) and editor_floorplan:
            floorplan, _ = floorplan_from_editor_payload(editor_floorplan)
        return validate_single_placement(
            floorplan,
            payload.get("item") or {},
            payload.get("others") or [],
        )


    @router.get("/api/furniture/{furniture_id}/model")
    def furniture_model(furniture_id: str):
        furniture = _get_merged_furniture_by_id(furniture_id)
        direct_url = str(furniture.get("model_url") or "").strip()
        if direct_url.startswith(("https://", "http://")):
            return RedirectResponse(direct_url, status_code=307)
        return _model_response_for_merged_furniture(furniture)


    @router.get("/api/furniture/{furniture_id}/model.gltf")
    def furniture_model_gltf(furniture_id: str) -> JSONResponse:
        if cloudfront_required():
            raise HTTPException(410, "CloudFront 模式不提供本機 glTF 拆解端點。")
        furniture = _get_furniture_by_id(furniture_id)
        model_path_text = _get_model_path_for_furniture(furniture)
        return JSONResponse(_gltf_payload_for_web(model_path_text, furniture_id))


    @router.get("/api/furniture/{furniture_id}/buffer.bin")
    def furniture_model_buffer(furniture_id: str) -> Response:
        if cloudfront_required():
            raise HTTPException(410, "CloudFront 模式不提供本機 GLB buffer。")
        furniture = _get_furniture_by_id(furniture_id)
        model_path_text = _get_model_path_for_furniture(furniture)
        _, binary_payload = _parse_glb(model_path_text)
        return Response(content=binary_payload, media_type="application/octet-stream")


    @router.get("/api/furniture/{furniture_id}/images/{image_index}")
    def furniture_model_image(furniture_id: str, image_index: int) -> Response:
        if cloudfront_required():
            raise HTTPException(410, "CloudFront 模式不提供本機 GLB 圖片。")
        furniture = _get_furniture_by_id(furniture_id)
        model_path_text = _get_model_path_for_furniture(furniture)
        image_bytes, mime_type = _image_bytes_from_glb(model_path_text, image_index)
        return Response(content=image_bytes, media_type=mime_type)


    def _floorplan_json_field(raw: str | None, field: str, default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"invalid_{field}_json") from exc


    def _layout_json_from_analysis(analysis: dict) -> dict:
        floorplan = analysis.get("floorplan")
        if isinstance(floorplan, dict):
            return floorplan
        return analysis


    @router.post("/api/floorplan/analyze")
    async def floorplan_analyze(
        file: UploadFile = File(...),
        calibration_json: str | None = Form(None),
        ocr_json: str | None = Form(None),
        geometry_json: str | None = Form(None),
        observed_utilities_json: str | None = Form(None),
        brief_json: str | None = Form(None),
    ):
        """PNG/JPG → 尺度、幾何、房間與初步機電需求；不確定時不得進設計。"""
        extension = Path(file.filename or "").suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg"}:
            raise HTTPException(415, "floorplan_image_required")
        data = await file.read()
        calibration = _floorplan_json_field(calibration_json, "calibration", None)
        observations = _floorplan_json_field(ocr_json, "ocr", [])
        geometry = _floorplan_json_field(geometry_json, "geometry", [])
        observed_utilities = _floorplan_json_field(observed_utilities_json, "observed_utilities", [])
        brief = _floorplan_json_field(brief_json, "brief", {})
        provider = _floorplan_ocr_provider()
        try:
            analysis = analyze_floorplan_image(
                data,
                filename=file.filename or "floorplan.png",
                calibration_hint=calibration,
                ocr_observations=observations,
                ocr_provider=provider,
                geometry_observations=geometry,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        analysis["observed_utilities"] = observed_utilities
        analysis["requirement_brief"] = brief
        layout_json = _layout_json_from_analysis(analysis)
        return {
            "analysis": analysis,
            "layout_json": layout_json,
            "requirements": infer_room_requirements(analysis, brief),
            "geometry_engine": "cody" if not geometry else "manual",
            "ocr_provider": "provided_or_reference_semantics",
        }


    @router.post("/api/floorplan/confirm")
    def floorplan_confirm(payload: dict):
        """套用使用者確認／修正並輸出可供既有 3D 與家具引擎使用的契約。"""
        analysis = payload.get("analysis") if isinstance(payload, dict) else None
        corrections = payload.get("corrections") if isinstance(payload, dict) else None
        if not isinstance(analysis, dict):
            raise HTTPException(422, "analysis_required")
        try:
            return confirm_floorplan_analysis(analysis, corrections)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


    @router.post("/api/cost/estimate")
    def cost_estimate(payload: dict):
        """以版控內的台灣公開網路行情，產生可追溯的概念工程概算。"""
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise HTTPException(422, "cost_items_required")
        try:
            return estimate_project_cost(items, catalog=load_default_cost_catalog())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


    @router.get("/api/furniture/{furniture_id}")
    def furniture_detail(furniture_id: str) -> dict:
        return _furniture_detail_payload(furniture_id)

    return router, {
        "floorplan_sample_public": floorplan_sample_public,
        "site_data": site_data,
        "catalog_status": catalog_status,
        "catalog_status_api": catalog_status_api,
        "home_data": home_data,
        "styles_data": styles_data,
        "scene_bootstrap": scene_bootstrap,
        "questionnaire_visual_catalog_api": questionnaire_visual_catalog_api,
        "questionnaire_visual_image_api": questionnaire_visual_image_api,
        "furniture_catalog": furniture_catalog,
        "_furniture_detail_payload": _furniture_detail_payload,
        "agent_intake_start": agent_intake_start,
        "agent_intake_answer": agent_intake_answer,
        "_normalize_selection_offers": _normalize_selection_offers,
        "_local_selection_raw": _local_selection_raw,
        "_selection_response": _selection_response,
        "agent_furniture_select": agent_furniture_select,
        "agent_pipeline_status_route": agent_pipeline_status_route,
        "_require_pipeline_enabled": _require_pipeline_enabled,
        "agent_pipeline_start_route": agent_pipeline_start_route,
        "agent_pipeline_submit_route": agent_pipeline_submit_route,
        "agent_pipeline_undo_route": agent_pipeline_undo_route,
        "agent_pipeline_get_route": agent_pipeline_get_route,
        "agent_pipeline_reconcile_route": agent_pipeline_reconcile_route,
        "generate_scene": generate_scene,
        "scene_layout": scene_layout,
        "scene_validate": scene_validate,
        "furniture_model": furniture_model,
        "furniture_model_gltf": furniture_model_gltf,
        "furniture_model_buffer": furniture_model_buffer,
        "furniture_model_image": furniture_model_image,
        "_floorplan_json_field": _floorplan_json_field,
        "_layout_json_from_analysis": _layout_json_from_analysis,
        "floorplan_analyze": floorplan_analyze,
        "floorplan_confirm": floorplan_confirm,
        "cost_estimate": cost_estimate,
        "furniture_detail": furniture_detail,
    }
