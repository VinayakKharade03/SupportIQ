import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import 'order_detail_screen.dart';

Color statusColor(String s) {
  switch (s) {
    case 'confirmed':
      return Colors.blue.shade100;
    case 'shipped':
      return Colors.orange.shade100;
    case 'delivered':
      return Colors.green.shade100;
    case 'cancelled':
      return Colors.red.shade100;
    default:
      return Colors.grey.shade200;
  }
}

String formatDate(String? iso) {
  if (iso == null) return '';
  final d = DateTime.tryParse(iso)?.toLocal();
  if (d == null) return '';
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(d.day)}/${two(d.month)}/${d.year} ${two(d.hour)}:${two(d.minute)}';
}

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key});

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  List<Map<String, dynamic>> _orders = [];
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
      final api = context.read<ApiClient>();
      final res = await api.send('GET', '/orders?limit=100');
      final data = jsonDecode(res.body) as List<dynamic>;
      setState(() {
        _orders = data.cast<Map<String, dynamic>>();
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('My orders'),
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
              : _orders.isEmpty
                  ? const Center(child: Text('No orders yet'))
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
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
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  spacing: 8,
                                  runSpacing: 4,
                                  children: [
                                    Text(
                                        '${formatDate(o['created_at'] as String?)}  |  ${o['units']} item(s)'),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: statusColor(status),
                                        borderRadius:
                                            BorderRadius.circular(10),
                                      ),
                                      child: Text(status,
                                          style:
                                              const TextStyle(fontSize: 12)),
                                    ),
                                  ],
                                ),
                              ),
                              trailing: Text(
                                  'Rs ${(o['total'] as num).toStringAsFixed(0)}',
                                  style:
                                      Theme.of(context).textTheme.titleMedium),
                              onTap: () async {
                                await Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => OrderDetailScreen(
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
    );
  }
}
