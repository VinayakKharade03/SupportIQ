import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import 'orders_screen.dart' show statusColor, formatDate;

class OrderDetailScreen extends StatefulWidget {
  final int orderId;
  const OrderDetailScreen({super.key, required this.orderId});

  @override
  State<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends State<OrderDetailScreen> {
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
      final api = context.read<ApiClient>();
      final res = await api.send('GET', '/orders/${widget.orderId}');
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

  Future<void> _cancel() async {
    final messenger = ScaffoldMessenger.of(context);
    final api = context.read<ApiClient>();
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
    setState(() => _busy = true);
    try {
      final res = await api.send('POST', '/orders/${widget.orderId}/cancel');
      if (!mounted) return;
      setState(() {
        _o = jsonDecode(res.body) as Map<String, dynamic>;
        _busy = false;
      });
      messenger.showSnackBar(const SnackBar(content: Text('Order cancelled')));
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
    final items = ((o['items'] as List?) ?? const []).cast<Map<String, dynamic>>();
    final theme = Theme.of(context);
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
            const SizedBox(height: 16),
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
            if (status == 'confirmed') ...[
              const SizedBox(height: 24),
              OutlinedButton(
                onPressed: _busy ? null : _cancel,
                child: _busy
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Cancel order'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
