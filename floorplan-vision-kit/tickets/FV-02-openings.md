# FV-02 牆、門、窗

- Seam：`analyze_floorplan_image`
- 自動來源：`opencv_geometry`；人工確認：`confirmed_geometry`。
- 門窗必須包含公尺端點、寬度、來源與 confidence。
- 自動結果不確定時由 confirm corrections 覆蓋。
- 證據：synthetic wall／door／window 測試。
