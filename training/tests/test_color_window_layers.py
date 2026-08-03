"""color 管線窗層萃取（color_window_layers）——detect_color 補窗封口的地基。

floor_09 實案：detect_color 沒接窗偵測（wins=[]、thin=None），外牆窗帶
是灌水的洞，左半客廳/主臥漏到影像邊界被室外過濾整片剪掉（命中 1/7）。
run() 色彩分支本來就有這段萃取，抽成共用函式讓 detect_color 同源取用。"""
import numpy as np

import floorplan2dxf_color as fp_c


def _scene():
    """100x100 白底：一條中性灰細線（窗線）＋一條彩色線（家具）＋一段實牆。"""
    bgr = np.full((100, 100, 3), 250, np.uint8)
    bgr[20:80, 30:33] = 190                      # 中性灰細線（窗）
    bgr[20:80, 60:63] = (40, 60, 200)            # 彩色線（家具，chroma 高）
    bgr[90:96, 10:90] = 10                       # 實牆（深黑）
    bw = np.zeros((100, 100), np.uint8)
    bw[90:96, 10:90] = 255                       # 牆二值層只有實牆
    return bgr, bw


def test_thin_keeps_neutral_line_only():
    bgr, bw = _scene()
    orig_win, soft, thin = fp_c.color_window_layers(bgr, bw, bw)
    assert thin[50, 31] > 0, "中性灰窗線應留在細線層"
    assert thin[50, 61] == 0, "彩色家具線不得進細線層"
    assert thin[92, 50] == 0, "牆體(膨脹後)應從細線層扣掉"


def test_layers_match_bw_shape_when_upscaled():
    # 彩圖管線 2x 放大：bw 比 bgr 大一倍，各層須輸出 bw 尺寸
    bgr, bw = _scene()
    bw2 = np.zeros((200, 200), np.uint8)
    bw2[180:192, 20:180] = 255
    orig_win, soft, thin = fp_c.color_window_layers(bgr, bw2, bw2)
    assert orig_win.shape == soft.shape == thin.shape == (200, 200)
    assert thin[100, 62] > 0, "2x 座標下窗線仍應留在細線層"
