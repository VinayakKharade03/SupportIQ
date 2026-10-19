import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../api/chat_stream.dart';
import '../state/cart_provider.dart';

class _Msg {
  String text;
  final bool fromUser;
  bool isError;
  bool flagged = false;
  int? ticketId;
  _Msg(this.text, {required this.fromUser, this.isError = false});
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_Msg> _messages = [
    _Msg(
        'Hi! Ask me about your products, Bluetooth or charging issues, '
        'warranty, or tell me what you would like to order.',
        fromUser: false),
  ];
  bool _sending = false;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.jumpTo(_scroll.position.maxScrollExtent);
      }
    });
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _sending) return;
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
      final msg = e is ApiException
          ? e.message
          : 'Connection lost. Is the backend running?';
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
    cart.load(); // chat orders can change the cart
  }

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
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _input,
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
                    tooltip: 'Send',
                    onPressed: _sending ? null : _send,
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
