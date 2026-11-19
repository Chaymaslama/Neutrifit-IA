
'use strict';
fetch('/health').then(r=>r.json()).then(d=>{document.getElementById('mode-api').textContent=d.mode==='demo'?'Mode démonstration locale — sans IA distante':'Mode IA Groq — clé à configurer si nécessaire';}).catch(()=>{});

// ---------- utilitaires DOM : tout le texte passe par des noeuds texte (jamais de HTML brut) ----------
function el(tag, props, ...enfants) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') e.className = v; else e.setAttribute(k, v);
  }
  for (const c of enfants.flat()) {
    if (c === null || c === undefined || c === false) continue;
    e.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return e;
}
const $ = id => document.getElementById(id);
const arrondi = (x, d = 0) => Number(x).toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d });
const REPAS = { petit_dejeuner: 'Petit-déjeuner', dejeuner: 'Déjeuner', diner: 'Dîner', collation: 'Collation' };
const ETAPES = [
  { id: 'calculer_besoins',  nom: 'Besoins',        desc: 'Calories et protéines cibles' },
  { id: 'chercher_aliments', nom: 'Aliments',       desc: 'Aliments autorisés (allergènes exclus)' },
  { id: 'verifier_menu',     nom: 'Vérification',   desc: 'Allergènes, calories, protéines, budget' },
  { id: 'construire_seance', nom: 'Séances',        desc: 'Exercices adaptés au profil' },
  { id: 'liste_courses',     nom: 'Courses',        desc: 'Liste et coût de la semaine' },
  { id: 'enregistrer_plan',  nom: 'Enregistrement', desc: 'Refusé si le menu n’est pas validé' },
];
const NOMS_OUTILS = Object.fromEntries(ETAPES.map(e => [e.id, e.nom]));
let dernierProfil = null;

// ---------- formulaire et appel ----------
function lireProfil() {
  const num = id => Number($(id).value);
  return {
    age: num('age'), sexe: $('sexe').value, poids: num('poids'), taille: num('taille'),
    activite: $('activite').value, objectif: $('objectif').value, niveau: $('niveau').value,
    jours_dispo: num('jours'),
    materiel: [...document.querySelectorAll('input[name=materiel]:checked')].map(c => c.value),
    allergies: [...document.querySelectorAll('input[name=allergie]:checked')].map(c => c.value),
    budget_dt_jour: $('budget').value === '' ? null : Number($('budget').value),
    consignes: '',
  };
}

function messageErreur(status, corps) {
  if (status === 422 && corps && Array.isArray(corps.detail)) {
    return 'Profil invalide : ' + corps.detail.map(d => {
      const champ = (d.loc || []).slice(1).join('.');
      return (champ ? champ + ' — ' : '') + d.msg;
    }).join(' ; ');
  }
  if (status === 503) return 'Service IA indisponible : clé invalide, quota atteint ou réseau. Le détail est dans le terminal du serveur (ligne « Erreur agent »).';
  if (corps && typeof corps.detail === 'string') return corps.detail;
  return 'Erreur ' + status;
}

let minuteur = null;
async function generer(affinage) {
  const etat = $('etat'), bouton = $('btn-generer'), zone = $('resultat');
  const profil = (affinage && dernierProfil)
    ? { ...dernierProfil, consignes: ($('consignes') ? $('consignes').value.trim() : '') }
    : lireProfil();

  bouton.disabled = true;
  const bAff = $('btn-regenerer'); if (bAff) bAff.disabled = true;
  zone.classList.add('occupe');
  const t0 = Date.now();
  const texte = el('span', {}, 'Génération en cours… 0 s');
  etat.className = 'charge';
  etat.replaceChildren(el('span', { class: 'spinner' }), texte);
  etat.append(el('small', {}, ' L’agent enchaîne plusieurs appels (de 10 s à quelques minutes).'));
  minuteur = setInterval(() => { texte.textContent = 'Génération en cours… ' + Math.round((Date.now() - t0) / 1000) + ' s'; }, 1000);

  try {
    const r = await fetch('/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profil),
    });
    let corps = null;
    try { corps = await r.json(); } catch (_) { /* corps vide */ }
    if (!r.ok) throw new Error(messageErreur(r.status, corps));
    dernierProfil = profil;
    try { sessionStorage.setItem("nutrifit:last", JSON.stringify({r:corps, profil})); } catch (_) {}
    afficher(corps, profil);
    etat.className = ''; etat.replaceChildren();
  } catch (e) {
    etat.className = 'erreur';
    etat.textContent = e instanceof TypeError ? 'Serveur injoignable : vérifiez que uvicorn tourne.' : e.message;
  } finally {
    clearInterval(minuteur);
    zone.classList.remove('occupe');
    bouton.disabled = false;
    const b2 = $('btn-regenerer'); if (b2) b2.disabled = false;
  }
}

// ---------- analyse du journal ----------
const appelsDe = (journal, outil) => journal.filter(j => j.outil === outil);
const sortieOk = j => !!(j.sortie && j.sortie.ok === true);
const sortieErreur = j => !!(j.sortie && j.sortie.erreur);

function indexAliments(journal) {
  // le menu ne contient que des aliment_id : les noms viennent des résultats de chercher_aliments
  const idx = {};
  for (const j of appelsDe(journal, 'chercher_aliments')) {
    if (Array.isArray(j.sortie)) for (const a of j.sortie) idx[a.id] = a;
  }
  return idx;
}

function statutEtapes(journal) {
  return ETAPES.map(e => {
    const appels = appelsDe(journal, e.id);
    if (!appels.length) return { ...e, statut: 'todo', note: 'Non atteint' };
    if (e.id === 'verifier_menu') {
      const premierOk = appels.findIndex(sortieOk);
      if (premierOk === -1) return { ...e, statut: 'ko', note: appels.length + ' essai(s), tous refusés' };
      return { ...e, statut: 'ok', note: premierOk === 0 ? 'Validé du premier coup' : 'Validé après ' + premierOk + ' correction(s)' };
    }
    if (e.id === 'enregistrer_plan') {
      return appels.some(sortieOk) ? { ...e, statut: 'ok', note: 'Plan enregistré' } : { ...e, statut: 'ko', note: 'Refusé' };
    }
    return appels.some(sortieErreur) && !appels.some(a => !sortieErreur(a))
      ? { ...e, statut: 'ko', note: 'Erreur' } : { ...e, statut: 'ok', note: 'Terminé' };
  });
}

function diagnostic(r) {
  const journal = r.journal || [];
  const derniere = journal[journal.length - 1];
  const verifs = appelsDe(journal, 'verifier_menu');
  const texteVide = !(r.texte && r.texte.trim());
  const limite = /limite d.étapes/i.test(r.texte || '');
  const d = { titre: '', lignes: [], conseils: [] };

  if (!journal.length) {
    d.titre = 'L’agent n’a appelé aucun outil.';
    d.conseils.push('Le modèle a répondu sans utiliser ses outils. Relancez la génération.');
  } else if (limite) {
    d.titre = 'L’agent a atteint sa limite d’étapes sans valider de menu.';
    d.lignes.push(journal.length + ' appels d’outils ont été faits, puis l’agent a été arrêté pour éviter une boucle sans fin.');
    d.conseils.push('Relancez : le comportement du modèle varie d’une exécution à l’autre.');
  } else if (!verifs.length) {
    d.titre = 'L’agent s’est arrêté avant de proposer un menu.';
    d.lignes.push('Dernier outil appelé : ' + (NOMS_OUTILS[derniere.outil] || derniere.outil) + ' (appel n° ' + journal.length + ').');
    d.lignes.push(texteVide
      ? 'Le modèle a ensuite renvoyé une réponse vide : ni nouvel appel d’outil, ni texte.'
      : 'Le modèle a répondu par du texte au lieu d’appeler l’outil de vérification.');
    d.conseils.push('Relancez une fois : ce type d’arrêt est souvent passager.');
    d.conseils.push('Si cela se répète, changez de modèle dans le fichier .env, puis redémarrez le serveur.');
    d.conseils.push('Cherchez dans le terminal du serveur une ligne d’erreur ou de limite (429) juste après l’appel.');
  } else if (!verifs.some(sortieOk)) {
    const dern = verifs[verifs.length - 1].sortie || {};
    d.titre = 'Aucun menu n’a passé la vérification.';
    d.lignes.push(verifs.length + ' menu(s) proposé(s), tous refusés par le code. Dernier refus :');
    d.problemes = dern.problemes || [];
    d.conseils.push('Essayez un budget plus élevé ou relancez. Ne retirez jamais une allergie réelle.');
  } else {
    d.titre = 'Le menu est valide mais le plan n’a pas été enregistré.';
    d.lignes.push('L’agent s’est arrêté avant l’étape d’enregistrement.');
    d.conseils.push('Relancez la génération.');
  }
  return d;
}

// ---------- rendu du texte de l'agent (mini-Markdown sûr : noeuds DOM uniquement) ----------
function inline(parent, texte) {
  texte.replace(/<br\s*\/?\s*>/gi, '\u000b').split(/(\*\*[^*]+\*\*|\u000b)/g).forEach(m => {
    if (m === '\u000b') parent.append(el('br'));
    else if (/^\*\*[^*]+\*\*$/.test(m)) parent.append(el('strong', {}, m.slice(2, -2)));
    else if (m) parent.append(document.createTextNode(m.replace(/`/g, '')));
  });
  return parent;
}
function rendreTexte(texte) {
  const boite = el('div', { class: 'texte' });
  if (!texte || !texte.trim()) {
    boite.append(el('p', { class: 'vide-texte' }, 'L’agent n’a renvoyé aucun texte.'));
    return boite;
  }
  const lignes = texte.replace(/\r/g, '').split('\n');
  let i = 0;
  while (i < lignes.length) {
    const l = lignes[i].trim();
    if (!l) { i++; continue; }
    let m;
    if ((m = l.match(/^#{1,6}\s+(.*)$/))) { boite.append(inline(el('h4'), m[1].replace(/\*\*/g, ''))); i++; }
    else if (l.startsWith('|')) {
      const bloc = [];
      while (i < lignes.length && lignes[i].trim().startsWith('|')) bloc.push(lignes[i++].trim());
      const cellules = s => s.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      const rows = bloc.filter(s => !/^\|?[\s:|-]+\|?$/.test(s)).map(cellules);
      if (rows.length) {
        const t = el('table', {}, el('thead', {}, el('tr', {}, rows[0].map(c => inline(el('th'), c)))),
          el('tbody', {}, rows.slice(1).map(r => el('tr', {}, r.map(c => inline(el('td'), c))))));
        boite.append(el('div', { class: 'defile' }, t));
      }
    } else if (/^[-*•]\s+/.test(l)) {
      const ul = el('ul');
      while (i < lignes.length && /^[-*•]\s+/.test(lignes[i].trim())) ul.append(inline(el('li'), lignes[i++].trim().replace(/^[-*•]\s+/, '')));
      boite.append(ul);
    } else if (/^\d+[.)]\s+/.test(l)) {
      const ol = el('ol');
      while (i < lignes.length && /^\d+[.)]\s+/.test(lignes[i].trim())) ol.append(inline(el('li'), lignes[i++].trim().replace(/^\d+[.)]\s+/, '')));
      boite.append(ol);
    } else { boite.append(inline(el('p'), l)); i++; }
  }
  return boite;
}

// ---------- blocs d'affichage ----------
function carteVerdict(r, profil) {
  const ok = !!r.valide;
  const boite = el('div', { class: 'verdict ' + (ok ? 'ok' : 'ko') });
  boite.append(el('div', { class: 'icone', 'aria-hidden': 'true' }, ok ? '✅' : '⚠️'));
  const corps = el('div');
  if (ok) {
    corps.append(el('h2', {}, 'Plan validé · n° ' + r.plan_id),
      el('p', {}, 'Le menu respecte vos allergies, vos besoins en calories et en protéines et votre budget. ' +
        'Les chiffres sont calculés et vérifiés par le code, pas inventés par l’IA.'));
  } else {
    const d = diagnostic(r);
    corps.append(el('h2', {}, 'Plan non validé'), el('p', {}, el('strong', {}, d.titre)));
    d.lignes.forEach(t => corps.append(el('p', {}, t)));
    if (d.problemes && d.problemes.length) corps.append(el('ul', {}, d.problemes.map(p => el('li', {}, p))));
    corps.append(el('p', {}, 'Rien d’invalide n’a été enregistré : le plan reste vide plutôt que faux.'));
    if (d.conseils.length) corps.append(el('h3', {}, 'Que faire ?'), el('ul', {}, d.conseils.map(c => el('li', {}, c))));
  }
  const actions = el('div', { class: 'actions no-print' });
  const rejouer = el('button', { type: 'button', class: ok ? 'secondaire' : '' }, ok ? 'Générer un autre plan' : 'Réessayer');
  rejouer.addEventListener('click', () => generer(false));
  actions.append(rejouer);
  if (ok) {
    const imprimer = el('button', { type: 'button', class: 'secondaire' }, 'Imprimer / enregistrer en PDF');
    imprimer.addEventListener('click', () => window.print());
    actions.append(imprimer);
  }
  corps.append(actions);
  boite.append(corps);
  return boite;
}

function carteParcours(journal) {
  const st = statutEtapes(journal);
  const grille = el('div', { class: 'parcours' }, st.map((e, i) => el('div', { class: 'etape ' + e.statut },
    el('div', { class: 't' }, el('span', { class: 'pastille' }, e.statut === 'ok' ? '✓' : e.statut === 'ko' ? '✗' : '–'), e.nom),
    el('div', { class: 'd' }, e.desc), el('div', { class: 's' }, e.note))));
  return el('section', {}, el('h2', {}, 'Parcours de l’agent'),
    el('p', { class: 'sous-titre' }, 'Les 6 étapes attendues et celles que l’agent a réellement franchies.'), grille);
}

function barre(valeur, cible, ok) {
  const max = 1.4;
  const part = Math.min(valeur / cible, max) / max * 100;
  return el('div', { class: 'bar' + (ok ? '' : ' ko') },
    el('div', { class: 'remplissage', style: 'width:' + part.toFixed(1) + '%' }),
    el('div', { class: 'cible', style: 'left:' + (100 / max).toFixed(1) + '%', title: 'Cible' }));
}
function ligneControle(nom, valeur, detail, ok, barreEl) {
  return el('div', { class: 'controle' }, el('div', { class: 'nom' }, nom),
    el('div', { class: 'valeur' }, valeur, detail ? el('small', {}, detail) : null, barreEl),
    el('div', { class: 'verdict-mini ' + (ok ? 'ok' : 'ko') }, ok ? '✓ Respecté' : '✗ Hors limite'));
}
function carteControles(r, profil) {
  const v = r.verification, b = r.besoins;
  if (!v || !b || v.kcal === undefined) return null;
  const ecart = (v.kcal - b.kcal) / b.kcal * 100;
  const okKcal = Math.abs(ecart) <= 15, okProt = v.proteines_g >= 0.8 * b.proteines_g;
  const budget = profil && profil.budget_dt_jour;
  const okBudget = !budget || v.cout_dt <= budget;
  const alls = (profil && profil.allergies) || [];
  const lignes = [
    ligneControle('Allergènes', alls.length ? 'Aucun allergène détecté' : 'Aucune allergie déclarée',
      alls.length ? 'Exclus : ' + alls.join(', ') + ' (filtrés avant et vérifiés après)' : '', true),
    ligneControle('Calories', arrondi(v.kcal) + ' kcal / cible ' + arrondi(b.kcal),
      'Écart ' + (ecart >= 0 ? '+' : '') + arrondi(ecart, 1) + ' % (tolérance ±15 %)', okKcal, barre(v.kcal, b.kcal, okKcal)),
    ligneControle('Protéines', arrondi(v.proteines_g) + ' g / cible ' + arrondi(b.proteines_g) + ' g',
      'Minimum accepté : ' + arrondi(0.8 * b.proteines_g) + ' g (80 % de la cible)', okProt, barre(v.proteines_g, b.proteines_g, okProt)),
    ligneControle('Budget', arrondi(v.cout_dt, 2) + ' DT' + (budget ? ' / ' + arrondi(budget, 2) + ' DT par jour' : ''),
      budget ? '' : 'Aucun budget fixé', okBudget, budget ? barre(v.cout_dt, budget, okBudget) : null),
  ];
  return el('section', {}, el('h2', {}, 'Ce que le code a vérifié'),
    el('p', { class: 'sous-titre' }, 'Ces contrôles sont calculés en Python à partir de la base d’aliments.'), lignes);
}

function carteMenu(r, idx) {
  if (!(r.menu && r.menu.items && r.menu.items.length)) return null;
  const parRepas = {};
  for (const it of r.menu.items) (parRepas[it.repas] = parRepas[it.repas] || []).push(it);
  const corps = el('tbody');
  let tk = 0, tp = 0, tc = 0;
  for (const repas of Object.keys(REPAS)) {
    const lignes = parRepas[repas];
    if (!lignes) continue;
    corps.append(el('tr', {}, el('th', { class: 'repas', colspan: 5 }, REPAS[repas])));
    for (const it of lignes) {
      const a = idx[it.aliment_id];
      const kcal = a ? a.kcal_100g * it.quantite_g / 100 : null;
      const prot = a ? a.prot_100g * it.quantite_g / 100 : null;
      const cout = a ? a.prix_dt_kg * it.quantite_g / 1000 : null;
      if (a) { tk += kcal; tp += prot; tc += cout; }
      corps.append(el('tr', {},
        el('td', {}, a ? a.nom : 'Aliment n° ' + it.aliment_id),
        el('td', { class: 'num' }, it.quantite_g + ' g'),
        el('td', { class: 'num' }, kcal === null ? '—' : arrondi(kcal) + ' kcal'),
        el('td', { class: 'num' }, prot === null ? '—' : arrondi(prot, 1) + ' g'),
        el('td', { class: 'num' }, cout === null ? '—' : arrondi(cout, 2) + ' DT')));
    }
  }
  corps.append(el('tr', { class: 'total' }, el('td', {}, 'Total de la journée'), el('td', {}),
    el('td', { class: 'num' }, arrondi(tk) + ' kcal'), el('td', { class: 'num' }, arrondi(tp, 1) + ' g'),
    el('td', { class: 'num' }, arrondi(tc, 2) + ' DT')));
  return el('section', {}, el('h2', {}, 'Menu d’une journée type'),
    el('div', { class: 'defile' }, el('table', {},
      el('thead', {}, el('tr', {}, el('th', {}, 'Aliment'), el('th', { class: 'num' }, 'Quantité'),
        el('th', { class: 'num' }, 'Calories'), el('th', { class: 'num' }, 'Protéines'), el('th', { class: 'num' }, 'Coût'))), corps)));
}

function carteCourses(r) {
  if (!(r.courses && r.courses.lignes)) return null;
  const corps = el('tbody', {}, r.courses.lignes.map(l => el('tr', {},
    el('td', {}, l.aliment), el('td', { class: 'num' }, arrondi(l.quantite_g) + ' g'),
    el('td', { class: 'num' }, arrondi(l.cout_dt, 2) + ' DT'))));
  corps.append(el('tr', { class: 'total' }, el('td', {}, 'Total pour 7 jours'), el('td', {}),
    el('td', { class: 'num' }, arrondi(r.courses.total_dt, 2) + ' DT')));
  return el('section', {}, el('h2', {}, 'Liste de courses de la semaine'),
    el('div', { class: 'defile' }, el('table', {}, el('thead', {}, el('tr', {}, el('th', {}, 'Produit'),
      el('th', { class: 'num' }, 'Quantité'), el('th', { class: 'num' }, 'Coût'))), corps)));
}

function carteTexte(r) {
  const s = el('section', {}, el('h2', {}, 'Votre entraînement'), el('p',{class:'sous-titre'}, 'Programme proposé par le coach · adaptez l’intensité à votre condition.'));
  if (r.seances && r.seances.exercices_candidats) {
    s.append(el('div',{class:'exercise-grid'},r.seances.exercices_candidats.map(e=>el('article',{class:'exercise'},el('small',{},e.groupe),el('strong',{},e.nom),el('span',{},e.materiel==='aucun'?'Sans matériel':e.materiel)))));
    s.append(el('h3',{},'Conseils du coach · '+r.seances.jours+' jour(s) par semaine'));
  }
  s.append(rendreTexte(r.texte),el('p',{class:'avert'},'Estimations pédagogiques, non prescriptions médicales. Consultez un professionnel en cas de problème de santé.'));
  return s;
}

function carteAffiner(consignes) {
  const champ = el('textarea', { id: 'consignes', maxlength: '200', rows: '2',
    placeholder: 'ex. : je n’aime pas le thon · repas moins chers · plus de légumes' });
  champ.value = consignes || '';
  const bouton = el('button', { id: 'btn-regenerer', type: 'button', class: 'secondaire' }, 'Régénérer');
  bouton.addEventListener('click', () => generer(true));
  return el('section', { class: 'affiner-section' }, el('h2', {}, 'Affiner le résultat'),
    el('div', { class: 'affiner' }, el('div', {}, el('label', { for: 'consignes' }, 'Consignes (200 caractères maximum)'), champ), bouton),
    el('p', { class: 'avert' }, 'Une consigne exprime un goût : elle ne peut jamais lever une allergie ni dépasser le budget.'));
}

// ---------- journal lisible ----------
function resumeEntree(j) {
  const e = j.entree || {};
  if (Array.isArray(e.items)) return e.items.length + ' ligne(s) de menu envoyée(s)';
  if (e.categorie) return 'Catégorie demandée : ' + e.categorie;
  return '';
}
function decrire(j) {
  const s = j.sortie, o = j.outil;
  if (s && s.erreur) return { badge: ['ko', 'Erreur'], resume: String(s.erreur), refuse: true };
  if (o === 'calculer_besoins' && s && s.kcal !== undefined)
    return { badge: ['ok', 'Fait'], resume: 'Cible : ' + arrondi(s.kcal) + ' kcal et ' + arrondi(s.proteines_g) + ' g de protéines par jour' };
  if (o === 'chercher_aliments' && Array.isArray(s))
    return { badge: ['ok', 'Fait'], resume: s.length + ' aliments autorisés (allergènes déjà exclus)' };
  if (o === 'verifier_menu' && s && typeof s.ok === 'boolean')
    return s.ok
      ? { badge: ['ok', 'Menu validé'], resume: arrondi(s.kcal) + ' kcal · ' + arrondi(s.proteines_g) + ' g de protéines · ' + arrondi(s.cout_dt, 2) + ' DT' }
      : { badge: ['ko', 'Menu refusé'], resume: (s.problemes || []).length + ' problème(s) : l’agent doit corriger son menu', refuse: true };
  if (o === 'construire_seance' && s && s.exercices_candidats)
    return { badge: ['ok', 'Fait'], resume: s.exercices_candidats.length + ' exercices possibles pour ' + s.jours + ' jour(s) par semaine' };
  if (o === 'liste_courses' && s && s.total_dt !== undefined)
    return { badge: ['ok', 'Fait'], resume: 'Total de la semaine : ' + arrondi(s.total_dt, 2) + ' DT' };
  if (o === 'enregistrer_plan' && s && typeof s.ok === 'boolean')
    return s.ok ? { badge: ['ok', 'Enregistré'], resume: 'Plan n° ' + s.plan_id + ' sauvegardé en base' }
                : { badge: ['ko', 'Refusé'], resume: 'Menu non validé : le code a refusé de l’enregistrer', refuse: true };
  return { badge: ['info', '—'], resume: '' };
}
function detailsOutil(j) {
  const s = j.sortie, d = [];
  if (j.outil === 'chercher_aliments' && Array.isArray(s)) {
    const groupes = {};
    s.forEach(a => (groupes[a.categorie] = groupes[a.categorie] || []).push(a.nom));
    d.push(el('div', {}, Object.entries(groupes).map(([cat, noms]) =>
      el('div', { class: 'groupe' }, el('b', {}, cat.replace(/_/g, ' ')), el('div', { class: 'chips' }, noms.map(n => el('span', {}, n)))))));
  }
  if (j.outil === 'verifier_menu' && s && s.problemes && s.problemes.length)
    d.push(el('ul', { class: 'problemes' }, s.problemes.map(p => el('li', {}, p))));
  if (j.outil === 'enregistrer_plan' && s && s.erreur) d.push(el('p', { class: 'problemes' }, s.erreur));
  const tech = el('details', { class: 'technique' }, el('summary', {}, 'Détails techniques (données brutes)'),
    el('pre', {}, 'entrée : ' + JSON.stringify(j.entree) + '\nsortie : ' + JSON.stringify(j.sortie, null, 1)));
  d.push(tech);
  return d;
}
function carteJournal(journal) {
  const s = el('section', { class: 'journal-section' }, el('h2', {}, 'Journal de l’agent (' + journal.length + ' appel(s) d’outils)'),
    el('p', { class: 'sous-titre' }, 'Chaque ligne est un outil que l’agent a choisi d’appeler. Cliquez pour voir le détail.'));
  if (!journal.length) { s.append(el('p', {}, 'Aucun appel d’outil.')); return s; }
  journal.forEach((j, i) => {
    const d = decrire(j);
    const det = el('details', { class: 'step' + (d.refuse ? ' refuse' : '') },
      el('summary', {}, el('span', { class: 'n' }, i + 1),
        el('div', {}, el('div', { class: 'titre' }, NOMS_OUTILS[j.outil] || j.outil, el('code', {}, j.outil)),
          el('div', { class: 'resume' }, (d.resume || resumeEntree(j)) + (Number.isFinite(j.duree_ms) ? ' · outil : '+j.duree_ms+' ms' : ''))),
        el('span', { class: 'badge ' + d.badge[0] }, d.badge[1])),
      el('div', { class: 'corps' }, resumeEntree(j) && d.resume ? el('p', {}, resumeEntree(j)) : null, detailsOutil(j)));
    if (d.refuse && j.outil === 'verifier_menu') det.open = true;
    s.append(det);
  });
  return s;
}

// ---------- page de résultat ----------
function afficher(r, profil) {
  const zone = $('resultat');
  zone.replaceChildren();
  const journal = r.journal || [];
  const idx = indexAliments(journal);
  const blocs = [carteVerdict(r, profil)];
  if(r.valide) blocs.push(kpis(r));
  if (r.valide) blocs.push(carteControles(r, profil), carteMenu(r, idx), carteCourses(r), carteTexte(r));
  else {

    if (r.besoins) blocs.push(el('section', {}, el('h2', {}, 'Ce qui a quand même été calculé'),
      el('p', {}, 'Vos besoins quotidiens estimés : ', el('strong', {}, arrondi(r.besoins.kcal) + ' kcal'),
        ' et ', el('strong', {}, arrondi(r.besoins.proteines_g) + ' g de protéines'), '.')));
    if (r.texte && r.texte.trim()) blocs.push(carteTexte(r));
  }
  
  blocs.push(carteAffiner(profil.consignes));
  blocs.filter(Boolean).forEach(b => zone.append(b));
}

function kpis(r) { const v=r.verification||{}; return el('div',{class:'kpis'}, ...[['Énergie',v.kcal,'kcal / jour'],['Protéines',v.proteines_g,'g / jour'],['Budget',v.cout_dt,'DT / jour']].map(([l,n,u])=>el('article',{},el('small',{},l),el('strong',{},arrondi(n, l==='Budget'?2:0)),el('span',{},u)))); }
function accueil() {
  $('resultat').replaceChildren(el('section', {}, el('div', { class: 'vide' },
    el('strong', {}, 'Remplissez le formulaire puis lancez la génération.'),
    el('p', {}, 'L’agent calcule vos besoins, choisit des aliments, vérifie le menu, puis construit vos séances et vos courses.'),
    el('div', { class: 'etapes-prevues' }, ETAPES.map((e, i) => el('span', {}, (i + 1) + '. ' + e.nom))))));
}

const zone=$('resultat');
function renderAgent(r,p){ const j=r.journal||[]; const rejected=j.filter(x=>x.outil==='verifier_menu'&&x.sortie?.ok===false); const accepted=j.filter(x=>x.outil==='verifier_menu'&&x.sortie?.ok===true); zone.replaceChildren(el('div',{class:'kpis'}, ...[['Appels d’outils',j.length],['Menus refusés',rejected.length],['Menus acceptés',accepted.length],['Plan',r.valide?'Validé':'Incomplet']].map(([l,v])=>el('article',{},el('small',{},l),el('strong',{},v)))),carteParcours(j));
 const compare=el('section',{},el('h2',{},'Analyse des corrections'),el('p',{class:'sous-titre'},'Résultats mesurés par les outils, dans leur ordre réel.'));
 for(const [i,x] of j.entries()) if(x.outil==='verifier_menu'){const v=x.sortie||{};compare.append(el('article',{class:'attempt '+(v.ok?'passed':'failed')},el('strong',{},'Appel '+(i+1)+' · '+(v.ok?'Accepté':'Refusé')),el('p',{},'Énergie : '+(v.kcal??'—')+' kcal · cible '+(r.besoins?.kcal??'—')+' kcal | Protéines : '+(v.proteines_g??'—')+' g | Coût : '+(v.cout_dt??'—')+' DT'),el('ul',{},(v.problemes||[]).map(t=>el('li',{},t)))));}
 if(!rejected.length)compare.append(el('p',{},'Aucun refus de menu enregistré dans cette exécution.')); zone.append(compare); if(r.verification&&r.besoins)zone.append(carteControles(r,p)); const journal=carteJournal(j); const filter=el('select',{'aria-label':'Filtrer le journal'},el('option',{value:'all'},'Tous les appels'),el('option',{value:'errors'},'Refus et erreurs uniquement'));filter.addEventListener('change',()=>journal.querySelectorAll('.step').forEach((d,i)=>d.hidden=filter.value==='errors'&&!decrire(j[i]).refuse));journal.insertBefore(filter,journal.children[2]||null);zone.append(journal); }
async function history(){try{const res=await fetch('/plans');if(!res.ok)throw Error();const rows=await res.json();const list=$('history');for(const x of rows){const b=el('button',{class:'history-item',type:'button'},'Plan #'+x.id+' · '+x.date);b.onclick=async()=>{try{const rr=await fetch('/plans/'+x.id);if(!rr.ok)throw Error();const d=await rr.json();renderAgent(JSON.parse(d.plan_json),JSON.parse(d.profil_json));}catch(_){zone.textContent='Impossible de charger ce plan.';}};list.append(b);}if(!rows.length)list.textContent='Aucun plan enregistré.';}catch(_){$('history').textContent='Historique indisponible.';}}
try{const saved=JSON.parse(sessionStorage.getItem('nutrifit:last'));if(saved)renderAgent(saved.r,saved.profil);}catch(_){} history();
