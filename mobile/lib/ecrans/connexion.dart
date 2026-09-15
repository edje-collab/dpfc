import 'package:flutter/material.dart';

import '../services/api.dart';
import 'accueil.dart';

class ConnexionPage extends StatefulWidget {
  const ConnexionPage({super.key, required this.api});

  final ApiDpfc api;

  @override
  State<ConnexionPage> createState() => _ConnexionPageState();
}

class _ConnexionPageState extends State<ConnexionPage> {
  final _matricule = TextEditingController();
  final _motDePasse = TextEditingController();
  String? _erreur;
  bool _enCours = false;

  Future<void> _connecter() async {
    setState(() {
      _enCours = true;
      _erreur = null;
    });
    try {
      await widget.api.connexion(_matricule.text.trim(), _motDePasse.text);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => AccueilPage(api: widget.api)),
      );
    } catch (e) {
      setState(() => _erreur = "Matricule ou mot de passe incorrect.");
    } finally {
      if (mounted) setState(() => _enCours = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const SizedBox(height: 40),
            const Text("Espace agent",
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600)),
            const Text("Direction de la Pedagogie et de la Formation Continue"),
            const SizedBox(height: 32),
            TextField(
              controller: _matricule,
              decoration: const InputDecoration(
                  labelText: "Matricule", border: OutlineInputBorder()),
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _motDePasse,
              obscureText: true,
              decoration: const InputDecoration(
                  labelText: "Mot de passe", border: OutlineInputBorder()),
              onSubmitted: (_) => _connecter(),
            ),
            if (_erreur != null) ...[
              const SizedBox(height: 12),
              Text(_erreur!, style: const TextStyle(color: Colors.red)),
            ],
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _enCours ? null : _connecter,
              child: Text(_enCours ? "Connexion..." : "Se connecter"),
            ),
          ],
        ),
      ),
    );
  }
}
