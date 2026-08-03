"""彩色門/窗輸出閘（2026-08-02 使用者裁定）。

彩門 P 0.38/R 0.47、彩窗 P 61/R 42——低於可用線的門窗畫進交付物
反而製造人工刪除成本，裁定：彩色管線的門/窗**輸出**預設關閉、由後端
自行補建；偵測本身保留（窗偵測餵著分割封口/比例尺，不可拔）。
灰階（門 P 0.85、窗 P 98）不受影響。
"""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "backend", "floorplan"))

import floorplan2dxf_color as fp_c
import floorplan2room as f2r


def test_config_default_suppresses_color_openings(tmp_path):
    """config 未設定 emit_openings → 預設 False（彩色不發射門窗）。"""
    ini = tmp_path / "c.ini"
    ini.write_text("[dxf]\ninput=x.png\n", encoding="utf-8")
    cfg = fp_c.load_config(str(ini))
    assert cfg.emit_openings is False


def test_config_can_reenable_openings(tmp_path):
    ini = tmp_path / "c.ini"
    ini.write_text("[dxf]\ninput=x.png\nemit_openings=true\n", encoding="utf-8")
    cfg = fp_c.load_config(str(ini))
    assert cfg.emit_openings is True


def test_openings_for_output_gates_on_flag(tmp_path):
    """DXF 發射用 helper：旗標關 → 空清單（牆照畫、窗不畫）。"""
    ini = tmp_path / "c.ini"
    ini.write_text("[dxf]\ninput=x.png\n", encoding="utf-8")
    cfg = fp_c.load_config(str(ini))
    wins = [("h", 0.0, 0.0, 10.0, 2.0)]
    assert fp_c.openings_for_output(cfg, wins) == []
    ini.write_text("[dxf]\ninput=x.png\nemit_openings=on\n", encoding="utf-8")
    cfg_on = fp_c.load_config(str(ini))
    assert fp_c.openings_for_output(cfg_on, wins) == wins


def _min_det():
    return {"img_w": 100, "img_h": 80, "cm": 1.0, "scale_info": {},
            "rects": [], "wins": [("h", 0, 0, 10, 2)]}


_ZONES = [([(0, 0), (10, 0), (10, 5), (0, 5)], (5.0, 2.5, 90.0))]


def test_rooms_json_color_doors_suppressed(tmp_path):
    p = tmp_path / "r.json"
    f2r.write_rooms_json(str(p), _min_det(), [], _ZONES, [],
                         is_color=True, colorful=0.5, emit_openings=False)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["doors"] == []
    assert data["openings_suppressed"] is True


def test_rooms_json_gray_doors_kept(tmp_path):
    """灰階門走 zones 路 P 0.85/R 0.71，照常發射。"""
    p = tmp_path / "r.json"
    f2r.write_rooms_json(str(p), _min_det(), [], _ZONES, [],
                         is_color=False, colorful=0.0, emit_openings=True)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert len(data["doors"]) == 1
    assert data["openings_suppressed"] is False
