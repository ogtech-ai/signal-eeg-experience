import numpy as np
from fastapi.testclient import TestClient
from app.core import synthetic,features,quality,train,FS
from app.main import app
client=TestClient(app)
def test_alpha_and_ml_respond_to_signal():
    assert features(synthetic(7,True))[1][1]>features(synthetic(7,False))[1][1]
    model,report=train()
    assert set(report['train_subjects']).isdisjoint(report['test_subjects'])
    assert model.predict([features(synthetic(8,False)[:,:FS*4])[0],features(synthetic(8,True)[:,:FS*4])[0]]).tolist()==[0,1]
def test_quality_rejects_flat_and_spike():
    assert not quality(np.zeros((3,FS*4)))['accepted']
    x=synthetic(7,False)[:,:FS*4]; x[0,100]+=500
    assert not quality(x)['accepted']
def test_api_flow_and_artifact():
    r=client.get('/api/record'); assert r.status_code==200
    assert len(r.json()['signal'])==3
    clean=client.post('/api/analyze',json={}).json()
    assert clean['quality']['accepted'] and clean['closed_probability'] is not None
    bad=client.post('/api/analyze',json={'artifact':True}).json()
    assert not bad['quality']['accepted'] and bad['closed_probability'] is None
    assert bad['segment_signal']!=clean['segment_signal']
def test_boundaries():
    for body in ({'source':'unknown'},{'start':59},{'duration':2},{'subject':9},{'start':-1}):
        assert client.post('/api/analyze',json=body).status_code==422
    assert client.get('/api/record?subject=1').status_code==422
    assert client.get('/').status_code==200
