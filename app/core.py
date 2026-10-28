"""CPU EEG baseline. Units are microvolts; probabilities are task scores, not health."""
from pathlib import Path
import json
import numpy as np
from scipy.signal import welch
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FS = 160
CHANNELS = ['O1', 'Oz', 'O2']
BANDS = {'theta': (4, 8), 'alpha': (8, 13), 'beta': (13, 30)}

def synthetic(subject, closed, duration=60):
    rng = np.random.default_rng(subject * 10 + int(closed))
    t = np.arange(FS * duration) / FS
    return np.array([(5 + 14 * closed) * np.sin(2*np.pi*(10 + .1*c)*t + rng.random()) + 6*rng.normal(size=len(t)) + 4*np.sin(2*np.pi*6*t) for c in range(3)])

def features(x):
    f, p = welch(x, FS, nperseg=FS*2, axis=-1)
    power = np.array([np.trapezoid(p[:, (f >= a) & (f < b)], f[(f >= a) & (f < b)], axis=-1) for a,b in BANDS.values()]).T
    relative = power / np.maximum(power.sum(axis=1, keepdims=True), 1e-12)
    return np.log(np.maximum(relative, 1e-8)).flatten(), relative.mean(axis=0)

def quality(x):
    ptp = np.ptp(x, axis=1)
    flat = np.std(x, axis=1) < .5
    bad = (ptp > 200) | flat | ~np.all(np.isfinite(x),axis=1)
    return {'accepted': not bool(bad.any()), 'bad_channels': [CHANNELS[i] for i in np.where(bad)[0]], 'peak_to_peak_uv': np.round(ptp,2).tolist(), 'rule': '任一通道峰對峰 > 200 µV 或標準差 < 0.5 µV，暫停分類。啟發式門檻，非臨床品質認證。'}

def load_record(subject, closed, source):
    if source == 'synthetic':
        return synthetic(subject, closed)
    path = ROOT/'data'/f'S{subject:03d}R{2 if closed else 1:02d}.npz'
    if not path.exists():
        raise FileNotFoundError('公開錄製尚未下載，請執行 scripts.prepare_data。')
    with np.load(path, allow_pickle=False) as d:
        return d['signal']

def train(source='synthetic'):
    X,y,groups=[],[],[]
    for subject in range(1,9):
        for closed in (False,True):
            x=load_record(subject, closed, source)
            for start in range(0,x.shape[1]-FS*4+1,FS*4):
                window=x[:,start:start+FS*4]
                if quality(window)['accepted']:
                    X.append(features(window)[0]); y.append(int(closed)); groups.append(subject)
    X,y,g=np.asarray(X),np.asarray(y),np.asarray(groups)
    fit=g<=6; test=g>=7
    if len(set(y[fit]))<2 or len(set(y[test]))<2:
        raise ValueError('訓練／測試資料品質通過後須各有兩類。')
    model=make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=1000,random_state=0))
    model.fit(X[fit],y[fit])
    pred=model.predict(X[test])
    from sklearn.metrics import balanced_accuracy_score, confusion_matrix
    report={'source':source,'train_subjects':list(range(1,7)),'test_subjects':[7,8], 'train_windows':int(fit.sum()),'test_windows':int(test.sum()),'balanced_accuracy':float(balanced_accuracy_score(y[test],pred)), 'confusion_matrix':confusion_matrix(y[test],pred,labels=[0,1]).tolist(), 'test_subject_balanced_accuracy':{str(s):float(balanced_accuracy_score(y[test][g[test]==s],pred[g[test]==s])) for s in (7,8)}, 'classes':['eyes_open','eyes_closed'], 'limitations':'僅 8 位受試者之小樣本技術基線；未做外部驗證。合成資料分數不能代表真實 EEG 效果。測試受試者亦供展示，後續調參須另留未接觸測試集。'}
    return model,report
