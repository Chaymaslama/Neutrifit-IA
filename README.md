# NutriFit AI — version corrigée

Python 3.11+ ; FastAPI, SQLite, interface HTML/CSS/JS. Le code original utilise Groq, conservé ici à la place de Gemini. Les données nutritionnelles et prix sont indicatifs, non audités médicalement. Application locale uniquement : historique sans authentification.

## Windows PowerShell (depuis le dossier extrait)

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Ouvrir http://127.0.0.1:8000/ ; Swagger : /docs. La base est initialisée automatiquement.

## Mode IA réel
Créer une clé personnelle sur https://console.groq.com/keys ; consulter https://console.groq.com/docs/models pour vérifier le modèle disponible. Dans .env, mettre NUTRIFIT_MODE=ai et GROQ_API_KEY=la clé personnelle. Le modèle proposé est openai/gpt-oss-120b (modifiable). Redémarrer le serveur. Tester avec `python -m backend.agent.check_llm` dans le venv. Ne jamais publier .env. Les quotas et la disponibilité dépendent du compte.

## Mode démo
Sans clé, scénario fixe validé par les outils, avec le profil initial du formulaire. Il ne remplace pas l'agent IA et ne traite pas les goûts libres. Un profil incompatible peut être refusé. Aucun appel externe.

## Tests
`python -m pytest -q` ; les tests agent utilisent un faux client. Aucun test ne prouve la disponibilité de l'API distante.

## Version 2 — Deux espaces
- Client : http://127.0.0.1:8000/app/
- Studio agent : http://127.0.0.1:8000/app/agent.html
- Le dernier résultat est conservé dans sessionStorage pour naviguer entre les pages dans le même onglet. Les plans validés restent dans SQLite.
- Studio : historique local, compteurs, comparaison des vérifications, filtre des erreurs, durée des outils IA (hors temps réseau).
- Application locale de démonstration sans authentification : ne pas exposer publiquement les routes /plans ni utiliser de profils réels sensibles.
- Configuration : copier .env.example vers .env si .env n'existe pas ; sinon conserver sa clé. Le mode démo n'est pas une IA.

## Studio V4
Navigation latérale, cartes repas illustratives, tableaux élargis et barres de comparaison des tentatives. Les photos de repas distantes ont une image locale de secours. Les photos ne représentent pas nécessairement les ingrédients exacts. Les deux bannières locales proviennent des captures fournies. Lancer sur un nouveau port pour éviter les anciennes versions : `python -m uvicorn backend.main:app --port 8002`.
