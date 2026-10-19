import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_client.dart';
import 'stream_client_stub.dart'
    if (dart.library.js_interop) 'stream_client_web.dart';

/// Streams events from POST /support/chat/stream.
/// Events: {token: "..."}, {escalate: true, ticket_id: N}, {done: true}.
Stream<Map<String, dynamic>> chatStream(ApiClient api, String message) async* {
  // Refreshes an expired access token first (errors ignored: chat also
  // works logged out, just without order actions).
  try {
    await api.me();
  } catch (_) {}

  final client = createStreamClient();
  try {
    final token = await api.accessToken;
    final req =
        http.Request('POST', Uri.parse('$apiBaseUrl/support/chat/stream'))
          ..headers['Content-Type'] = 'application/json'
          ..body = jsonEncode({'message': message});
    if (token != null) req.headers['Authorization'] = 'Bearer $token';

    final res = await client.send(req).timeout(const Duration(seconds: 60));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, 'Request failed (${res.statusCode})');
    }

    await for (final line in res.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())) {
      if (!line.startsWith('data:')) continue;
      final payload = line.substring(5).trim();
      if (payload.isEmpty) continue;
      yield jsonDecode(payload) as Map<String, dynamic>;
    }
  } finally {
    client.close();
  }
}
