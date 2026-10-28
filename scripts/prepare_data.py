"""Download 16 public baseline EDFs (~20 MB), four bounded concurrent requests."""
import hashlib,json,urllib.request,sys,ssl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import certifi
import mne
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core import CHANNELS,FS,train

def prepare(pair):
    subject,run=pair; folder=ROOT/'data'; name=f'S{subject:03d}R{run:02d}'
    url=f'https://physionet.org/files/eegmmidb/1.0.0/S{subject:03d}/{name}.edf'
    target=folder/(name+'.edf')
    if not target.exists():
        print('Downloading',name,flush=True)
        with urllib.request.urlopen(url,timeout=60,context=ssl.create_default_context(cafile=certifi.where())) as response:
            content=response.read(10_000_000)
        if len(content)>=10_000_000: raise ValueError('Unexpected file size')
        temporary=target.with_suffix('.partial'); temporary.write_bytes(content); temporary.replace(target)
    raw=mne.io.read_raw_edf(target,preload=True,verbose='ERROR')
    raw.rename_channels({c:c.strip('.').upper() for c in raw.ch_names})
    if raw.info['sfreq']!=FS: raise ValueError('Unexpected sampling rate')
    signal=raw.get_data(picks=[c.upper() for c in CHANNELS])*1e6
    if not np.isfinite(signal).all(): raise ValueError('Nonfinite EEG')
    np.savez_compressed(folder/(name+'.npz'),signal=signal)
    return {'file':target.name,'url':url,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'label':'eyes_open' if run==1 else 'eyes_closed','subject':subject}

def main():
    folder=ROOT/'data'; folder.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest=list(pool.map(prepare,[(s,r) for s in range(1,9) for r in (1,2)]))
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    _,report=train('physionet'); (folder/'evaluation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)); print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
