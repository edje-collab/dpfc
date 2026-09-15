import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Client de l'API du portail DPFC.
/// Adapter [baseUrl] a l'adresse du serveur (https://dpfc.education.ci en production).
class ApiDpfc {
  ApiDpfc({this.baseUrl = "http://10.0.2.2:8000/api/v1"});

  final String baseUrl;
  String? _acces;
  String? _rafraichissement;

  Map<String, String> get _entetes => {
        "Content-Type": "application/json",
        if (_acces != null) "Authorization": "Bearer $_acces",
      };

  Future<void> chargerSession() async {
    final prefs = await SharedPreferences.getInstance();
    _acces = prefs.getString("acces");
    _rafraichissement = prefs.getString("rafraichissement");
  }

  Future<void> _enregistrerSession(Map<String, dynamic> donnees) async {
    _acces = donnees["access"] as String?;
    _rafraichissement = donnees["refresh"] as String?;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString("acces", _acces ?? "");
    await prefs.setString("rafraichissement", _rafraichissement ?? "");
  }

  bool get estConnecte => _acces != null && _acces!.isNotEmpty;

  Future<Map<String, dynamic>> connexion(String matricule, String motDePasse) async {
    final reponse = await http.post(
      Uri.parse("$baseUrl/auth/connexion/"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({"matricule": matricule, "password": motDePasse}),
    );
    if (reponse.statusCode != 200) {
      throw Exception("Matricule ou mot de passe incorrect.");
    }
    final donnees = jsonDecode(utf8.decode(reponse.bodyBytes)) as Map<String, dynamic>;
    await _enregistrerSession(donnees);
    return donnees["agent"] as Map<String, dynamic>;
  }

  Future<void> deconnexion() async {
    _acces = null;
    _rafraichissement = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove("acces");
    await prefs.remove("rafraichissement");
  }

  Future<bool> _rafraichir() async {
    if (_rafraichissement == null) return false;
    final reponse = await http.post(
      Uri.parse("$baseUrl/auth/rafraichir/"),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({"refresh": _rafraichissement}),
    );
    if (reponse.statusCode != 200) return false;
    await _enregistrerSession(jsonDecode(reponse.body) as Map<String, dynamic>);
    return true;
  }

  Future<dynamic> _lire(String chemin, {bool reessai = true}) async {
    final reponse = await http.get(Uri.parse("$baseUrl$chemin"), headers: _entetes);
    if (reponse.statusCode == 401 && reessai && await _rafraichir()) {
      return _lire(chemin, reessai: false);
    }
    if (reponse.statusCode >= 400) {
      throw Exception("Erreur ${reponse.statusCode} sur $chemin");
    }
    return jsonDecode(utf8.decode(reponse.bodyBytes));
  }

  Future<dynamic> _ecrire(String chemin, Map<String, dynamic> corps, {bool reessai = true}) async {
    final reponse = await http.post(
      Uri.parse("$baseUrl$chemin"),
      headers: _entetes,
      body: jsonEncode(corps),
    );
    if (reponse.statusCode == 401 && reessai && await _rafraichir()) {
      return _ecrire(chemin, corps, reessai: false);
    }
    if (reponse.statusCode >= 400) {
      throw Exception(utf8.decode(reponse.bodyBytes));
    }
    return jsonDecode(utf8.decode(reponse.bodyBytes));
  }

  Future<Map<String, dynamic>> profil() async => await _lire("/moi/") as Map<String, dynamic>;

  Future<Map<String, dynamic>> solde() async => await _lire("/moi/solde/") as Map<String, dynamic>;

  Future<List<dynamic>> mesDemandes() async {
    final donnees = await _lire("/demandes/");
    return donnees is Map ? donnees["results"] as List<dynamic> : donnees as List<dynamic>;
  }

  Future<List<dynamic>> aValider() async => await _lire("/demandes/a-valider/") as List<dynamic>;

  Future<List<dynamic>> notifications() async {
    final donnees = await _lire("/notifications/");
    return donnees is Map ? donnees["results"] as List<dynamic> : donnees as List<dynamic>;
  }

  Future<Map<String, dynamic>> creerDemande(Map<String, dynamic> donnees) async =>
      await _ecrire("/demandes/", donnees) as Map<String, dynamic>;

  Future<Map<String, dynamic>> soumettre(int id) async =>
      await _ecrire("/demandes/$id/soumettre/", {}) as Map<String, dynamic>;

  /// Avis favorable ou rejet. Le code de signature, s'il est fourni, appose la
  /// signature electronique du valideur sur l'acte.
  Future<Map<String, dynamic>> decider(
    int id,
    bool favorable,
    String commentaire, {
    String? codeSignature,
  }) async =>
      await _ecrire("/demandes/$id/decision/", {
        "favorable": favorable,
        "commentaire": commentaire,
        if (codeSignature != null && codeSignature.isNotEmpty) "code_signature": codeSignature,
      }) as Map<String, dynamic>;

  /// Depot des pieces jointes (TDR, lettre d'invitation, justificatif) depuis le terrain.
  Future<Map<String, dynamic>> deposerPieces(int id, Map<String, String> fichiers) async {
    final requete = http.MultipartRequest("POST", Uri.parse("$baseUrl/demandes/$id/pieces/"));
    if (_acces != null) {
      requete.headers["Authorization"] = "Bearer $_acces";
    }
    for (final entree in fichiers.entries) {
      requete.files.add(await http.MultipartFile.fromPath(entree.key, entree.value));
    }
    final reponse = await http.Response.fromStream(await requete.send());
    if (reponse.statusCode >= 400) {
      throw Exception(utf8.decode(reponse.bodyBytes));
    }
    return jsonDecode(utf8.decode(reponse.bodyBytes)) as Map<String, dynamic>;
  }

  /// Verification publique d'un acte signe (aucune authentification requise).
  Future<Map<String, dynamic>> verifier(String code) async {
    final reponse = await http.get(Uri.parse("$baseUrl/verification/$code/"));
    if (reponse.statusCode == 404) {
      throw Exception("Code de verification inconnu.");
    }
    return jsonDecode(utf8.decode(reponse.bodyBytes)) as Map<String, dynamic>;
  }
}
