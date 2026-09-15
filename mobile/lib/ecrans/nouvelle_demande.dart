import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../services/api.dart';

const typesActe = {
  "CONGE_ANNUEL": "Conge annuel",
  "CONGE_EXCEPTIONNEL": "Conge exceptionnel",
  "PERMISSION": "Permission d'absence",
  "ORDRE_MISSION": "Ordre de mission",
  "ABSENCE": "Declaration d'absence",
  "FORMATION": "Demande de formation",
};

class NouvelleDemandePage extends StatefulWidget {
  const NouvelleDemandePage({super.key, required this.api});

  final ApiDpfc api;

  @override
  State<NouvelleDemandePage> createState() => _NouvelleDemandePageState();
}

class _NouvelleDemandePageState extends State<NouvelleDemandePage> {
  String _type = "CONGE_ANNUEL";
  DateTime _debut = DateTime.now().add(const Duration(days: 7));
  DateTime _fin = DateTime.now().add(const Duration(days: 10));
  final _motif = TextEditingController();
  final _destination = TextEditingController();
  bool _horsPerimetre = false;
  String? _cheminTdr;
  String? _cheminInvitation;
  bool _envoi = false;

  final _format = DateFormat("yyyy-MM-dd");

  bool get _estMission => _type == "ORDRE_MISSION";

  bool get _piecesCompletes =>
      !_horsPerimetre || (_cheminTdr != null && _cheminInvitation != null);

  Future<void> _choisirDate(bool debut) async {
    final choix = await showDatePicker(
      context: context,
      initialDate: debut ? _debut : _fin,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (choix != null) {
      setState(() => debut ? _debut = choix : _fin = choix);
    }
  }

  Future<void> _choisirFichier(bool tdr) async {
    final resultat = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ["pdf", "jpg", "jpeg", "png", "doc", "docx"],
    );
    final chemin = resultat?.files.single.path;
    if (chemin != null) {
      setState(() => tdr ? _cheminTdr = chemin : _cheminInvitation = chemin);
    }
  }

  Future<void> _envoyer({required bool transmettre}) async {
    if (transmettre && !_piecesCompletes) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text(
            "Mission hors perimetre : joignez les TDR et la lettre d'invitation avant de transmettre."),
      ));
      return;
    }
    setState(() => _envoi = true);
    try {
      final demande = await widget.api.creerDemande({
        "type": _type,
        "motif": _motif.text,
        "date_debut": _format.format(_debut),
        "date_fin": _format.format(_fin),
        if (_estMission) "destination": _destination.text,
        if (_estMission) "hors_perimetre_drenaet": _horsPerimetre,
      });
      final identifiant = demande["id"] as int;

      final pieces = <String, String>{
        if (_cheminTdr != null) "termes_de_reference": _cheminTdr!,
        if (_cheminInvitation != null) "lettre_invitation": _cheminInvitation!,
      };
      if (pieces.isNotEmpty) {
        await widget.api.deposerPieces(identifiant, pieces);
      }
      if (transmettre) {
        await widget.api.soumettre(identifiant);
      }
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text("Envoi impossible : $e")));
      }
    } finally {
      if (mounted) setState(() => _envoi = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Nouvelle demande")),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          DropdownButtonFormField<String>(
            value: _type,
            decoration: const InputDecoration(labelText: "Type d'acte", border: OutlineInputBorder()),
            items: typesActe.entries
                .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
                .toList(),
            onChanged: (v) => setState(() {
              _type = v ?? _type;
              if (!_estMission) _horsPerimetre = false;
            }),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _motif,
            maxLines: 3,
            decoration: const InputDecoration(labelText: "Motif", border: OutlineInputBorder()),
          ),
          if (_estMission) ...[
            const SizedBox(height: 16),
            TextField(
              controller: _destination,
              decoration: const InputDecoration(labelText: "Destination", border: OutlineInputBorder()),
            ),
            SwitchListTile(
              value: _horsPerimetre,
              onChanged: (v) => setState(() => _horsPerimetre = v),
              title: const Text("Mission hors du perimetre de la DRENAET"),
              subtitle: const Text(
                  "L'ordre de mission sera etabli par le DRENAET, sur presentation des TDR "
                  "et de la lettre d'invitation."),
            ),
            if (_horsPerimetre) ...[
              _LignePiece(
                titre: "Termes de reference (TDR)",
                chemin: _cheminTdr,
                onChoisir: () => _choisirFichier(true),
              ),
              _LignePiece(
                titre: "Lettre d'invitation ou d'information",
                chemin: _cheminInvitation,
                onChoisir: () => _choisirFichier(false),
              ),
            ],
          ],
          const SizedBox(height: 16),
          ListTile(
            title: const Text("Date de debut"),
            subtitle: Text(_format.format(_debut)),
            trailing: const Icon(Icons.calendar_today),
            onTap: () => _choisirDate(true),
          ),
          ListTile(
            title: const Text("Date de fin"),
            subtitle: Text(_format.format(_fin)),
            trailing: const Icon(Icons.calendar_today),
            onTap: () => _choisirDate(false),
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _envoi ? null : () => _envoyer(transmettre: true),
            child: const Text("Transmettre pour validation"),
          ),
          TextButton(
            onPressed: _envoi ? null : () => _envoyer(transmettre: false),
            child: const Text("Enregistrer comme brouillon"),
          ),
        ],
      ),
    );
  }
}

class _LignePiece extends StatelessWidget {
  const _LignePiece({required this.titre, required this.chemin, required this.onChoisir});

  final String titre;
  final String? chemin;
  final VoidCallback onChoisir;

  @override
  Widget build(BuildContext context) {
    final nom = chemin?.split(RegExp(r"[\\/]")).last;
    return ListTile(
      leading: Icon(chemin == null ? Icons.attach_file : Icons.check_circle,
          color: chemin == null ? null : Colors.green),
      title: Text(titre),
      subtitle: Text(nom ?? "Aucun fichier joint"),
      trailing: TextButton(onPressed: onChoisir, child: const Text("Choisir")),
    );
  }
}
