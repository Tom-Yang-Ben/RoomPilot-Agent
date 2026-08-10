"""3D 場景生命週期契約：viewer 常駐、家具增刪走增量操作、GLB 只載一次。

背景：六個 viewer 只在頁面載入時建一次，但過去唯一的內容 API loadScene 每次
清空全部家具＋重建房殼＋重抓所有 GLB，家具增刪也整包重跑。本檔鎖住：

- GLB 頁面級快取（同 model_url 只下載解析一次；快取資產清場時不得 dispose）。
- 增量 API（addObject/removeObject/updateObject）存在，且家具新增/刪除/
  替換/單件重擺四條路都改走增量，不再整包 loadScene。
- 內容未變（lastSceneKey）與房殼未變（lastShellKey）的跳過鍵。
- 第 6 步 A/B 方案 3D 預覽在離屏縮圖 viewer 背景建立，不得動前景
  whiteViewer 場景；方案內容變更與完成選擇時清除預覽快取。
"""
from pathlib import Path
import re
import subprocess

STATIC = Path(__file__).resolve().parents[1] / "backend" / "server" / "static"


def _function_body(source: str, header: str) -> str:
    start = source.index(header)
    tail = source[start + len(header):]
    next_match = re.search(r"\n(?:async )?function \w+", tail)
    end = next_match.start() if next_match else len(tail)
    return source[start:start + len(header) + end]


def test_scene_viewer_parses_as_an_es_module(tmp_path) -> None:
    module_file = tmp_path / "scene_viewer.mjs"
    module_file.write_bytes((STATIC / "scene_viewer.js").read_bytes())
    result = subprocess.run(
        ["node", "--check", str(module_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_glb_models_load_once_and_cached_assets_survive_scene_clear() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "const gltfPromiseCache = new Map();" in viewer
    assert "loadGltfCached(loader, item.model_url)" in viewer
    assert "cloneCachedGltfScene(gltf)" in viewer
    # 家具載入不得繞過快取直接抓網路
    assert "loader.loadAsync(item.model_url)" not in viewer
    # 清場時共用資產（幾何/貼圖）由快取持有，不得 dispose
    assert "if (object.userData?.roompilotCachedAsset) return;" in viewer


def test_viewer_exposes_incremental_furniture_operations() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "async function addObject(item)" in viewer
    assert "function removeObject(furnitureId)" in viewer
    assert "async function updateObject(item)" in viewer
    assert "function renumberFurnitureWrappers()" in viewer
    for exported in ("addObject,", "removeObject,", "updateObject,"):
        assert exported in viewer.split("return {", 1)[-1] or f"\n    {exported}" in viewer


def test_viewer_exposes_update_room_surfaces_used_by_material_flow() -> None:
    """第 6→7 步材質狀態機呼叫 whiteViewer.updateRoomSurfaces()（bella-new 拼接帶入）。
    viewer 若未匯出此方法，confirmWhiteModel 會擲
    "updateRoomSurfaces is not a function" → 未捕捉的 promise → 「確認家具配置並
    調整材質」按鈕點了沒反應。回歸守門:呼叫端存在,且 viewer 公開 API 真的有它。"""
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "whiteViewer.updateRoomSurfaces(" in source
    api = viewer.split("\n  return {", 1)[-1]
    assert "\n    updateRoomSurfaces,\n" in api
    # A material edit must NOT do a full loadScene (which re-clones every GLB and
    # caused the per-material jank); it rebuilds only the shell via createRoom.
    surfaces_fn = viewer.split("function updateRoomSurfaces(sceneData) {", 1)[1].split(
        "\n  }", 1
    )[0]
    assert "createRoom(lastWorldSceneData)" in surfaces_fn
    assert "loadScene(" not in surfaces_fn
    assert "clearGroup(furnitureGroup)" not in surfaces_fn


def test_furniture_edits_use_incremental_operations_not_full_reload() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    delete_body = _function_body(source, "async function deleteSelectedSceneFurniture()")
    assert "whiteViewer.removeObject(" in delete_body
    assert "realisticViewer.removeObject(" in delete_body

    add_body = _function_body(source, "function addSceneFurniture(furnitureId)")
    assert "whiteViewer.addObject(candidate)" in add_body

    replace_body = _function_body(source, "async function replaceSceneFurniture(furnitureId)")
    assert "whiteViewer.updateObject(current)" in replace_body

    reflow_body = _function_body(
        source, "async function reflowSingleConfigurationFurniture(furnitureId)",
    )
    assert "whiteViewer.updateObject(sceneObject)" in reflow_body
    assert "whiteViewer.loadScene(" not in reflow_body


def test_load_scene_skips_unchanged_content_and_unchanged_shell() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "let lastSceneKey = null;" in viewer
    assert "let lastShellKey = null;" in viewer
    # 房殼鍵＝去除家具後的場景資料；未變時不重建房殼
    assert "JSON.stringify({ ...lastWorldSceneData, scene_objects: null })" in viewer


def test_gpu_memory_stays_bounded_against_context_loss() -> None:
    """Shader Error 1282／白畫面的根因是 WebGL context 遺失：GPU 用量必須有上界。

    - GLB 快取有 LRU 上限，淘汰時真正釋放幾何/貼圖（clone 由 three 惰性重傳）。
    - 隱藏面板與離屏縮圖臺不每幀渲染（七個 renderer 全速跑會撐爆 GPU）。
    - 離屏縮圖 viewer 拍完 A/B 預覽即整包卸載，不滯留整棟場景。
    """
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "const GLTF_CACHE_LIMIT" in viewer
    assert "function disposeGltfResources(" in viewer
    assert "oldest.then(disposeGltfResources)" in viewer
    assert "if (container.offsetParent === null) return;" in viewer
    assert "function unloadScene()" in viewer

    preview_body = _function_body(source, "async function ensureRoomScheme3dPreviews()")
    assert "glbThumbnailViewer.unloadScene()" in preview_body


def test_room_scheme_previews_build_offscreen_and_get_cleaned_up() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    preview_body = _function_body(source, "async function ensureRoomScheme3dPreviews()")
    assert "glbThumbnailViewer.loadScene(" in preview_body
    assert "glbThumbnailSequence" in preview_body           # 與 GLB 縮圖共用序列佇列
    assert "whiteViewer.loadScene(" not in preview_body     # 前景場景不得被預覽借用

    sync_body = _function_body(source, "function syncFurnitureInventoryAcrossSchemes()")
    assert "roomSchemePreviewCache.clear()" in sync_body    # 方案變更 → 舊預覽作廢

    complete_body = _function_body(source, "async function completeRoomSchemeSelection()")
    assert "roomSchemePreviewCache.clear()" in complete_body  # 進下一流程 → 清除預覽
