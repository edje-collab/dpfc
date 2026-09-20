from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from apps.core.models import JournalAction, Region, Structure

from .forms import AgentForm, ConnexionForm, ImportAgentsForm, ProfilForm
from .imports import analyser, appliquer, generer_modele, lire_fichier
from .models import Agent, Notification


@method_decorator(never_cache, name="dispatch")
class ConnexionView(LoginView):
    template_name = "intranet/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        reponse = super().form_valid(form)
        JournalAction.tracer(self.request.user, "Connexion a l'intranet", requete=self.request)
        if self.request.user.doit_changer_mot_de_passe:
            messages.warning(
                self.request,
                "Votre mot de passe est provisoire. Changez-le des maintenant pour securiser votre compte.",
            )
            return redirect("accounts:changer_mot_de_passe")
        return reponse


class DeconnexionView(LogoutView):
    next_page = "/"


class ChangerMotDePasseView(PasswordChangeView):
    template_name = "intranet/changer_mot_de_passe.html"
    success_url = reverse_lazy("rh:tableau_bord")

    def form_valid(self, form):
        reponse = super().form_valid(form)
        Agent.objects.filter(pk=self.request.user.pk).update(doit_changer_mot_de_passe=False)
        messages.success(self.request, "Mot de passe mis a jour.")
        return reponse


@login_required
def profil(request):
    form = ProfilForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil enregistre.")
        return redirect("accounts:profil")
    return render(request, "intranet/profil.html", {"form": form})


@login_required
def annuaire(request):
    """Annuaire des agents : direction centrale et antennes regionales."""
    agents = (
        Agent.objects.filter(is_active=True)
        .select_related("structure", "structure__region")
        .order_by("last_name", "first_name")
    )
    q = request.GET.get("q", "").strip()
    rattachement = request.GET.get("rattachement", "")
    region = request.GET.get("region", "")
    structure = request.GET.get("structure", "")

    if q:
        agents = agents.filter(
            Q(last_name__icontains=q)
            | Q(first_name__icontains=q)
            | Q(matricule__icontains=q)
            | Q(fonction__icontains=q)
            | Q(email__icontains=q)
        )
    if rattachement:
        agents = agents.filter(structure__rattachement=rattachement)
    if region:
        agents = agents.filter(structure__region__code=region)
    if structure:
        agents = agents.filter(structure__slug=structure)

    contexte = {
        "agents": agents[:300],
        "total": agents.count(),
        "q": q,
        "rattachement": rattachement,
        "region_active": region,
        "structure_active": structure,
        "regions": Region.objects.all(),
        "structures": Structure.objects.filter(active=True).select_related("region"),
        "rattachements": Structure.Rattachement.choices,
    }
    return render(request, "intranet/annuaire.html", contexte)


@login_required
def agent_detail(request, pk):
    agent = get_object_or_404(
        Agent.objects.select_related("structure", "structure__region", "superieur"), pk=pk
    )
    return render(
        request,
        "intranet/agent_detail.html",
        {"agent_fiche": agent, "subordonnes": agent.equipe()},
    )


@login_required
def organigramme(request):
    centrale = (
        Structure.objects.filter(rattachement=Structure.Rattachement.CENTRALE, active=True)
        .select_related("responsable", "parent")
        .prefetch_related("agents")
    )
    antennes = (
        Structure.objects.filter(rattachement=Structure.Rattachement.REGION, active=True)
        .select_related("region", "responsable")
        .prefetch_related("agents")
    )
    return render(
        request,
        "intranet/organigramme.html",
        {"structures_centrales": centrale, "antennes": antennes},
    )


@login_required
def notifications(request):
    liste = request.user.notifications.all()[:100]
    request.user.notifications.filter(lue=False).update(lue=True)
    return render(request, "intranet/notifications.html", {"notifications": liste})


@login_required
def notification_ouvrir(request, pk):
    notif = get_object_or_404(Notification, pk=pk, destinataire=request.user)
    notif.lue = True
    notif.save(update_fields=["lue"])
    return redirect(notif.lien or "rh:tableau_bord")


# --- Gestion des comptes (service du personnel / administrateur) -------------
def _peut_gerer_comptes(agent):
    return agent.est_rh or agent.peut_administrer


@login_required
def comptes_liste(request):
    if not _peut_gerer_comptes(request.user):
        messages.error(request, "Acces reserve au service du personnel.")
        return redirect("rh:tableau_bord")
    agents = Agent.objects.select_related("structure").order_by("last_name")
    q = request.GET.get("q", "").strip()
    if q:
        agents = agents.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(matricule__icontains=q)
        )
    return render(request, "intranet/comptes_liste.html", {"agents": agents[:400], "q": q})


@login_required
def compte_editer(request, pk=None):
    if not _peut_gerer_comptes(request.user):
        messages.error(request, "Acces reserve au service du personnel.")
        return redirect("rh:tableau_bord")
    agent = get_object_or_404(Agent, pk=pk) if pk else None
    form = AgentForm(request.POST or None, instance=agent)
    if request.method == "POST" and form.is_valid():
        cree = agent is None
        agent = form.save()
        JournalAction.tracer(
            request.user,
            "Creation d'un compte agent" if cree else "Modification d'un compte agent",
            agent.matricule,
            requete=request,
        )
        messages.success(
            request,
            f"Compte {'cree' if cree else 'mis a jour'} pour {agent.nom_complet}."
            + (" Le mot de passe initial est le matricule." if cree else ""),
        )
        return redirect("accounts:comptes_liste")
    return render(request, "intranet/compte_form.html", {"form": form, "agent_edite": agent})


@login_required
def compte_basculer_activation(request, pk):
    if not _peut_gerer_comptes(request.user) or request.method != "POST":
        return redirect("accounts:comptes_liste")
    agent = get_object_or_404(Agent, pk=pk)
    agent.is_active = not agent.is_active
    agent.save(update_fields=["is_active"])
    JournalAction.tracer(
        request.user,
        "Activation d'un compte" if agent.is_active else "Desactivation d'un compte",
        agent.matricule,
        requete=request,
    )
    messages.success(
        request, f"Compte de {agent.nom_complet} {'active' if agent.is_active else 'desactive'}."
    )
    return redirect("accounts:comptes_liste")


@login_required
def compte_reinitialiser_mot_de_passe(request, pk):
    if not _peut_gerer_comptes(request.user) or request.method != "POST":
        return redirect("accounts:comptes_liste")
    agent = get_object_or_404(Agent, pk=pk)
    agent.set_password(agent.matricule)
    agent.doit_changer_mot_de_passe = True
    agent.save(update_fields=["password", "doit_changer_mot_de_passe"])
    JournalAction.tracer(request.user, "Reinitialisation de mot de passe", agent.matricule, requete=request)
    messages.success(
        request,
        f"Mot de passe de {agent.nom_complet} reinitialise : il correspond desormais au matricule.",
    )
    return redirect("accounts:comptes_liste")


# --- Import en masse des agents ---------------------------------------------
@login_required
def import_agents(request):
    """Import Excel/CSV en deux temps : analyse puis application."""
    if not _peut_gerer_comptes(request.user):
        messages.error(request, "Import reserve au service du personnel.")
        return redirect("rh:tableau_bord")

    form = ImportAgentsForm()
    resultats = request.session.get("import_agents") or []

    if request.method == "POST" and request.POST.get("action") == "appliquer":
        if not resultats:
            messages.error(request, "Aucune analyse en memoire : deposez a nouveau le fichier.")
            return redirect("accounts:import_agents")
        compte = appliquer(resultats, auteur=request.user)
        JournalAction.tracer(
            request.user,
            "Import d'agents",
            f"{compte['crees']} creations, {compte['mis_a_jour']} mises a jour",
            requete=request,
        )
        request.session.pop("import_agents", None)
        messages.success(
            request,
            f"Import termine : {compte['crees']} compte(s) cree(s), "
            f"{compte['mis_a_jour']} mis a jour, {compte['ignores']} ligne(s) ignoree(s). "
            "Le mot de passe initial des nouveaux comptes est le matricule.",
        )
        return redirect("accounts:comptes_liste")

    if request.method == "POST" and request.POST.get("action") == "abandonner":
        request.session.pop("import_agents", None)
        return redirect("accounts:import_agents")

    if request.method == "POST" and request.FILES:
        form = ImportAgentsForm(request.POST, request.FILES)
        if form.is_valid():
            fichier = form.cleaned_data["fichier"]
            lignes, erreur = lire_fichier(fichier, fichier.name)
            if erreur:
                messages.error(request, erreur)
            else:
                resultats = analyser(lignes)
                request.session["import_agents"] = resultats
                valides = sum(1 for r in resultats if r["action"] != "erreur")
                messages.info(
                    request,
                    f"{len(resultats)} ligne(s) analysee(s), {valides} prete(s) a etre importee(s). "
                    "Verifiez le tableau avant de confirmer.",
                )

    return render(
        request,
        "intranet/import_agents.html",
        {
            "form": form,
            "resultats": resultats,
            "nb_creations": sum(1 for r in resultats if r["action"] == "creation"),
            "nb_maj": sum(1 for r in resultats if r["action"] == "mise_a_jour"),
            "nb_erreurs": sum(1 for r in resultats if r["action"] == "erreur"),
        },
    )


@login_required
def modele_import(request):
    """Telechargement du classeur modele, pre-rempli avec les structures existantes."""
    if not _peut_gerer_comptes(request.user):
        return redirect("rh:tableau_bord")
    contenu = generer_modele()
    reponse = HttpResponse(
        contenu,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    reponse["Content-Disposition"] = "attachment; filename=modele-import-agents-dpfc.xlsx"
    return reponse
