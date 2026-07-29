"""ccmodel — CubiCasa5k 模型定義的推論期副本（floortrans.models 子集）。

**為什麼存在**：推論鏈（floorplan2room → ensure_cc_masks → infer_cubicasa）
原本要 `sys.path` 掛 `training/CubiCasa5k` 再 `os.chdir` 進去才跑得動，
等於把「訓練材料目錄」變成部署必要條件。本套件把推論真正需要的東西
（模型架構，兩支純 PyTorch 檔）搬進 backend/floorplan/，training/ 從此
只放訓練材料，交付給 main 的推論鏈不再踩在 training/ 上。

**為什麼不叫 floortrans**：`eval_rooms_cc.py` 等研發工具仍需原版的
`floortrans.loaders`（GT 解析），同名會在 sys.path 上互相遮蔽。

**不含 model_1427.pth（70MB）**：那是 MPII 姿態估計預訓練權重，只在
`init_weights()`（訓練起點）用；推論期建完架構後隨即被 v5 微調權重的
`load_state_dict` 全部覆蓋，載了 100% 是浪費。要訓練請用原版
`training/CubiCasa5k/`。

上游授權 CC BY-NC（禁商用），與 v5 權重的授權閘門一致。
"""
from .hg_furukawa_original import hg_furukawa_original


def get_model(name, n_classes=None, version=None, pretrained=False):
    """同上游 floortrans.models.get_model，但 `pretrained` 預設 False。

    上游無條件呼叫 `init_weights()`（讀寫死相對路徑的 model_1427.pth，
    故需 chdir）。推論不需要那份權重，預設關閉即可拿掉整條 chdir 依賴。"""
    if name != 'hg_furukawa_original':
        raise ValueError('Model {} not available'.format(name))
    model = hg_furukawa_original(n_classes=n_classes)
    if pretrained:
        model.init_weights()
    return model
