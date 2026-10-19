import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_client.dart';
import 'stream_client_stub.dart'
    if (dart.library.js_interop) 'stream_client_web.dart';

/// Uploads a WAV recording to POST /voice/reply and streams its events:
/// {transcript}, {text, audio(base64 WAV)}, {escalate, ticket_id}, {done}.
Stream<Map<String, dynamic>> voiceReply(ApiClient api, List<int> wav) async* {
  try {
    await api.me(); // refreshes an expired access token
  } catch (_) {}

  final client = createStreamClient();
  try {
    final token = await api.accessToken;
    final req =
        http.MultipartRequest('POST', Uri.parse('$apiBaseUrl/voice/reply'))
          ..files.add(http.MultipartFile.fromBytes('file', wav,
              filename: 'voice.wav'));
    if (token != null) req.headers['Authorization'] = 'Bearer $token';

    final res = await client.send(req).timeout(const Duration(seconds: 120));
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
