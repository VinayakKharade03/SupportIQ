import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../orders_screen.dart' show statusColor, formatDate;
import 'admin_order_detail_screen.dart';

class AdminOrdersScreen extends StatefulWidget {
  const AdminOrdersScreen({super.key});

  @override
  State<AdminOrdersScreen> createState() => _AdminOrdersScreenState();
}

class _AdminOrdersScreenState extends State<AdminOrdersScreen> {
  List<Map<String, dynamic>> _orders = [];
  bool _loading = true;
  String? _error;
  String? _status; // null = all placed orders

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
      final q = _status == null ? '' : '&status=$_status';
      final res = await context
          .read<ApiClient>()
          .send('GET', '/admin/orders?limit=100$q');
      setState(() {
        _orders = (jsonDecode(res.body) as List).cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e is ApiException
            ? e.message
            : 'Cannot reach the server. Is the backend running?';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    const filters = <String?, String>{
      null: 'All',
      'confirmed': 'Confirmed',
      'shipped': 'Shipped',
      'delivered': 'Delivered',
      'cancelled': 'Cancelled',
    };
    return Scaffold(
      appBar: AppBar(title: const Text('Orders'), actions: [
        IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _load),
      ]),
      body: Column(
        children: [
          SizedBox(
            height: 56,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: [
                for (final e in filters.entries)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(e.value),
                      selected: _status == e.key,
                      onSelected: (_) {
                        setState(() => _status = e.key);
                        _load();
                      },
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: _loading
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
                    : _orders.isEmpty
                        ? const Center(child: Text('No orders'))
                        : ListView.builder(
                            padding: const EdgeInsets.all(12),
                            itemCount: _orders.length,
                            itemBuilder: (context, i) {
                              final o = _orders[i];
                              final status = '${o['status']}';
                              return Card(
                                child: ListTile(
                                  title: Text('Order #${o['id']}'),
                                  subtitle: Padding(
                                    padding: const EdgeInsets.only(top: 4),
                                    child: Wrap(
                                      spacing: 8,
                                      runSpacing: 4,
                                      crossAxisAlignment:
                                          WrapCrossAlignment.center,
                                      children: [
                                        Text(
                                            '${o['user_email'] ?? 'unknown'} | ${formatDate(o['created_at'] as String?)} | ${o['units']} item(s)'),
                                        Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: statusColor(status),
                                            borderRadius:
                                                BorderRadius.circular(10),
                                          ),
                                          child: Text(status,
                                              style: const TextStyle(
                                                  fontSize: 12)),
                                        ),
                                      ],
                                    ),
                                  ),
                                  trailing: Text(
                                      'Rs ${(o['total'] as num).toStringAsFixed(0)}',
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleMedium),
                                  onTap: () async {
                                    await Navigator.of(context).push(
                                      MaterialPageRoute(
                                        builder: (_) => AdminOrderDetailScreen(
                                            orderId: (o['id'] as num).toInt()),
                                      ),
                                    );
                                    _load();
                                  },
                                ),
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}
