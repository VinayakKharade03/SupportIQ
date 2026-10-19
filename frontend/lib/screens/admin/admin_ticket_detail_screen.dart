import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../orders_screen.dart' show formatDate;
import 'admin_tickets_screen.dart' show ticketColor;

class AdminTicketDetailScreen extends StatefulWidget {
  final int ticketId;
  const AdminTicketDetailScreen({super.key, required this.ticketId});

  @override
  State<AdminTicketDetailScreen> createState() =>
      _AdminTicketDetailScreenState();
}

class _AdminTicketDetailScreenState extends State<AdminTicketDetailScreen> {
  Map<String, dynamic>? _t;
  bool _loading = true;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _msg(Object e) => e is ApiException
      ? e.message
      : 'Cannot reach the server. Is the backend running?';

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await context
          .read<ApiClient>()
          .send('GET', '/admin/tickets/${widget.ticketId}');
      setState(() {
        _t = jsonDecode(res.body) as Map<String, dynamic>;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = _msg(e);
        _loading = false;
      });
    }
  }

  Future<void> _setStatus(String status) async {
    final messenger = ScaffoldMessenger.of(context);
    final api = context.read<ApiClient>();
    setState(() => _busy = true);
    try {
      final res = await api.send('PATCH', '/admin/tickets/${widget.ticketId}',
          body: {'status': status});
      if (!mounted) return;
      final updated = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _t = {...?_t, 'status': updated['status']};
        _busy = false;
      });
      messenger.showSnackBar(SnackBar(content: Text('Marked $status')));
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Ticket #${widget.ticketId}')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error!),
                      const SizedBox(height: 12),
                      OutlinedButton(
                          onPressed: _load, child: const Text('Retry')),
                    ],
                  ),
                )
              : _content(context),
    );
  }

  Widget _content(BuildContext context) {
    final t = _t!;
    final status = '${t['status']}';
    final who = t['user_email'] == null
        ? 'Anonymous'
        : '${t['user_name'] ?? ''} ${t['user_email']}'.trim();
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: ticketColor(status),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(status),
            ),
            const SizedBox(height: 16),
            SelectableText('${t['message']}',
                style: Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height: 16),
            Text('From: $who'),
            Text('Category: ${t['category']}'),
            Text('Sentiment: ${t['sentiment']}'),
            Text('Source: ${t['source']}'),
            Text('Created: ${formatDate(t['created_at'] as String?)}'),
            const SizedBox(height: 24),
            Wrap(
              spacing: 8,
              children: [
                for (final s in const ['open', 'in_progress', 'resolved'])
                  FilledButton.tonal(
                    onPressed: (_busy || s == status) ? null : () => _setStatus(s),
                    child: Text(s),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
