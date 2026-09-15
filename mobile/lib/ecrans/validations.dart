import 'package:flutter/material.dart';

import '../services/api.dart';

class ValidationsPage extends StatefulWidget {
  const ValidationsPage({super.key, required this.api});

  final ApiDpfc api;

  @override
  State<ValidationsPage> createState() => _ValidationsPageState();
}

class _ValidationsPageState extends State<ValidationsPage> {
  late Future<List<dynamic>> _dossiers;

  @override
  void initState() {
    super.initState();
    _dossiers = widget.api.aValider();
  }

  void _recharger() => setState(() => _dossiers = widget.api.aValider());

  /// Derniere etape du circuit : l'avis favorable vaut signature de l'acte.
  bool _estEtapeDeSignature(Map<String, dynamic> demande) {
    final validations = (demande["validations"] as List<dynamic>?) ?? [];
    final restantes = validations.where((v) => v["decision"] == "ATTENTE").length;
    return restantes <= 1;
  }

  Future<void> _decider(Map<String, dynamic> demande, bool favorable) async {
    final observation = TextEditingController();
    final code = TextEditingController();
    final signature = favorable && _estEtapeDeSignature(demande);

    final valide = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(favorable ? "Avis favorable" : "Rejeter la demande"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: observation,
              decoration: InputDecoration(
                labelText: favorable ? "Observation" : "Motif du rejet",
              ),
            ),
            if (signature) ...[
              const SizedBox(height: 12),
              TextField(
                controller: code,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: "Code de signature electronique",
                  helperText: "Derniere etape : votre code signe l'acte.",
                  helperMaxLines: 2,
                ),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text("Annuler")),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text("Confirmer")),
        ],
      ),
    );
    if (valide != true) return;

    try {
      final reponse = await widget.api.decider(
        demande["id"] as int,
        favorable,
        observation.text,
        codeSignature: code.text,
      );
      if (mounted) {
        final codeVerification = reponse["code_verification"] as String?;
        final avertissement = reponse["avertissement_signature"] as String?;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
            avertissement ??
                (codeVerification != null
                    ? "Acte signe. Code de verification : $codeVerification"
                    : (favorable ? "Avis favorable enregistre." : "Demande rejetee.")),
          ),
        ));
      }
      _recharger();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text("Decision impossible : $e")));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<dynamic>>(
      future: _dossiers,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final dossiers = snapshot.data!;
        if (dossiers.isEmpty) {
          return const Center(child: Text("Aucun dossier n'attend votre decision."));
        }
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: dossiers.length,
          itemBuilder: (context, i) {
            final d = dossiers[i] as Map<String, dynamic>;
            final hors = d["hors_perimetre_drenaet"] == true;
            return Card(
              child: Column(
                children: [
                  ListTile(
                    title: Text("${d["agent_nom"]} - ${d["type_libelle"]}"),
                    subtitle: Text("${d["date_debut"]} au ${d["date_fin"]}\n${d["motif"]}"),
                    isThreeLine: true,
                  ),
                  if (hors)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Row(
                        children: [
                          const Icon(Icons.info_outline, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              "Mission hors perimetre : acte etabli par le ${d["autorite_signataire"]}",
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ),
                        ],
                      ),
                    ),
                  OverflowBar(
                    children: [
                      TextButton(onPressed: () => _decider(d, false), child: const Text("Rejeter")),
                      FilledButton(
                          onPressed: () => _decider(d, true), child: const Text("Avis favorable")),
                    ],
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}
