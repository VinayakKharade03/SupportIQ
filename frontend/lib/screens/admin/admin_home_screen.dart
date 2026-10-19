import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import 'admin_tickets_screen.dart';

class AdminHomeScreen extends StatefulWidget {
  const AdminHomeScreen({super.key});

  @override
  State<AdminHomeScreen> createState() => _AdminHomeScreenState();
}

class _AdminHomeScreenState extends State<AdminHomeScreen> {
  Map<String, dynamic>? _s;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await context.read<ApiClient>().send('GET', '/admin/stats');
      setState(() {
        _s = jsonDecode(res.body) as Map<String, dynamic>;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e is ApiException
            ? (e.statusCode == 403 ? 'Not authorised' : e.message)
            : 'Cannot reach the server. Is the backend running?';
        _loading = false;
      });
    }
  }

  Widget _tile(String label, String value) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(value, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 4),
              Text(label),
            ],
          ),
        ),
      );

  String _counts(Map<String, dynamic> m) =>
      m.entries.map((e) => '${e.key}: ${e.value}').join('   ');

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin'),
        actions: [
          IconButton(
              tooltip: 'Refresh',
              icon: const Icon(Icons.refresh),
              onPressed: _load),
        ],
      ),
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
    final s = _s!;
    final users = s['users'] as Map<String, dynamic>;
    final tickets = s['tickets'] as Map<String, dynamic>;
    final orders = s['orders'] as Map<String, dynamic>;
    final products = s['products'] as Map<String, dynamic>;
    final top = ((s['top_products'] as List?) ?? const [])
        .cast<Map<String, dynamic>>();
    final theme = Theme.of(context);
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _tile('Users (${users['admins']} admin)', '${users['total']}'),
                _tile('Orders', '${orders['total']}'),
                _tile('Revenue',
                    'Rs ${(orders['revenue'] as num).toStringAsFixed(0)}'),
                _tile('Units sold', '${orders['units_sold']}'),
                _tile('Tickets', '${tickets['total']}'),
                _tile('Active products', '${products['active']}'),
              ],
            ),
            const SizedBox(height: 16),
            Text('Orders by status', style: theme.textTheme.titleMedium),
            Text(_counts(orders['by_status'] as Map<String, dynamic>)),
            Text('Pending carts: ${orders['pending_carts']}'),
            const SizedBox(height: 12),
            Text('Tickets by status', style: theme.textTheme.titleMedium),
            Text(_counts(tickets['by_status'] as Map<String, dynamic>)),
            const SizedBox(height: 12),
            Text('Stock', style: theme.textTheme.titleMedium),
            Text(
                'Out of stock: ${products['out_of_stock']}   Low stock (<= ${products['low_stock_threshold']}): ${products['low_stock']}   Archived: ${products['archived']}'),
            if (top.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Top products', style: theme.textTheme.titleMedium),
              for (final t in top)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  title: Text('${t['name']}'),
                  trailing: Text(
                      '${t['units_sold']} sold  |  Rs ${(t['revenue'] as num).toStringAsFixed(0)}'),
                ),
            ],
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(
                    builder: (_) => const AdminTicketsScreen()),
              ),
              icon: const Icon(Icons.support_agent),
              label: const Text('Tickets'),
            ),
          ],
        ),
      ),
    );
  }
}
