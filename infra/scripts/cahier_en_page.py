#!/usr/bin/env python3
"""
Rend le cahier des charges en page consultable.

Le document de reference reste `docs/cahier-des-charges.md` : cette page en
derive, de sorte qu'elle ne peut pas diverger. La relancer apres chaque mise a
jour du cahier.

    python3 infra/scripts/cahier_en_page.py            # ecrit la page
    python3 infra/scripts/cahier_en_page.py --sortie X # ailleurs
"""
import argparse
import html
import re
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
SOURCE = RACINE / "docs" / "cahier-des-charges.md"

# Domaines d'exigence, dans l'ordre de lecture du document.
DOMAINES = {
    "ORG": ("Organisation", "Périmètres de gestion et organigramme"),
    "CIR": ("Circuits", "Validation paramétrable des dossiers"),
    "ACT": ("Actes administratifs", "Congés, missions, permissions"),
    "SIG": ("Signature", "Signature électronique des actes"),
    "PIL": ("Pilotage", "Plans d'action et activités"),
    "COU": ("Courrier", "Registre arrivée et départ"),
    "GED": ("Documents", "Bibliothèque et recherche"),
    "PAR": ("Parapheur", "Visas internes"),
    "ATE": ("Ateliers", "Émargement par QR code"),
    "ACH": ("Achats", "Besoins, offres, commandes"),
    "STO": ("Stocks", "Magasin et équipements"),
    "PUB": ("Site public", "Contenus éditoriaux"),
    "SEC": ("Sécurité", "Droits, traçabilité, chiffrement"),
    "TEC": ("Technique", "Architecture et déploiement"),
    "QUA": ("Qualités attendues", "Règles transverses de conception"),
}

LIGNE_EXIGENCE = re.compile(r"^\|\s*\*\*([A-Z]{3}-\d{2})\*\*\s*\|\s*(.+?)\s*\|\s*$")
LIGNE_MATRICE = re.compile(r"^\|\s*([A-Z]{3}-\d{2})\s*\|\s*(.+?)\s*\|\s*$")
LIGNE_AUTREMENT = re.compile(r"^\|\s*([A-Z]{3}-\d{2})\s*\|\s*(.+?)\s*\|\s*$")


@dataclass
class Exigence:
    code: str
    texte: str
    preuves: list[str] = field(default_factory=list)
    verification: str = ""


def _enrichir(texte: str) -> str:
    """Gras et code du Markdown vers HTML, le reste etant echappe."""
    morceaux = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", texte)
    rendu = []
    for morceau in morceaux:
        if morceau.startswith("**") and morceau.endswith("**"):
            rendu.append(f"<strong>{html.escape(morceau[2:-2])}</strong>")
        elif morceau.startswith("`") and morceau.endswith("`"):
            rendu.append(f"<code>{html.escape(morceau[1:-1])}</code>")
        else:
            rendu.append(html.escape(morceau))
    return "".join(rendu)


def lire(source: Path) -> tuple[dict[str, Exigence], dict[str, str]]:
    texte = source.read_text(encoding="utf-8")
    debut_matrice = texte.index("## 15. Matrice de traçabilité")
    debut_autrement = texte.index("### 15.1 Exigences vérifiées autrement")
    fin_matrice = texte.index("## 16.")

    corps = texte[:debut_matrice]
    matrice = texte[debut_matrice:debut_autrement]
    autrement = texte[debut_autrement:fin_matrice]

    exigences: dict[str, Exigence] = {}
    for ligne in corps.splitlines():
        if m := LIGNE_EXIGENCE.match(ligne):
            exigences[m.group(1)] = Exigence(code=m.group(1), texte=m.group(2))

    for ligne in matrice.splitlines():
        if (m := LIGNE_MATRICE.match(ligne)) and m.group(1) in exigences:
            preuves = [
                p.strip().strip("`")
                for p in m.group(2).split("<br>")
                if p.strip().strip("`")
            ]
            exigences[m.group(1)].preuves = preuves

    for ligne in autrement.splitlines():
        if (m := LIGNE_AUTREMENT.match(ligne)) and m.group(1) in exigences:
            exigences[m.group(1)].verification = m.group(2)

    # Entete du document : maitre d'ouvrage, version, reference.
    entete = {}
    for ligne in texte[: texte.index("## 1.")].splitlines():
        if m := re.match(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$", ligne):
            entete[m.group(1)] = m.group(2)
    return exigences, entete


def rendre_exigence(exigence: Exigence) -> str:
    if exigence.preuves:
        preuves = "".join(
            f'<li><code>{html.escape(p)}</code></li>' for p in exigence.preuves
        )
        pied = (
            f'<div class="preuves"><span class="preuves__titre">'
            f'Vérifiée par {len(exigence.preuves)} test'
            f'{"s" if len(exigence.preuves) > 1 else ""}</span>'
            f'<ul>{preuves}</ul></div>'
        )
        etat = '<span class="etat etat--teste">testée</span>'
    elif exigence.verification:
        pied = (
            '<div class="preuves"><span class="preuves__titre">Mode de vérification</span>'
            f'<p>{_enrichir(exigence.verification)}</p></div>'
        )
        etat = '<span class="etat etat--autre">contrôlée</span>'
    else:
        pied = ""
        etat = '<span class="etat etat--autre">—</span>'

    return (
        f'<article class="exigence" id="{exigence.code}" '
        f'data-recherche="{html.escape((exigence.code + " " + exigence.texte).lower())}">'
        f'<header class="exigence__tete">'
        f'<a class="exigence__code" href="#{exigence.code}">{exigence.code}</a>{etat}'
        f"</header>"
        f'<p class="exigence__texte">{_enrichir(exigence.texte)}</p>'
        f"{pied}</article>"
    )


def rendre(exigences: dict[str, Exigence], entete: dict[str, str]) -> str:
    par_domaine: dict[str, list[Exigence]] = {cle: [] for cle in DOMAINES}
    for exigence in exigences.values():
        par_domaine.setdefault(exigence.code[:3], []).append(exigence)

    nav, sections = [], []
    for prefixe, (titre, sous_titre) in DOMAINES.items():
        lot = sorted(par_domaine.get(prefixe, []), key=lambda e: e.code)
        if not lot:
            continue
        nav.append(
            f'<li><a href="#d-{prefixe}"><span>{html.escape(titre)}</span>'
            f'<span class="nav__compte">{len(lot)}</span></a></li>'
        )
        sections.append(
            f'<section class="domaine" id="d-{prefixe}" data-domaine="{prefixe}">'
            f'<header class="domaine__tete">'
            f'<span class="domaine__sigle">{prefixe}</span>'
            f"<div><h2>{html.escape(titre)}</h2>"
            f'<p>{html.escape(sous_titre)}</p></div></header>'
            f'<div class="exigences">{"".join(rendre_exigence(e) for e in lot)}</div>'
            f"</section>"
        )

    total = len(exigences)
    testees = sum(1 for e in exigences.values() if e.preuves)
    preuves = sum(len(e.preuves) for e in exigences.values())

    return GABARIT.format(
        nav="".join(nav),
        sections="".join(sections),
        total=total,
        testees=testees,
        preuves=preuves,
        domaines=len([p for p in DOMAINES if par_domaine.get(p)]),
        version=html.escape(entete.get("Version", "")),
        reference=html.escape(entete.get("Référence réglementaire", "")),
        tutelle=html.escape(entete.get("Tutelle", "")),
        ministere=html.escape(entete.get("Ministère", "")),
    )


GABARIT = """<title>Cahier des charges DPFC</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Document de reference : rail de navigation a gauche, colonne de lecture a droite.
   Palette tiree de l'identite de la direction — encre teal, accent ocre. */
:root {{
  --fond: #fbfaf7;
  --fond-creux: #f2f1ec;
  --papier: #ffffff;
  --encre: #15312f;
  --encre-douce: #5c716f;
  --trait: #e0e2dd;
  --teal: #0d6b64;
  --teal-clair: #14958a;
  --ocre: #b5751a;
  --ocre-fond: #fdf3e2;
  --vert-fond: #e7f3ec;
  --vert-encre: #246b45;
  --display: "Archivo", system-ui, sans-serif;
  --texte: "Source Serif 4", Georgia, serif;
  --mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --fond: #111817;
    --fond-creux: #18211f;
    --papier: #192221;
    --encre: #e8efed;
    --encre-douce: #93a7a4;
    --trait: #2a3634;
    --teal: #4fb3a6;
    --teal-clair: #6ec9bb;
    --ocre: #e0a95f;
    --ocre-fond: #2e2415;
    --vert-fond: #162b20;
    --vert-encre: #7fc79b;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --fond: #111817;
  --fond-creux: #18211f;
  --papier: #192221;
  --encre: #e8efed;
  --encre-douce: #93a7a4;
  --trait: #2a3634;
  --teal: #4fb3a6;
  --teal-clair: #6ec9bb;
  --ocre: #e0a95f;
  --ocre-fond: #2e2415;
  --vert-fond: #162b20;
  --vert-encre: #7fc79b;
  color-scheme: dark;
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--fond);
  color: var(--encre);
  font-family: var(--texte);
  font-size: 1rem;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
h1, h2, h3 {{ font-family: var(--display); line-height: 1.15; text-wrap: balance; margin: 0; }}
code {{ font-family: var(--mono); font-size: .84em; }}
a {{ color: inherit; }}
:focus-visible {{ outline: 2px solid var(--ocre); outline-offset: 2px; border-radius: 3px; }}

/* --- Banniere --------------------------------------------------------- */
.banniere {{ background: var(--teal); color: #fff; }}
.banniere__inner {{
  max-width: 1180px; margin-inline: auto;
  padding-block: clamp(2rem, 5vw, 3.2rem);
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
}}
.surtitre {{
  font-family: var(--display); font-size: .72rem; font-weight: 600;
  letter-spacing: .14em; text-transform: uppercase; color: #a8ded6; margin: 0 0 .9rem;
}}
.banniere h1 {{ font-size: clamp(1.75rem, 4.4vw, 2.75rem); font-weight: 700; max-width: 20ch; }}
.banniere__sous {{
  font-size: 1.05rem; color: #cfeae5; max-width: 62ch; margin: .9rem 0 0;
}}
.jetons {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.6rem; }}
.jeton {{
  font-family: var(--mono); font-size: .76rem; padding: .3rem .7rem;
  border: 1px solid rgba(255,255,255,.3); border-radius: 999px; color: #e4f4f1;
}}

/* --- Chiffres --------------------------------------------------------- */
.chiffres {{
  max-width: 1180px; margin-inline: auto;
  padding-block: 1.6rem;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 1px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}}
.chiffre {{ padding: .3rem .2rem; }}
.chiffre strong {{
  display: block; font-family: var(--display); font-size: 2rem; font-weight: 700;
  color: var(--teal-clair); line-height: 1; font-variant-numeric: tabular-nums;
}}
.chiffre span {{ font-size: .88rem; color: var(--encre-douce); }}

/* --- Mise en page ----------------------------------------------------- */
.page {{
  max-width: 1180px; margin-inline: auto;
  padding-block: 0 4rem;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 2.5rem; grid-template-columns: 230px minmax(0, 1fr);
  align-items: start;
}}
@media (max-width: 860px) {{ .page {{ grid-template-columns: 1fr; gap: 1.5rem; }} }}

.rail {{ position: sticky; top: calc(1rem + env(safe-area-inset-top, 0px)); }}
@media (max-width: 860px) {{ .rail {{ position: static; }} }}
.rail h2 {{
  font-size: .72rem; font-weight: 600; letter-spacing: .12em;
  text-transform: uppercase; color: var(--encre-douce); margin-bottom: .7rem;
}}
.rail ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 1px; }}
.rail a {{
  display: flex; justify-content: space-between; align-items: center; gap: .6rem;
  padding: .36rem .55rem; border-radius: 6px; text-decoration: none;
  font-family: var(--display); font-size: .88rem; color: var(--encre);
}}
.rail a:hover {{ background: var(--fond-creux); color: var(--teal); }}
.nav__compte {{
  font-family: var(--mono); font-size: .72rem; color: var(--encre-douce);
  font-variant-numeric: tabular-nums;
}}

/* --- Recherche -------------------------------------------------------- */
.recherche {{ margin-bottom: 2rem; }}
.recherche label {{
  display: block; font-family: var(--display); font-size: .72rem; font-weight: 600;
  letter-spacing: .12em; text-transform: uppercase; color: var(--encre-douce);
  margin-bottom: .45rem;
}}
.recherche input {{
  width: 100%; padding: .65rem .85rem; font-family: var(--texte); font-size: 1rem;
  background: var(--papier); color: var(--encre);
  border: 1px solid var(--trait); border-radius: 8px;
}}
.recherche input:focus {{ outline: 2px solid var(--teal-clair); outline-offset: -1px; border-color: var(--teal-clair); }}
.recherche__aide {{ font-size: .84rem; color: var(--encre-douce); margin: .45rem 0 0; }}
.vide {{
  display: none; padding: 2rem; text-align: center; color: var(--encre-douce);
  background: var(--fond-creux); border-radius: 10px;
}}

/* --- Domaines et exigences -------------------------------------------- */
.domaine {{ margin-bottom: 2.8rem; scroll-margin-top: 1.5rem; }}
.domaine__tete {{
  display: flex; gap: .9rem; align-items: baseline;
  padding-bottom: .7rem; border-bottom: 2px solid var(--teal); margin-bottom: 1.1rem;
}}
.domaine__sigle {{
  font-family: var(--mono); font-size: .8rem; font-weight: 500;
  color: var(--teal); letter-spacing: .06em;
}}
.domaine__tete h2 {{ font-size: 1.3rem; font-weight: 600; }}
.domaine__tete p {{ margin: .15rem 0 0; font-size: .9rem; color: var(--encre-douce); }}

.exigences {{ display: grid; gap: .8rem; }}
.exigence {{
  background: var(--papier); border: 1px solid var(--trait); border-radius: 10px;
  padding: .95rem 1.1rem; scroll-margin-top: 1.5rem;
}}
.exigence__tete {{ display: flex; align-items: center; gap: .7rem; margin-bottom: .4rem; }}
.exigence__code {{
  font-family: var(--mono); font-size: .8rem; font-weight: 500;
  color: var(--teal); text-decoration: none; letter-spacing: .04em;
}}
.exigence__code:hover {{ text-decoration: underline; }}
.exigence__texte {{ margin: 0; }}
.etat {{
  font-family: var(--display); font-size: .66rem; font-weight: 600;
  letter-spacing: .08em; text-transform: uppercase;
  padding: .14rem .5rem; border-radius: 999px;
}}
.etat--teste {{ background: var(--vert-fond); color: var(--vert-encre); }}
.etat--autre {{ background: var(--ocre-fond); color: var(--ocre); }}

.preuves {{ margin-top: .7rem; padding-top: .65rem; border-top: 1px dashed var(--trait); }}
.preuves__titre {{
  display: block; font-family: var(--display); font-size: .68rem; font-weight: 600;
  letter-spacing: .09em; text-transform: uppercase; color: var(--encre-douce);
  margin-bottom: .35rem;
}}
.preuves ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: .22rem; }}
.preuves code {{ color: var(--encre-douce); word-break: break-word; }}
.preuves p {{ margin: 0; font-size: .92rem; color: var(--encre-douce); }}

/* --- Pied ------------------------------------------------------------- */
.pied {{
  border-top: 1px solid var(--trait); background: var(--fond-creux);
}}
.pied__inner {{
  max-width: 1180px; margin-inline: auto;
  padding-block: 1.8rem 2.4rem;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  font-size: .9rem; color: var(--encre-douce);
}}
.pied strong {{ color: var(--encre); font-family: var(--display); }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; }} }}
html {{ scroll-behavior: smooth; }}
</style>

<header class="banniere">
  <div class="banniere__inner">
    <p class="surtitre">Cahier des charges &middot; version {version}</p>
    <h1>Plateforme de gestion de la Direction de la Pédagogie et de la Formation Continue</h1>
    <p class="banniere__sous">
      Chaque exigence porte un identifiant et renvoie aux tests qui la vérifient.
      La matrice de traçabilité est contrôlée à chaque exécution de la suite de tests :
      une exigence ne peut pas être invoquée sans preuve.
    </p>
    <div class="jetons">
      <span class="jeton">{reference}</span>
      <span class="jeton">{tutelle}</span>
    </div>
  </div>
</header>

<div class="chiffres">
  <div class="chiffre"><strong>{total}</strong><span>exigences énoncées</span></div>
  <div class="chiffre"><strong>{testees}</strong><span>vérifiées par un test</span></div>
  <div class="chiffre"><strong>{preuves}</strong><span>renvois vers des tests</span></div>
  <div class="chiffre"><strong>{domaines}</strong><span>domaines</span></div>
</div>

<div class="page">
  <nav class="rail" aria-label="Domaines d'exigence">
    <h2>Domaines</h2>
    <ul>{nav}</ul>
  </nav>

  <main>
    <div class="recherche">
      <label for="filtre">Rechercher une exigence</label>
      <input id="filtre" type="search" autocomplete="off"
             placeholder="Un identifiant (STO-03) ou un mot (inventaire, périmètre, émargement)">
      <p class="recherche__aide" id="compte"></p>
    </div>
    <p class="vide" id="vide">Aucune exigence ne correspond à cette recherche.</p>
    {sections}
  </main>
</div>

<footer class="pied">
  <div class="pied__inner">
    <p><strong>{ministere}</strong></p>
    <p>
      Document tenu à jour avec le code. Il dérive de <code>docs/cahier-des-charges.md</code>
      et se régénère par <code>python3 infra/scripts/cahier_en_page.py</code>.
    </p>
  </div>
</footer>

<script>
(function () {{
  var champ = document.getElementById("filtre");
  var compte = document.getElementById("compte");
  var vide = document.getElementById("vide");
  var exigences = Array.prototype.slice.call(document.querySelectorAll(".exigence"));
  var domaines = Array.prototype.slice.call(document.querySelectorAll(".domaine"));
  var total = exigences.length;

  function accord(n) {{
    return n + " exigence" + (n > 1 ? "s" : "") + (n > 1 ? " affichées" : " affichée");
  }}

  function filtrer() {{
    var terme = champ.value.trim().toLowerCase();
    var visibles = 0;
    exigences.forEach(function (bloc) {{
      var correspond = !terme || bloc.dataset.recherche.indexOf(terme) !== -1;
      bloc.hidden = !correspond;
      if (correspond) visibles++;
    }});
    domaines.forEach(function (domaine) {{
      var reste = domaine.querySelectorAll(".exigence:not([hidden])").length;
      domaine.hidden = reste === 0;
    }});
    vide.style.display = visibles === 0 ? "block" : "none";
    compte.textContent = terme ? accord(visibles) + " sur " + total + "." : accord(total) + ".";
  }}

  champ.addEventListener("input", filtrer);
  filtrer();
}})();
</script>
"""


def principal():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--source", type=Path, default=SOURCE)
    analyseur.add_argument(
        "--sortie", type=Path, default=RACINE / "docs" / "cahier-des-charges.html"
    )
    options = analyseur.parse_args()

    exigences, entete = lire(options.source)
    options.sortie.write_text(rendre(exigences, entete), encoding="utf-8")
    testees = sum(1 for e in exigences.values() if e.preuves)
    print(
        f"{options.sortie} : {len(exigences)} exigence(s), "
        f"{testees} verifiee(s) par un test."
    )


if __name__ == "__main__":
    principal()
