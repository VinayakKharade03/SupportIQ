import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../state/cart_provider.dart';

class _Msg {
  final String text;
  final bool fromUser;
  final bool isError;
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
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _sending) return;
    final api = context.read<ApiClient>();
    final cart = context.read<CartProvider>();
    _input.clear();
    setState(() {
      _messages.add(_Msg(text, fromUser: true));
      _sending = true;
    });
    _scrollToEnd();

    try {
      final res = await api.send('POST', '/support/chat', body: {'message': text});
      final reply = api.decode(res)['reply'] as String? ?? '';
      if (!mounted) return;
      setState(() => _messages.add(_Msg(reply, fromUser: false)));
      cart.load(); // chat orders can change the cart
    } catch (e) {
      if (!mounted) return;
      final msg = e is ApiException
          ? e.message
          : 'Cannot reach the server. Is the backend running?';
      setState(() => _messages.add(_Msg(msg, fromUser: false, isError: true)));
    }
    if (!mounted) return;
    setState(() => _sending = false);
    _scrollToEnd();
  }

  Widget _bubble(_Msg m) {
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
        child: SelectableText(m.text, style: TextStyle(color: fg)),
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
              itemCount: _messages.length + (_sending ? 1 : 0),
              itemBuilder: (context, i) {
                if (i == _messages.length) {
                  return const Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: EdgeInsets.all(12),
                      child: SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  );
                }
                return _bubble(_messages[i]);
              },
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
