import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:record/record.dart';

import 'api/api_client.dart';

void main() => runApp(const MaterialApp(home: RecTest()));

class RecTest extends StatefulWidget {
  const RecTest({super.key});
  @override
  State<RecTest> createState() => _RecTestState();
}

class _RecTestState extends State<RecTest> {
  final _rec = AudioRecorder();
  String _log = 'Press the button, speak for 3 seconds.';
  bool _busy = false;

  Future<void> _run() async {
    setState(() {
      _busy = true;
      _log = 'Checking mic permission...';
    });
    try {
      if (!await _rec.hasPermission()) {
        setState(() => _log = 'Mic permission denied.');
        return;
      }
      const cfg = RecordConfig(
          encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1);
      setState(() => _log = 'Recording 3 seconds... speak now');
      await _rec.start(cfg, path: '');
      await Future.delayed(const Duration(seconds: 3));
      final blobUrl = await _rec.stop();
      if (blobUrl == null) throw Exception('No recording returned');
      final blobRes = await http.get(Uri.parse(blobUrl));
      final wav = blobRes.bodyBytes;
      final head = wav.length >= 4 ? String.fromCharCodes(wav.sublist(0, 4)) : '?';
      setState(() => _log = 'Recorded ${wav.length} bytes, header "$head" (RIFF = real WAV).\nUploading...');      final req = http.MultipartRequest('POST', Uri.parse('$apiBaseUrl/voice/reply'))
        ..files.add(http.MultipartFile.fromBytes('file', wav, filename: 'a.wav'));
      final res = await req.send().timeout(const Duration(seconds: 60));
      final body = await res.stream.bytesToString();
      final tr = RegExp(r'"transcript": "(.*?)"').firstMatch(body)?.group(1);
      setState(() => _log = 'HTTP ${res.statusCode}\nTranscript: "${tr ?? '(none)'}"');
    } catch (e) {
      setState(() => _log = 'Error: $e');
    } finally {
      setState(() => _busy = false);
    }
  }

  List<int> _wav(List<int> pcm, int rate) {
    final h = BytesBuilder();
    void s(String t) => h.add(t.codeUnits);
    void i32(int v) => h.add([v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255]);
    void i16(int v) => h.add([v & 255, (v >> 8) & 255]);
    s('RIFF'); i32(36 + pcm.length); s('WAVE'); s('fmt '); i32(16);
    i16(1); i16(1); i32(rate); i32(rate * 2); i16(2); i16(16);
    s('data'); i32(pcm.length); h.add(pcm);
    return h.toBytes();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Recording test')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(_log, textAlign: TextAlign.center),
              const SizedBox(height: 24),
              FilledButton(
                  onPressed: _busy ? null : _run,
                  child: const Text('Record 3 s and upload')),
            ]),
          ),
        ),
      );
}
