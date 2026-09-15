import 'package:flutter/material.dart';

import '../services/api.dart';

class DemandesPage extends StatefulWidget {
  const DemandesPage({super.key, required this.api});

  final ApiDpfc api;

  @override
  State<DemandesPage> createState() => _DemandesPageState();
}

class _DemandesPageState extends State<DemandesPage> {
  late Future<List<dynamic>> _demandes;

  @override
  void initState() {
    super.initState();
    _demandes = widget.api.mesDemandes();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => setState(() => _demandes = widget.api.mesDemandes()),
      child: FutureBuilder<List<dynamic>>(
        future: _demandes,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final demandes = snapshot.data!;
          if (demandes.isEmpty) {
            return const Center(child: Text("Aucune demande. Utilisez le bouton ci-dessous."));
          }
          return ListView.builder(
            itemCount: demandes.length,
            padding: const EdgeInsets.all(12),
            itemBuilder: (context, i) {
              final d = demandes[i] as Map<String, dynamic>;
              return Card(
                child: ListTile(
                  title: Text("${d["type_libelle"]} - ${d["numero"] ?? "brouillon"}"),
                  subtitle: Text("${d["date_debut"]} au ${d["date_fin"]} - ${d["nb_jours"]} j"),
                  trailing: Chip(label: Text(d["statut_libelle"] as String)),
                  onTap: () => showModalBottomSheet(
                    context: context,
                    builder: (_) => DetailDemande(api: widget.api, demande: d),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class DetailDemande extends StatelessWidget {
  const DetailDemande({super.key, required this.api, required this.demande});

  final ApiDpfc api;
  final Map<String, dynamic> demande;

  @override
  Widget build(BuildContext context) {
    final validations = (demande["validations"] as List<dynamic>?) ?? [];
    return ListView(
      padding: const EdgeInsets.all(20),
      shrinkWrap: true,
      children: [
        Text(demande["type_libelle"] as String,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Text(demande["motif"] as String? ?? ""),
        const SizedBox(height: 16),
        ...validations.map((v) => ListTile(
              dense: true,
              leading: Text("${v["ordre"]}"),
              title: Text(v["libelle"] as String),
              subtitle: Text("${v["valideur"]} - ${v["decision_libelle"]}"),
            )),
        if (demande["est_modifiable"] == true)
          FilledButton(
            onPressed: () async {
              await api.soumettre(demande["id"] as int);
              if (context.mounted) Navigator.of(context).pop();
            },
            child: const Text("Transmettre pour validation"),
          ),
      ],
    );
  }
}
