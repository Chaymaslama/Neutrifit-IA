# Étape 12 — Livraison

## 1. Vérifier avant le rendu
```
git checkout main
git pull
pip install -r requirements.txt
python -m pytest -q
python -m backend.data.import_aliments
uvicorn backend.main:app --reload
```
Ouvrir http://127.0.0.1:8000/app/ et faire tout le parcours (génération, affinage, journal).

## 2. Évaluation pour les slides
```
python evaluation.py --n 5
```
Recopier le tableau de `evaluation_resultats.md` dans la slide « Évaluation ».

## 3. Marquer la version
```
git checkout -b docs/livraison
git add .
git commit -m "docs: README et résultats d'évaluation"
git push -u origin docs/livraison
```
Pull Request relue par un autre membre, Squash and merge, puis :
```
git checkout main
git pull
git tag v1.0
git push origin v1.0
```

## 4. Contrôle « inconnu »
Une personne qui n'a jamais ouvert le projet le lance avec le README seul.

## 5. Plan B
Enregistrer une vidéo de la démonstration (voir `docs/demo.md`) au cas où le réseau ou l'API tomberait.
