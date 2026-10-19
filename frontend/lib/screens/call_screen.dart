import 'dart:async';
import 'dart:convert';
import 'dart:io' show File;
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../api/api_client.dart';
import '../api/voice_reply.dart';
import '../state/cart_provider.dart';

enum _Phase { starting, listening, thinking, speaking, error }

class CallScreen extends StatefulWidget {
  const CallScreen({super.key});

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> {
  final _rec = AudioRecorder();
  final _player = AudioPlayer();
  _Phase _phase = _Phase.starting;
  bool _active = true;
  String _error = '';
  final List<String> _lines = [];
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _run());
  }

  @override
  void dispose() {
    _active = false;
    _scroll.dispose();
    _player.dispose();
    _rec.dispose();
    super.dispose();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.jumpTo(_scroll.position.maxScrollExtent);
      }
    });
  }

  void _fail(String msg) {
    if (!mounted) return;
    setState(() {
      _phase = _Phase.error;
      _error = msg;
    });
  }

  Future<void> _end() async {
    _active = false;
    try {
      await _player.stop();
    } catch (_) {}
    try {
      await _rec.stop();
    } catch (_) {}
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _run() async {
    try {
      if (!await _rec.hasPermission()) {
        _fail('Microphone permission was denied.');
        return;
      }
      while (_active && mounted) {
        final wav = await _listenTurn();
        if (!_active || !mounted) break;
        if (wav == null) continue;
        await _respond(wav);
      }
    } catch (e) {
      if (_active) _fail('$e');
    }
  }

  /// Records until the caller stops talking. Returns null if nothing was said.
  Future<Uint8List?> _listenTurn() async {
    if (!mounted) return null;
    setState(() => _phase = _Phase.listening);

    const cfg = RecordConfig(
        encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1);
    var path = '';
    if (!kIsWeb) {
      final dir = await getTemporaryDirectory();
      path = '${dir.path}/call_${DateTime.now().millisecondsSinceEpoch}.wav';
    }
    await _rec.start(cfg, path: path);

    final started = DateTime.now();
    final calib = <double>[];
    var calibrated = false;
    var threshold = -30.0;
    var heard = false;
    var speechStart = started;
    var lastLoud = started;

    while (_active && mounted) {
      await Future.delayed(const Duration(milliseconds: 100));
      final level = (await _rec.getAmplitude()).current;
      final now = DateTime.now();
      final since = now.difference(started);

      // Skip the start-up blip, then measure the room floor.
      if (since < const Duration(milliseconds: 300)) continue;
      if (since < const Duration(milliseconds: 900)) {
        if (level > -150) calib.add(level);
        continue;
      }
      if (!calibrated) {
        calibrated = true;
        if (calib.isNotEmpty) {
          calib.sort();
          final floor = calib[calib.length ~/ 4]; // lower quartile
          threshold = (floor + 10).clamp(-50.0, -12.0).toDouble();
        }
      }
      if (level > threshold) {
        if (!heard) {
          heard = true;
          speechStart = now;
        }
        lastLoud = now;
      }
      if (heard &&
          now.difference(lastLoud) > const Duration(milliseconds: 1000)) {
        break;
      }
      if (!heard && since > const Duration(seconds: 20)) break;
      if (since > const Duration(seconds: 30)) break;
    }

    final out = await _rec.stop();
    if (!_active || !mounted) return null;
    if (!heard || out == null) return null;
    if (lastLoud.difference(speechStart) < const Duration(milliseconds: 300)) {
      return null; // a click or cough, not speech
    }
    return kIsWeb
        ? (await http.get(Uri.parse(out))).bodyBytes
        : await File(out).readAsBytes();
  }

  Future<void> _play(Uint8List bytes) async {
    if (!_active) return;
    try {
      final done = _player.onPlayerComplete.first;
      await _player.play(BytesSource(bytes, mimeType: 'audio/wav'));
      await done.timeout(const Duration(seconds: 30));
    } catch (_) {}
  }

  Future<void> _respond(Uint8List wav) async {
    final api = context.read<ApiClient>();
    final cart = context.read<CartProvider>();
    setState(() => _phase = _Phase.thinking);

    Future<void> chain = Future.value();
    int? agentIdx;
    try {
      await for (final ev in voiceReply(api, wav)) {
        if (!_active || !mounted) return;
        if (ev['transcript'] is String) {
          final t = (ev['transcript'] as String).trim();
          if (t.isNotEmpty) setState(() => _lines.add('You: $t'));
        } else if (ev['text'] is String) {
          final s = ev['text'] as String;
          setState(() {
            if (agentIdx == null) {
              _lines.add('Agent: $s');
              agentIdx = _lines.length - 1;
            } else {
              _lines[agentIdx!] = '${_lines[agentIdx!]} $s';
            }
          });
          if (ev['audio'] is String) {
            final bytes = base64Decode(ev['audio'] as String);
            chain = chain.then((_) => _play(bytes));
            if (_phase != _Phase.speaking) {
              setState(() => _phase = _Phase.speaking);
            }
          }
        }
        _scrollToEnd();
      }
      setState(() => _phase = _Phase.speaking);
      await chain;
      cart.load(); // voice orders can change the cart
    } catch (e) {
      if (!mounted || !_active) return;
      final msg = e is ApiException ? e.message : 'Connection lost.';
      setState(() => _lines.add('[$msg]'));
      await Future.delayed(const Duration(seconds: 1));
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    late final IconData icon;
    late final Color color;
    late final String label;
    switch (_phase) {
      case _Phase.starting:
        icon = Icons.phone_in_talk;
        color = scheme.outline;
        label = 'Connecting...';
      case _Phase.listening:
        icon = Icons.mic;
        color = Colors.green;
        label = 'Listening...';
      case _Phase.thinking:
        icon = Icons.hourglass_top;
        color = Colors.orange;
        label = 'Thinking...';
      case _Phase.speaking:
        icon = Icons.volume_up;
        color = scheme.primary;
        label = 'Speaking...';
      case _Phase.error:
        icon = Icons.error_outline;
        color = scheme.error;
        label = _error;
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice call'),
        automaticallyImplyLeading: false,
      ),
      body: Column(
        children: [
          const SizedBox(height: 24),
          CircleAvatar(
            radius: 44,
            backgroundColor: color.withValues(alpha: 0.15),
            child: Icon(icon, size: 44, color: color),
          ),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(label,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 600),
                child: ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.all(16),
                  itemCount: _lines.length,
                  itemBuilder: (_, i) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Text(_lines[i]),
                  ),
                ),
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: scheme.error),
                onPressed: _end,
                icon: const Icon(Icons.call_end),
                label: const Text('End call'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
