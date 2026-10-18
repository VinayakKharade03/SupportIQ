import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const String _envBaseUrl = String.fromEnvironment('API_BASE_URL');

String get apiBaseUrl {
  if (_envBaseUrl.isNotEmpty) return _envBaseUrl;
  if (!kIsWeb && Platform.isAndroid) return 'http://10.0.2.2:8000';
  return 'http://localhost:8000';
}

class ApiException implements Exception {
  final int statusCode;
  final String message;
  ApiException(this.statusCode, this.message);

  @override
  String toString() => message;
}

class ApiClient {
  static const _accessKey = 'access_token';
  static const _refreshKey = 'refresh_token';

  final http.Client _http = http.Client();
  Completer<bool>? _refreshing;

  // ---- token storage ----

  Future<String?> get accessToken async =>
      (await SharedPreferences.getInstance()).getString(_accessKey);

  Future<String?> get refreshToken async =>
      (await SharedPreferences.getInstance()).getString(_refreshKey);

  Future<void> _saveTokens(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, data['access_token'] as String);
    await prefs.setString(_refreshKey, data['refresh_token'] as String);
  }

  Future<void> clearTokens() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }

  Future<bool> get hasSession async => (await refreshToken) != null;

  // ---- helpers ----

  Uri _uri(String path) => Uri.parse('$apiBaseUrl$path');

  String _errorMessage(http.Response res) {
    try {
      final body = jsonDecode(res.body);
      if (body is Map && body['detail'] is String) {
        return body['detail'] as String;
      }
    } catch (_) {}
    return 'Request failed (${res.statusCode})';
  }

  // ---- auth ----

  Future<void> login(String email, String password) async {
    final res = await _http
        .post(
          _uri('/auth/login'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'email': email, 'password': password}),
        )
        .timeout(const Duration(seconds: 15));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, _errorMessage(res));
    }
    await _saveTokens(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<void> logout() async {
    final rt = await refreshToken;
    if (rt != null) {
      try {
        await _http
            .post(
              _uri('/auth/logout'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({'refresh_token': rt}),
            )
            .timeout(const Duration(seconds: 10));
      } catch (_) {
        // Offline or server down: still clear local tokens.
      }
    }
    await clearTokens();
  }

  /// Rotates the token pair. Only one refresh runs at a time; callers that
  /// arrive during a refresh wait for the same result.
  Future<bool> _refresh() {
    final running = _refreshing;
    if (running != null) return running.future;

    final completer = Completer<bool>();
    _refreshing = completer;
    () async {
      try {
        final rt = await refreshToken;
        if (rt == null) {
          completer.complete(false);
          return;
        }
        final res = await _http
            .post(
              _uri('/auth/refresh'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({'refresh_token': rt}),
            )
            .timeout(const Duration(seconds: 15));
        if (res.statusCode == 200) {
          await _saveTokens(jsonDecode(res.body) as Map<String, dynamic>);
          completer.complete(true);
        } else {
          // Rejected: the session is over.
          await clearTokens();
          completer.complete(false);
        }
      } catch (_) {
        // Network problem: keep tokens so a later retry can still work.
        completer.complete(false);
      } finally {
        _refreshing = null;
      }
    }();
    return completer.future;
  }

  // ---- authenticated requests ----

  /// Sends a request with the Bearer token. On a 401, refreshes once and
  /// retries once. Throws ApiException when the response is not 2xx.
  Future<http.Response> send(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    Future<http.Response> attempt() async {
      final token = await accessToken;
      final headers = <String, String>{
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };
      final request = http.Request(method, _uri(path))..headers.addAll(headers);
      if (body != null) request.body = jsonEncode(body);
      final streamed =
          await _http.send(request).timeout(const Duration(seconds: 20));
      return http.Response.fromStream(streamed);
    }

    var res = await attempt();
    if (res.statusCode == 401 && await _refresh()) {
      res = await attempt();
    }
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw ApiException(res.statusCode, _errorMessage(res));
    }
    return res;
  }

  Map<String, dynamic> decode(http.Response res) =>
      jsonDecode(res.body) as Map<String, dynamic>;

  Future<Map<String, dynamic>> me() async {
    final res = await send('GET', '/auth/me');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
