# 基線來源與授權（2026-10-29 核對）

- [PhysioNet EEGMMIDB 1.0.0](https://physionet.org/content/eegmmidb/1.0.0/)：Open Data Commons Attribution License 1.0。只由下載腳本抓取 S001–S008 R01/R02；原始 EDF 與衍生 NPZ、manifest 不進 git。使用或分享衍生資料時保留此來源與授權告知。[完整資料授權](https://physionet.org/content/eegmmidb/view-license/1.0.0/)。
- Schalk, G. (2009). EEG Motor Movement/Imagery Dataset (version 1.0.0). PhysioNet. https://doi.org/10.13026/C28G6P 。原始研究：Schalk et al. (2004), BCI2000: a general-purpose brain-computer interface system, IEEE TBME 51(6), 1034–1043, DOI 10.1109/TBME.2004.827072。PhysioNet：Goldberger et al. (2000), Circulation 101(23), e215–e220。
- [MNE-Python](https://github.com/mne-tools/mne-python/blob/main/LICENSE.txt)：BSD-3-Clause，實際用於 EDF 載入。CPU/Python 3.12 可用。
- [autoreject](https://github.com/autoreject/autoreject/blob/main/LICENSE)：BSD-3-Clause；未採用，避免本小樣本不適當地宣稱自動修補／驗證品質。
- [MOABB](https://github.com/NeuroTechX/moabb/blob/develop/LICENSE)：BSD-3-Clause；未採用，這版僅建立明確受試者分割的小基線，尚非 MOABB benchmark。
- [Braindecode](https://github.com/braindecode/braindecode/blob/master/LICENSE.txt)：BSD-3-Clause；未採用，CPU 小模型不需要 PyTorch 或權重。
- [BrainFlow](https://github.com/brainflow-dev/brainflow/blob/master/LICENSE)：主體 MIT，但目前 LICENSE 另有 SimpleBLE 使用／散布限制；本版未採用、不串接硬體。將來選板與藍牙模組前需重核對。

執行套件：NumPy、SciPy、scikit-learn（BSD-3-Clause）；FastAPI、Uvicorn（MIT）；MNE（BSD-3-Clause）。開發：pytest（MIT）、HTTPX（BSD-3-Clause）、Playwright（Apache-2.0）。完整版本鎖在 requirements.lock；套件原始授權隨安裝的 distributions 保留，不將第三方程式複製到本 repo。合成訊號由本專案程式產生，隨原始碼 MIT，無真人資料。
