import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../orders_screen.dart' show statusColor, formatDate;

// current status -> statuses an admin may move it to (matches the backend)
const _transitions = <String, List<String>>{
  'confirmed': ['shipped', 'cancelled'],
  'shipped': ['delivered'],
};

class AdminOrderDetailScreen extends StatefulWidget {
  final int orderId;
  const AdminOrderDetailScreen({super.key, required this.orderId});

  @override
  State<AdminOrderDetailScreen> createState() =>
      _AdminOrderDetailScreenState();
}

class _AdminOrderDetailScreenState extends State<AdminOrderDetailScreen> {
  Map<String, dynamic>? _o;
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
          .send('GET', '/admin/orders/${widget.orderId}');
      setState(() {
        _o = jsonDecode(res.body) as Map<String, dynamic>;
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
    if (status == 'cancelled') {
      final go = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Cancel order #${widget.orderId}?'),
          content: const Text('The items go back into stock. This cannot be undone.'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Keep order')),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Cancel order')),
          ],
        ),
      );
      if (go != true) return;
    }
    setState(() => _busy = true);
    try {
      final res = await api.send('PATCH', '/admin/orders/${widget.orderId}/status',
          body: {'status': status});
      if (!mounted) return;
      setState(() {
        _o = jsonDecode(res.body) as Map<String, dynamic>;
        _busy = false;
      });
      messenger.showSnackBar(SnackBar(content: Text('Order marked $status')));
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
  }

  String _money(num v) => 'Rs ${v.toStringAsFixed(0)}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Order #${widget.orderId}')),
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
    final o = _o!;
    final status = '${o['status']}';
    final items =
        ((o['items'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final theme = Theme.of(context);
    final moves = _transitions[status] ?? const <String>[];
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor(status),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(status),
                ),
                const SizedBox(width: 12),
                Text(formatDate(o['created_at'] as String?)),
              ],
            ),
            const SizedBox(height: 12),
            Text('Customer: ${o['user_name'] ?? ''} ${o['user_email'] ?? ''}'.trim()),
            const SizedBox(height: 12),
            for (final it in items)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${it['name']}'),
                subtitle:
                    Text('${it['quantity']} x ${_money(it['unit_price'] as num)}'),
                trailing: Text(_money(it['line_total'] as num),
                    style: theme.textTheme.titleMedium),
              ),
            const Divider(),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Total', style: theme.textTheme.titleLarge),
                Text(_money(o['total'] as num), style: theme.textTheme.titleLarge),
              ],
            ),
            const SizedBox(height: 24),
            if (moves.isEmpty)
              const Text('This order is final and cannot be changed.')
            else
              Wrap(
                spacing: 8,
                children: [
                  for (final s in moves)
                    FilledButton.tonal(
                      onPressed: _busy ? null : () => _setStatus(s),
                      child: Text('Mark $s'),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
