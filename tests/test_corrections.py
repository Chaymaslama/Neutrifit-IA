from fastapi.testclient import TestClient
from backend.main import app
from backend.schemas import Profil
from pydantic import ValidationError
import pytest
P=dict(age=21,sexe='F',poids=60,taille=168,activite='leger',objectif='prise_masse',niveau='debutant',jours_dispo=3,materiel=['halteres'],allergies=['arachides'],budget_dt_jour=8)
def test_demo(monkeypatch):
    monkeypatch.setenv('NUTRIFIT_MODE','demo')
    r=TestClient(app).post('/generate',json=P).json()
    assert r['valide'] and r['mode']=='demo' and len(r['journal'])==6
@pytest.mark.parametrize('change',[{'budget_dt_jour':-1},{'allergies':['inconnue']}])
def test_invalid_profile(change):
    with pytest.raises(ValidationError): Profil(**(P|change))
def test_zero_budget(monkeypatch):
    monkeypatch.setenv('NUTRIFIT_MODE','demo')
    assert not TestClient(app).post('/generate',json=P|{'budget_dt_jour':0}).json()['valide']
