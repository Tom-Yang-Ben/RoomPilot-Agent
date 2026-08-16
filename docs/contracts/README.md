# RoomPilot 公開契約索引

公開 runtime 的核心契約：

- [layout_json／scene_json 邊界](LAYOUT_SCENE_BOUNDARY_CONTRACT.md)
- [project schema 與可回復遷移](PROJECT_SCHEMA_CONTRACT.md)
- [Step 4 牆體編輯](STEP4_WALL_EDITING_CONTRACT.md)
- [家具引擎逐房需求](FURNITURE_ENGINE_ROOM_REQUIREMENTS_CONTRACT.md)
- [家具工程規則](FURNITURE_ENGINEERING_RULES.md)
- [layout evaluation schema](LAYOUT_EVALUATION_SCHEMA.md)
- [遠端渲染](REMOTE_RENDER_CONTRACT.md)
- [AI render／OpenRouter](AI_RENDER_OPENROUTER_CONTRACT.md)

舊 PostgreSQL phase、固定 catalog 筆數、私有 embedding 與資料交付 handoff 已退出公開 repository。公開 profile、schema 與操作方式以 [README](../../README.md)、[Full profile](../FULL_PROFILE.md)、`pyproject.toml`、`docker_postgresql/init/001_roompilot.sql` 及目前測試為準。

共享契約變更須同時驗證 producer 與 consumer。
