"""
Reprise des donnees existantes vers l'organisation du decret n° 2026-509.

  - les structures de type DRENAET deviennent des DRENA (article 41) ;
  - un perimetre de gestion est cree pour la direction centrale, pour chaque
    antenne et pour le CNRPN, puis rattache aux structures correspondantes.

La migration est sans effet sur une base vierge.
"""
from django.db import migrations
from django.utils.text import slugify


def _code_perimetre(structure):
    if structure.sigle:
        return structure.sigle[:20]
    return slugify(structure.nom)[:20].upper() or f"P{structure.pk}"


def reprendre(apps, schema_editor):
    Structure = apps.get_model("core", "Structure")
    Perimetre = apps.get_model("core", "Perimetre")

    # 1. Services exterieurs : DRENAET -> DRENA.
    Structure.objects.filter(type="DRENAET").update(type="DRENA")

    # 2. Perimetre de la direction centrale : tout ce qui n'est ni antenne,
    #    ni bureau, ni service exterieur.
    centrale = None
    tete = (
        Structure.objects.filter(type="DIRECTION", sigle="DPFC").first()
        or Structure.objects.filter(type="DIRECTION").order_by("pk").first()
    )
    if tete is not None:
        centrale, _ = Perimetre.objects.get_or_create(
            code="DPFC",
            defaults={"nom": tete.nom, "type": "CENTRALE", "actif": True},
        )
        Structure.objects.filter(
            rattachement="CENTRALE", perimetre__isnull=True
        ).update(perimetre=centrale)
        Structure.objects.filter(pk=tete.pk).update(perimetre_racine=True)

    # 3. Un perimetre autonome par antenne, avec ses bureaux.
    for antenne in Structure.objects.filter(type="ANTENNE"):
        perimetre, _ = Perimetre.objects.get_or_create(
            code=_code_perimetre(antenne),
            defaults={
                "nom": antenne.nom,
                "type": "ANTENNE",
                "region_id": antenne.region_id,
                "actif": antenne.active,
            },
        )
        Structure.objects.filter(pk=antenne.pk).update(
            perimetre=perimetre, perimetre_racine=True
        )
        Structure.objects.filter(parent_id=antenne.pk, type="BUREAU").update(perimetre=perimetre)

    # 4. Le CNRPN, s'il existait deja sous forme de service.
    for centre in Structure.objects.filter(type="CENTRE"):
        perimetre, _ = Perimetre.objects.get_or_create(
            code=_code_perimetre(centre),
            defaults={"nom": centre.nom, "type": "CENTRE", "actif": centre.active},
        )
        Structure.objects.filter(pk=centre.pk).update(perimetre=perimetre, perimetre_racine=True)


def revenir(apps, schema_editor):
    Structure = apps.get_model("core", "Structure")
    Structure.objects.filter(type="DRENA").update(type="DRENAET")
    Structure.objects.update(perimetre=None, perimetre_racine=False)
    apps.get_model("core", "Perimetre").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0005_perimetres_et_organisation_du_decret")]
    operations = [migrations.RunPython(reprendre, revenir)]
