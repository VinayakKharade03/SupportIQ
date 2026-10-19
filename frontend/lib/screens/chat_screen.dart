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
import '../api/chat_stream.dart';
import '../api/voice_reply.dart';
import '../state/cart_provider.dart';

class _Msg {
  String text;
  final bool fromUser;
  bool isError = false;
  bool flagged = false;
  int? ticketId;
  _Msg(this.text, {required this.fromUser});
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _rec = AudioRecorder();
  final _player = AudioPlayer();
  final _audioQueue = <Uint8List>[];
  bool _draining = false;

  final List<_Msg> _messages = [
    _Msg(
        'Hi! Ask me about your products, Bluetooth or charging issues, '
        'warranty, or tell me what you would like to order. '
        'You can also tap the mic and speak.',
        fromUser: false),
  ];
  bool _sending = false;
  bool _recording = false;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    _audioQueue.clear();
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

  String _errText(Object e) => e is ApiException
      ? e.message
      : 'Connection lost. Is the backend running?';

  // ---------- spoken audio queue ----------

  void _enqueueAudio(Uint8List wav) {
    _audioQueue.add(wav);
    _drain();
  }

  Future<void> _drain() async {
    if (_draining) return;
    _draining = true;
    while (_audioQueue.isNotEmpty && mounted) {
      final bytes = _audioQueue.removeAt(0);
      try {
        final done = _player.onPlayerComplete.first;
        await _player.play(BytesSource(bytes, mimeType: 'audio/wav'));
        await done.timeout(const Duration(seconds: 30));
      } catch (_) {
        // Skip a chunk that fails to play; keep the rest going.
      }
    }
    _draining = false;
  }

  // ---------- text chat ----------

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _sending || _recording) return;
    final api = context.read<ApiClient>();
    final cart = context.read<CartProvider>();
    _input.clear();
    final bot = _Msg('', fromUser: false);
    setState(() {
      _messages.add(_Msg(text, fromUser: true));
      _messages.add(bot);
      _sending = true;
    });
    _scrollToEnd();

    try {
      await for (final ev in chatStream(api, text)) {
        if (!mounted) return;
        if (ev['token'] is String) {
          setState(() => bot.text += ev['token'] as String);
          _scrollToEnd();
        } else if (ev['escalate'] == true) {
          setState(() {
            bot.flagged = true;
            bot.ticketId = (ev['ticket_id'] as num?)?.toInt();
          });
        }
      }
    } catch (e) {
      if (!mounted) return;
      final msg = _errText(e);
      setState(() {
        if (bot.text.isEmpty) {
          bot.text = msg;
          bot.isError = true;
        } else {
          bot.text += '\n\n[$msg]';
        }
      });
    }
    if (!mounted) return;
    setState(() => _sending = false);
    _scrollToEnd();
    cart.load();
  }

  // ---------- voice ----------

  Future<void> _toggleMic() async {
    if (_sending) return;
    if (_recording) {
      await _stopAndSend();
    } else {
      await _startRecording();
    }
  }

  Future<void> _startRecording() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      if (!await _rec.hasPermission()) {
        messenger.showSnackBar(const SnackBar(
            content: Text('Microphone permission was denied.')));
        return;
      }
      // Stop any reply that is still being spoken.
      _audioQueue.clear();
      await _player.stop();

      const cfg = RecordConfig(
          encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1);
      var path = '';
      if (!kIsWeb) {
        final dir = await getTemporaryDirectory();
        path =
            '${dir.path}/voice_${DateTime.now().millisecondsSinceEpoch}.wav';
      }
      await _rec.start(cfg, path: path);
      if (!mounted) return;
      setState(() => _recording = true);
    } catch (e) {
      messenger.showSnackBar(
          SnackBar(content: Text('Could not start recording: $e')));
    }
  }

  Future<void> _stopAndSend() async {
    final api = context.read<ApiClient>();
    final cart = context.read<CartProvider>();
    final user = _Msg('...', fromUser: true);
    final bot = _Msg('', fromUser: false);

    Uint8List wav;
    try {
      final out = await _rec.stop();
      if (!mounted) return;
      setState(() => _recording = false);
      if (out == null) throw Exception('No recording returned');
      wav = kIsWeb
          ? (await http.get(Uri.parse(out))).bodyBytes
          : await File(out).readAsBytes();
    } catch (e) {
      if (!mounted) return;
      setState(() => _recording = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Recording failed: $e')));
      return;
    }

    setState(() {
      _messages.add(user);
      _messages.add(bot);
      _sending = true;
    });
    _scrollToEnd();

    try {
      await for (final ev in voiceReply(api, wav)) {
        if (!mounted) return;
        if (ev['transcript'] is String) {
          final t = (ev['transcript'] as String).trim();
          setState(() => user.text = t.isEmpty ? '(nothing heard)' : t);
        } else if (ev['text'] is String) {
          setState(() {
            bot.text = bot.text.isEmpty
                ? ev['text'] as String
                : '${bot.text} ${ev['text']}';
          });
          if (ev['audio'] is String) {
            _enqueueAudio(base64Decode(ev['audio'] as String));
          }
          _scrollToEnd();
        } else if (ev['escalate'] == true) {
          setState(() {
            bot.flagged = true;
            bot.ticketId = (ev['ticket_id'] as num?)?.toInt();
          });
        }
      }
    } catch (e) {
      if (!mounted) return;
      final msg = _errText(e);
      setState(() {
        if (user.text == '...') user.text = '(voice message)';
        if (bot.text.isEmpty) {
          bot.text = msg;
          bot.isError = true;
        } else {
          bot.text += '\n\n[$msg]';
        }
      });
    }
    if (!mounted) return;
    setState(() => _sending = false);
    _scrollToEnd();
    cart.load();
  }

  // ---------- UI ----------

  Widget _bubble(_Msg m, bool waiting) {
    final scheme = Theme.of(context).colorScheme;
    final bg = m.isError
        ? scheme.errorContainer
        : (m.fromUser ? scheme.primary : scheme.surfaceContainerHighest);
    final fg = m.isError
        ? scheme.onErrorContainer
        : (m.fromUser ? scheme.onPrimary : scheme.onSurface);
    return Align(
      alignment: m.fromUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 560),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (waiting && m.text.isEmpty)
              const SizedBox(
                height: 18,
                width: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              SelectableText(m.text, style: TextStyle(color: fg)),
            if (m.flagged) ...[
              const SizedBox(height: 6),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.flag, size: 14, color: scheme.error),
                  const SizedBox(width: 4),
                  Text(
                    m.ticketId != null
                        ? 'Flagged for priority review (ticket #${m.ticketId})'
                        : 'Flagged for priority review',
                    style: TextStyle(fontSize: 12, color: scheme.error),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Support chat')),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (context, i) => _bubble(
                  _messages[i], _sending && i == _messages.length - 1),
            ),
          ),
          if (_recording)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text('Listening... tap the mic again to send',
                  style: TextStyle(color: scheme.error)),
            ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _input,
                      enabled: !_recording,
                      minLines: 1,
                      maxLines: 4,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: const InputDecoration(
                        hintText: 'Type a message',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    tooltip: _recording ? 'Stop and send' : 'Speak',
                    style: _recording
                        ? IconButton.styleFrom(backgroundColor: scheme.error)
                        : null,
                    onPressed: _sending ? null : _toggleMic,
                    icon: Icon(_recording ? Icons.stop : Icons.mic),
                  ),
                  const SizedBox(width: 4),
                  IconButton.filled(
                    tooltip: 'Send',
                    onPressed: (_sending || _recording) ? null : _send,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
