import 'package:flutter/material.dart';

import '../services/api.dart';

/// Controle de l'authenticite d'un acte a partir de son code de verification.
class VerificationPage extends StatefulWidget {
  const VerificationPage({super.key, required this.api});

  final ApiDpfc api;

  @override
  State<VerificationPage> createState() => _VerificationPageState();
}

class _VerificationPageState extends State<VerificationPage> {
  final _code = TextEditingController();
  Map<String, dynamic>? _resultat;
  String? _erreur;
  bool _enCours = false;

  Future<void> _verifier() async {
    setState(() {
      _enCours = true;
      _erreur = null;
      _resultat = null;
    });
    try {
      final donnees = await widget.api.verifier(_code.text.trim().toUpperCase());
      setState(() => _resultat = donnees);
    } catch (e) {
      setState(() => _erreur = "Code de verification inconnu.");
    } finally {
      if (mounted) setState(() => _enCours = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = _resultat;
    final authentique =
        r != null && r["signature_valide"] == true && r["document_intact"] == true;
    return Scaffold(
      appBar: AppBar(title: const Text("Verifier un acte")),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _code,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
              labelText: "Code de verification",
              hintText: "DPFC-XXXX-XXXX-XXXX",
              border: OutlineInputBorder(),
            ),
            onSubmitted: (_) => _verifier(),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _enCours ? null : _verifier,
            child: Text(_enCours ? "Verification..." : "Verifier"),
          ),
          if (_erreur != null) ...[
            const SizedBox(height: 16),
            Text(_erreur!, style: const TextStyle(color: Colors.red)),
          ],
          if (r != null) ...[
            const SizedBox(height: 16),
            Card(
              color: authentique ? Colors.green.shade50 : Colors.red.shade50,
              child: ListTile(
                leading: Icon(authentique ? Icons.verified : Icons.report_problem,
                    color: authentique ? Colors.green : Colors.red),
                title: Text(r["message"] as String? ?? ""),
              ),
            ),
            Card(
              child: Column(
                children: [
                  ListTile(title: const Text("Acte"), subtitle: Text("${r["acte"]} - ${r["numero"]}")),
                  ListTile(
                      title: const Text("Beneficiaire"),
                      subtitle: Text("${r["beneficiaire"]} (${r["matricule"]})")),
                  ListTile(
                      title: const Text("Periode"),
                      subtitle: Text("du ${r["date_debut"]} au ${r["date_fin"]}")),
                  ListTile(
                      title: const Text("Signataire"),
                      subtitle: Text("${r["signataire"]} - ${r["qualite"]}")),
                  ListTile(title: const Text("Algorithme"), subtitle: Text("${r["algorithme"]}")),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
