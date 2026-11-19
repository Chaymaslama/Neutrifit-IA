import os
from ..agent.demo import run_demo
from fastapi import APIRouter, HTTPException
from ..schemas import Profil
from ..agent.agent import run_agent

router = APIRouter()


@router.post('/generate')
def generate(profil: Profil):
    try:
        return (run_demo if os.getenv("NUTRIFIT_MODE", "demo") == "demo" else run_agent)(profil.model_dump())
    except Exception as e:
        print('Erreur agent :', type(e).__name__, getattr(getattr(e, 'response', None), 'status_code', ''))      # détail dans la console du serveur uniquement
        raise HTTPException(status_code=503, detail='Service IA indisponible, réessayez.')
