# RoomPilot 公開契約索引

公開 runtime 的核心契約：

- [layout_json／scene_json 邊界](LAYOUT_SCENE_BOUNDARY_CONTRACT.md)
- [Step 4 牆體編輯](STEP4_WALL_EDITING_CONTRACT.md)
- [家具引擎逐房需求](FURNITURE_ENGINE_ROOM_REQUIREMENTS_CONTRACT.md)
- [家具工程規則](FURNITURE_ENGINEERING_RULES.md)
- [layout evaluation schema](LAYOUT_EVALUATION_SCHEMA.md)
- [遠端渲染](REMOTE_RENDER_CONTRACT.md)
- [AI render／OpenRouter](AI_RENDER_OPENROUTER_CONTRACT.md)

PostgreSQL Phase 1–5、舊 catalog delivery、舊 embedding 數量與歷史 handoff 文件保留作設計背景，但不再是公開資料集、啟動指令或驗收數量的來源。公開 profile、schema 與操作方式以 [README](../../README.md)、[Full profile](../FULL_PROFILE.md)、`pyproject.toml`、`docker_postgresql/init/001_roompilot.sql` 及目前測試為準。

共享契約變更須同時驗證 producer 與 consumer；歷史文件若與上述現行來源衝突，一律以現行來源為準。
