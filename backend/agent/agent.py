import json
import os
import time
from dotenv import load_dotenv
import httpx
from types import SimpleNamespace

class OpenAI:
    def __init__(self, api_key, base_url, **kwargs):
        if not api_key: raise RuntimeError("GROQ_API_KEY manquante dans .env")
        self.key, self.url = api_key, base_url.rstrip("/")
        self.chat = SimpleNamespace(completions=self)
    def create(self, **kwargs):
        r = httpx.post(self.url + "/chat/completions", headers={"Authorization": "Bearer " + self.key}, json=kwargs, timeout=60)
        r.raise_for_status()
        return json.loads(r.text, object_hook=lambda d: SimpleNamespace(**d))
from ..database import get_db
from .tools import Outils, charger_aliments
from .tool_schemas import TOOLS
from .prompts import SYSTEM

load_dotenv()
# Groq : API compatible OpenAI. Pour changer de fournisseur, modifier LLM_BASE_URL, la clé et le modèle.
MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')
BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.groq.com/openai/v1')
NOMS = {t['function']['name'] for t in TOOLS}

_client = None


def get_client():
    """Client créé à la demande : l'import du module ne plante pas sans clé API."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv('GROQ_API_KEY'), base_url=BASE_URL, max_retries=0)
    return _client


def _attente(e, n):
    """Durée d'attente avant un nouvel essai : en-tête retry-after de l'API, sinon progressive."""
    try:
        v = float(e.response.headers.get('retry-after'))
        return min(max(v, 1), 60)
    except Exception:
        return 3 * (n + 1)


def appeler_modele(messages, essais=3):
    """Réessaie si la limite par minute est atteinte (429), si le service est surchargé (5xx)
    ou si le modèle a mal formé un appel d'outil. S'arrête tout de suite si le quota du jour est épuisé."""
    for n in range(essais):
        try:
            return get_client().chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS, tool_choice='auto', max_tokens=4000)
        except Exception as e:
            txt = str(e)
            quota_jour = any(m in txt for m in ('per day', 'TPD', 'RPD'))
            temporaire = not quota_jour and any(
                c in txt for c in ('429', 'rate_limit', '500', '502', '503', 'overloaded', 'tool_use_failed'))
            if temporaire and n < essais - 1:
                attente = _attente(e, n)
                print(f'Limite ou erreur passagère, nouvel essai {n + 2}/{essais} dans {attente:.0f} s…')
                time.sleep(attente)
                continue
            raise


def pour_modele(nom, sortie):
    """Texte renvoyé au modèle. La liste d'aliments est compactée pour économiser des tokens
    (le journal affiché dans l'interface garde la sortie complète)."""
    if nom == 'chercher_aliments' and isinstance(sortie, list):
        lignes = ['id|nom|categorie|kcal/100g|prot/100g|prix DT/kg']
        lignes += [f"{a['id']}|{a['nom']}|{a['categorie']}|{a['kcal_100g']}|{a['prot_100g']}|{a['prix_dt_kg']}"
                   for a in sortie]
        return '\n'.join(lignes)
    return json.dumps(sortie, ensure_ascii=False, separators=(',', ':'))


def run_agent(profil, max_steps=12):
    con = get_db()
    outils = Outils(profil, charger_aliments(con), con)
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': json.dumps(profil, ensure_ascii=False)}]
    journal = []                                     # étapes affichées dans l'interface
    try:
        for _ in range(max_steps):
            r = appeler_modele(messages)
            if not r.choices:                        # réponse bloquée ou vide
                return outils.reponse('Le modèle n’a pas renvoyé de réponse.', journal)
            msg = r.choices[0].message
            appels = getattr(msg, "tool_calls", None) or []            # outils demandés (ou vide)
            if not appels:                           # réponse finale
                return outils.reponse(getattr(msg, "content", None) or '', journal)

            messages.append({'role': 'assistant', 'content': getattr(msg, "content", None) or None,
                             'tool_calls': [{'id': a.id, 'type': 'function',
                                             'function': {'name': a.function.name,
                                                          'arguments': a.function.arguments or '{}'}}
                                            for a in appels]})
            for a in appels:
                t0 = time.monotonic()
                nom = a.function.name
                try:
                    args = json.loads(a.function.arguments or '{}')
                except ValueError:
                    args = None
                if nom not in NOMS:                  # liste blanche des outils
                    sortie = {'erreur': 'outil inconnu'}
                elif not isinstance(args, dict):
                    sortie = {'erreur': 'arguments JSON invalides'}
                else:
                    try:
                        sortie = getattr(outils, nom)(**args)
                    except Exception as e:
                        sortie = {'erreur': str(e)}  # l'agent peut se corriger
                journal.append({'outil': nom, 'entree': args if isinstance(args, dict) else {},
                                'sortie': sortie, 'duree_ms': round((time.monotonic()-t0)*1000)})
                messages.append({'role': 'tool', 'tool_call_id': a.id,
                                 'content': pour_modele(nom, sortie)})

        return outils.reponse('Limite d’étapes atteinte avant la fin du plan.', journal)
    finally:
        con.close()
