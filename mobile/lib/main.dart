import 'package:flutter/material.dart';

import 'ecrans/accueil.dart';
import 'ecrans/connexion.dart';
import 'services/api.dart';

void main() => runApp(const ApplicationDpfc());

const couleurTeal = Color(0xFF14958A);

class ApplicationDpfc extends StatefulWidget {
  const ApplicationDpfc({super.key});

  @override
  State<ApplicationDpfc> createState() => _ApplicationDpfcState();
}

class _ApplicationDpfcState extends State<ApplicationDpfc> {
  final api = ApiDpfc();
  bool _pret = false;

  @override
  void initState() {
    super.initState();
    api.chargerSession().then((_) => setState(() => _pret = true));
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "DPFC - Espace agent",
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: couleurTeal),
        scaffoldBackgroundColor: const Color(0xFFEEF3F2),
      ),
      home: !_pret
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : (api.estConnecte ? AccueilPage(api: api) : ConnexionPage(api: api)),
    );
  }
}
