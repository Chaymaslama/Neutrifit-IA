from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    assert client.get('/health').json()['status'] == 'ok'


def test_plan_introuvable():
    assert client.get('/plans/999999').status_code == 404


def test_plans_liste():
    assert client.get('/plans').status_code == 200


def test_age_mineur_refuse():
    p = {'age': 17, 'sexe': 'F', 'poids': 60, 'taille': 168, 'activite': 'leger',
         'objectif': 'maintien', 'niveau': 'debutant', 'jours_dispo': 3}
    assert client.post('/generate', json=p).status_code == 422
