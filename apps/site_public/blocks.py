"""Blocs de contenu (StreamField) partages par les pages editoriales du site public."""
from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageBlock

FONCTIONS_TEXTE = ["bold", "italic", "h3", "h4", "ol", "ul", "link", "document-link", "hr"]


class BlocImage(blocks.StructBlock):
    image = ImageBlock()
    legende = blocks.CharBlock(label="legende", required=False, max_length=200)

    class Meta:
        icon = "image"
        label = "Image"
        template = "public/blocs/image.html"


class BlocDocument(blocks.StructBlock):
    document = DocumentChooserBlock(label="document")
    description = blocks.CharBlock(label="description", required=False, max_length=250)

    class Meta:
        icon = "doc-full"
        label = "Document a telecharger"
        template = "public/blocs/document.html"


class BlocCitation(blocks.StructBlock):
    texte = blocks.TextBlock(label="citation")
    auteur = blocks.CharBlock(label="auteur", required=False, max_length=120)

    class Meta:
        icon = "openquote"
        label = "Citation"
        template = "public/blocs/citation.html"


class BlocEncadre(blocks.StructBlock):
    titre = blocks.CharBlock(label="titre", max_length=120)
    texte = blocks.RichTextBlock(label="texte", features=FONCTIONS_TEXTE)
    ton = blocks.ChoiceBlock(
        label="couleur",
        choices=[("menthe", "Vert clair"), ("ocre", "Ocre"), ("azur", "Azur")],
        default="menthe",
    )

    class Meta:
        icon = "info-circle"
        label = "Encadre"
        template = "public/blocs/encadre.html"


class BlocLien(blocks.StructBlock):
    libelle = blocks.CharBlock(label="libelle", max_length=120)
    page = blocks.PageChooserBlock(label="page du site", required=False)
    url = blocks.URLBlock(label="ou adresse externe", required=False)

    def get_url(self, valeur):
        if valeur.get("page"):
            return valeur["page"].url
        return valeur.get("url") or "#"


class BlocLiens(blocks.StructBlock):
    titre = blocks.CharBlock(label="titre", required=False, max_length=120)
    liens = blocks.ListBlock(BlocLien(), label="liens")

    class Meta:
        icon = "link"
        label = "Liste de liens"
        template = "public/blocs/liens.html"


BLOCS_EDITORIAUX = [
    ("paragraphe", blocks.RichTextBlock(label="Paragraphe", features=FONCTIONS_TEXTE)),
    ("titre", blocks.CharBlock(label="Titre de section", max_length=150, form_classname="title")),
    ("image", BlocImage()),
    ("document", BlocDocument()),
    ("citation", BlocCitation()),
    ("encadre", BlocEncadre()),
    ("liens", BlocLiens()),
    ("video", EmbedBlock(label="Video (YouTube...)", max_width=800, max_height=450)),
]
