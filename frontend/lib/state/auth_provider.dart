import 'package:flutter/foundation.dart';

import '../api/api_client.dart';

enum AuthStatus { unknown, loggedOut, loggedIn }

class AuthProvider extends ChangeNotifier {
  final ApiClient api;

  AuthProvider(this.api);

  AuthStatus _status = AuthStatus.unknown;
  Map<String, dynamic>? _user;
  String? _error;
  bool _busy = false;

  AuthStatus get status => _status;
  Map<String, dynamic>? get user => _user;
  String? get error => _error;
  bool get busy => _busy;
  bool get isAdmin => _user?['is_admin'] == true;

  /// Called once at startup. If a refresh token is stored, try /auth/me
  /// (the client refreshes the access token itself if it has expired).
  Future<void> restoreSession() async {
    if (!await api.hasSession) {
      _status = AuthStatus.loggedOut;
      notifyListeners();
      return;
    }
    try {
      _user = await api.me();
      _status = AuthStatus.loggedIn;
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        // Session is over (expired or revoked).
        await api.clearTokens();
        _status = AuthStatus.loggedOut;
      } else {
        // Server error: keep the tokens, show logged out for now.
        _status = AuthStatus.loggedOut;
      }
    } catch (_) {
      // Backend unreachable: keep the tokens so a later start can restore.
      _status = AuthStatus.loggedOut;
    }
    notifyListeners();
  }

  Future<bool> login(String email, String password) async {
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      await api.login(email, password);
      _user = await api.me();
      _status = AuthStatus.loggedIn;
      _busy = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Cannot reach the server. Is the backend running?';
    }
    _busy = false;
    notifyListeners();
    return false;
  }

  Future<void> logout() async {
    await api.logout();
    _user = null;
    _error = null;
    _status = AuthStatus.loggedOut;
    notifyListeners();
  }
}
