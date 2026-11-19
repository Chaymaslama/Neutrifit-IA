from fastapi import APIRouter, HTTPException
from ..database import get_db

router = APIRouter()


@router.get('/plans')
def plans():
    con = get_db()
    rows = con.execute('SELECT id, date FROM plans ORDER BY id DESC LIMIT 20').fetchall()
    con.close()
    return [dict(r) for r in rows]


@router.get('/plans/{plan_id}')
def plan(plan_id: int):
    con = get_db()
    r = con.execute('SELECT * FROM plans WHERE id = ?', (plan_id,)).fetchone()
    con.close()
    if r is None:
        raise HTTPException(status_code=404, detail='Plan introuvable')
    return dict(r)
