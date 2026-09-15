import 'package:flutter/material.dart';

import '../services/api.dart';
import 'demandes.dart';
import 'verification.dart';
import 'nouvelle_demande.dart';
import 'validations.dart';

class AccueilPage extends StatefulWidget {
  const AccueilPage({super.key, required this.api});

  final ApiDpfc api;

  @override
  State<AccueilPage> createState() => _AccueilPageState();
}

class _AccueilPageState extends State<AccueilPage> {
  int _onglet = 0;

  @override
  Widget build(BuildContext context) {
    final pages = [
      TableauBord(api: widget.api),
      DemandesPage(api: widget.api),
      ValidationsPage(api: widget.api),
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text("Espace agent DPFC"),
        actions: [
          IconButton(
            tooltip: "Verifier un acte signe",
            icon: const Icon(Icons.verified_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => VerificationPage(api: widget.api)),
            ),
          ),
          IconButton(
            tooltip: "Se deconnecter",
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await widget.api.deconnexion();
              if (context.mounted) Navigator.of(context).pop();
            },
          )
        ],
      ),
      body: pages[_onglet],
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => NouvelleDemandePage(api: widget.api)),
        ),
        label: const Text("Nouvelle demande"),
        icon: const Icon(Icons.add),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _onglet,
        onDestinationSelected: (i) => setState(() => _onglet = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: "Tableau"),
          NavigationDestination(icon: Icon(Icons.description_outlined), label: "Mes demandes"),
          NavigationDestination(icon: Icon(Icons.fact_check_outlined), label: "A valider"),
        ],
      ),
    );
  }
}

class TableauBord extends StatelessWidget {
  const TableauBord({super.key, required this.api});

  final ApiDpfc api;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<dynamic>>(
      future: Future.wait([api.profil(), api.solde(), api.notifications()]),
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final profil = snapshot.data![0] as Map<String, dynamic>;
        final solde = snapshot.data![1] as Map<String, dynamic>;
        final notifications = snapshot.data![2] as List<dynamic>;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: ListTile(
                title: Text(profil["nom_complet"] as String),
                subtitle: Text("${profil["fonction"] ?? ""}\n${profil["matricule"]}"),
                isThreeLine: true,
              ),
            ),
            Card(
              child: ListTile(
                title: Text("${solde["jours_restants"]} jours de conge restants"),
                subtitle: Text("Droits ${solde["annee"]} : ${solde["total_droits"]} jours"),
              ),
            ),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text("Notifications", style: TextStyle(fontWeight: FontWeight.w600)),
            ),
            ...notifications.take(10).map((n) => Card(
                  child: ListTile(
                    title: Text(n["titre"] as String),
                    subtitle: Text(n["message"] as String? ?? ""),
                  ),
                )),
          ],
        );
      },
    );
  }
}
