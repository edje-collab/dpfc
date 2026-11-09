#!/usr/bin/env python3
"""
Rend le manuel de l'utilisateur en page consultable.

Le document de reference reste `docs/manuel-utilisateur.md` : cette page en
derive, de sorte qu'elle ne peut pas diverger. La relancer apres chaque mise a
jour du manuel.

    python3 infra/scripts/manuel_en_page.py
"""
import argparse
import html
import re
from pathlib import Path

import markdown
from markdown.extensions.toc import slugify

RACINE = Path(__file__).resolve().parent.parent.parent
SOURCE = RACINE / "docs" / "manuel-utilisateur.md"

# Le manuel est organise par profil : chaque section de premier niveau en est
# un, hormis les deux premieres qui valent pour tout le monde.
TITRE_SECTION = re.compile(r"^## (\d+)\. (.+)$", re.M)


def ancre(titre: str) -> str:
    """
    Identifiant de section.

    On emprunte la fonction du rendu Markdown plutot que d'en reecrire une :
    c'est le seul moyen sur que les liens du rail tombent sur les ancres
    reellement produites — une apostrophe, par exemple, y est supprimee et non
    remplacee par un tiret.
    """
    return slugify(titre, "-")


def sommaire(texte: str) -> str:
    entrees = []
    for numero, titre in TITRE_SECTION.findall(texte):
        if titre.startswith("Questions") or titre.startswith("Pour aller"):
            continue
        entrees.append(
            f'<li><a href="#{numero}-{ancre(titre)}">'
            f'<span class="rail__num">{numero}</span>'
            f'<span>{html.escape(titre)}</span></a></li>'
        )
    return "".join(entrees)


def rendre(source: Path) -> str:
    texte = source.read_text(encoding="utf-8")
    # Le sommaire du Markdown fait doublon avec le rail de navigation.
    debut = texte.index("## 1. Se connecter")
    corps = markdown.markdown(
        texte[debut:],
        extensions=["tables", "toc", "sane_lists"],
        extension_configs={"toc": {"permalink": False}},
    )
    return GABARIT.format(sommaire=sommaire(texte), corps=corps)


GABARIT = """<title>Manuel de la plateforme DPFC</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
/* Manuel par profil : rail de sections a gauche, colonne de lecture a droite.
   Meme encre teal que le cahier des charges, accent ocre sur les reperes. */
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
  --display: "Archivo", system-ui, sans-serif;
  --texte: "Source Serif 4", Georgia, serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --fond: #111817; --fond-creux: #18211f; --papier: #192221;
    --encre: #e8efed; --encre-douce: #93a7a4; --trait: #2a3634;
    --teal: #4fb3a6; --teal-clair: #6ec9bb;
    --ocre: #e0a95f; --ocre-fond: #2e2415;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --fond: #111817; --fond-creux: #18211f; --papier: #192221;
  --encre: #e8efed; --encre-douce: #93a7a4; --trait: #2a3634;
  --teal: #4fb3a6; --teal-clair: #6ec9bb;
  --ocre: #e0a95f; --ocre-fond: #2e2415;
  color-scheme: dark;
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--fond); color: var(--encre);
  font-family: var(--texte); font-size: 1.02rem; line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}}
:focus-visible {{ outline: 2px solid var(--ocre); outline-offset: 2px; border-radius: 3px; }}
html {{ scroll-behavior: smooth; }}
@media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}

.banniere {{ background: var(--teal); color: #fff; }}
.banniere__inner {{
  max-width: 1180px; margin-inline: auto;
  padding-block: clamp(1.8rem, 4.5vw, 2.8rem);
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
}}
.surtitre {{
  font-family: var(--display); font-size: .72rem; font-weight: 600;
  letter-spacing: .14em; text-transform: uppercase; color: #a8ded6; margin: 0 0 .8rem;
}}
.banniere h1 {{
  font-family: var(--display); font-size: clamp(1.7rem, 4vw, 2.5rem); font-weight: 700;
  line-height: 1.15; margin: 0; max-width: 22ch; text-wrap: balance;
}}
.banniere p.intro {{ color: #cfeae5; max-width: 60ch; margin: .8rem 0 0; }}

.page {{
  max-width: 1180px; margin-inline: auto;
  padding-block: 2rem 4rem;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 2.5rem; grid-template-columns: 250px minmax(0, 1fr);
  align-items: start;
}}
@media (max-width: 900px) {{ .page {{ grid-template-columns: 1fr; gap: 1.5rem; }} }}

.rail {{ position: sticky; top: calc(1rem + env(safe-area-inset-top, 0px)); }}
@media (max-width: 900px) {{ .rail {{ position: static; }} }}
.rail h2 {{
  font-family: var(--display); font-size: .72rem; font-weight: 600;
  letter-spacing: .12em; text-transform: uppercase; color: var(--encre-douce);
  margin: 0 0 .7rem;
}}
.rail ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 1px; }}
.rail a {{
  display: flex; gap: .6rem; align-items: baseline;
  padding: .34rem .5rem; border-radius: 6px; text-decoration: none;
  font-family: var(--display); font-size: .88rem; color: var(--encre);
}}
.rail a:hover {{ background: var(--fond-creux); color: var(--teal); }}
.rail__num {{
  font-family: var(--mono); font-size: .72rem; color: var(--encre-douce);
  min-width: 1.3em; font-variant-numeric: tabular-nums;
}}

/* --- Corps du manuel --------------------------------------------------- */
.manuel {{ min-width: 0; }}
.manuel h2 {{
  font-family: var(--display); font-size: 1.5rem; font-weight: 700; line-height: 1.2;
  margin: 3rem 0 1rem; padding-bottom: .5rem; border-bottom: 2px solid var(--teal);
  scroll-margin-top: 1.5rem; text-wrap: balance;
}}
.manuel h2:first-child {{ margin-top: 0; }}
.manuel h3 {{
  font-family: var(--display); font-size: 1.12rem; font-weight: 600;
  margin: 2rem 0 .6rem; color: var(--teal); scroll-margin-top: 1.5rem;
}}
.manuel h4 {{
  font-family: var(--display); font-size: .96rem; font-weight: 600;
  margin: 1.4rem 0 .4rem;
}}
.manuel p {{ margin: 0 0 .9rem; max-width: 68ch; }}
.manuel ul, .manuel ol {{ margin: 0 0 .9rem; padding-left: 1.3rem; max-width: 68ch; }}
.manuel li {{ margin-bottom: .3rem; }}
.manuel li > p {{ margin-bottom: .4rem; }}
.manuel strong {{ font-weight: 600; }}
.manuel a {{ color: var(--teal); text-underline-offset: 2px; }}
.manuel hr {{ border: 0; border-top: 1px solid var(--trait); margin: 2.5rem 0; }}

.manuel code {{
  font-family: var(--mono); font-size: .84em; background: var(--fond-creux);
  padding: .1em .35em; border-radius: 4px; word-break: break-word;
}}
.manuel pre {{
  background: var(--fond-creux); border: 1px solid var(--trait); border-radius: 8px;
  padding: .9rem 1rem; overflow-x: auto; font-size: .86rem; line-height: 1.5;
}}
.manuel pre code {{ background: none; padding: 0; }}

.manuel blockquote {{
  margin: 1.2rem 0; padding: .85rem 1.1rem;
  background: var(--ocre-fond); border-left: 3px solid var(--ocre);
  border-radius: 0 8px 8px 0;
}}
.manuel blockquote p {{ margin: 0; }}
.manuel blockquote p + p {{ margin-top: .6rem; }}

.manuel table {{
  width: 100%; border-collapse: collapse; margin: 0 0 1.2rem; font-size: .95rem;
}}
.manuel table th, .manuel table td {{
  text-align: left; padding: .5rem .6rem; border-bottom: 1px solid var(--trait);
  vertical-align: top;
}}
.manuel table th {{
  font-family: var(--display); font-size: .76rem; font-weight: 600;
  letter-spacing: .04em; text-transform: uppercase; color: var(--encre-douce);
}}
.manuel table tr:last-child td {{ border-bottom: 0; }}

.pied {{ border-top: 1px solid var(--trait); background: var(--fond-creux); }}
.pied__inner {{
  max-width: 1180px; margin-inline: auto;
  padding-block: 1.6rem 2.2rem;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  font-size: .9rem; color: var(--encre-douce);
}}
.pied code {{ font-family: var(--mono); font-size: .85em; }}
</style>

<header class="banniere">
  <div class="banniere__inner">
    <p class="surtitre">Manuel de l'utilisateur</p>
    <h1>Plateforme de gestion de la Direction de la Pédagogie et de la Formation Continue</h1>
    <p class="intro">
      Trouvez votre profil dans le sommaire, lisez la section qui vous concerne,
      ignorez le reste. Les deux premières valent pour tout le monde.
    </p>
  </div>
</header>

<div class="page">
  <nav class="rail" aria-label="Sections du manuel">
    <h2>Profils</h2>
    <ul>{sommaire}</ul>
  </nav>
  <main class="manuel">{corps}</main>
</div>

<footer class="pied">
  <div class="pied__inner">
    <p>
      Ce manuel dérive de <code>docs/manuel-utilisateur.md</code> et se régénère par
      <code>python3 infra/scripts/manuel_en_page.py</code>.
    </p>
  </div>
</footer>
"""


def principal():
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--source", type=Path, default=SOURCE)
    analyseur.add_argument(
        "--sortie", type=Path, default=RACINE / "docs" / "manuel-utilisateur.html"
    )
    options = analyseur.parse_args()

    page = rendre(options.source)
    options.sortie.write_text(page, encoding="utf-8")
    sections = len(TITRE_SECTION.findall(options.source.read_text(encoding="utf-8")))
    print(f"{options.sortie} : {sections} section(s), {len(page) // 1024} Ko.")


if __name__ == "__main__":
    principal()
