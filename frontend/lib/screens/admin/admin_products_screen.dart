import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import 'admin_product_form_screen.dart';

class AdminProductsScreen extends StatefulWidget {
  const AdminProductsScreen({super.key});

  @override
  State<AdminProductsScreen> createState() => _AdminProductsScreenState();
}

class _AdminProductsScreenState extends State<AdminProductsScreen> {
  final _search = TextEditingController();
  List<Map<String, dynamic>> _products = [];
  bool _loading = true;
  bool _busy = false;
  String? _error;
  String _show = 'all'; // all | active | archived

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
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
      final q = _search.text.trim();
      final qs = StringBuffer('?limit=100');
      if (q.isNotEmpty) qs.write('&search=${Uri.encodeQueryComponent(q)}');
      if (_show == 'active') qs.write('&is_active=true');
      if (_show == 'archived') qs.write('&is_active=false');
      final res = await context
          .read<ApiClient>()
          .send('GET', '/admin/products$qs');
      setState(() {
        _products =
            (jsonDecode(res.body) as List).cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = _msg(e);
        _loading = false;
      });
    }
  }

  Future<void> _openForm([Map<String, dynamic>? p]) async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => AdminProductFormScreen(product: p)),
    );
    if (saved == true) _load();
  }

  Future<void> _toggle(Map<String, dynamic> p) async {
    final messenger = ScaffoldMessenger.of(context);
    final api = context.read<ApiClient>();
    final archive = p['is_active'] == true;
    final go = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(archive ? 'Archive ${p['name']}?' : 'Restore ${p['name']}?'),
        content: Text(archive
            ? 'It disappears from the shop and the chatbot. Order history is kept.'
            : 'It appears in the shop and the chatbot again.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(archive ? 'Archive' : 'Restore')),
        ],
      ),
    );
    if (go != true) return;
    setState(() => _busy = true);
    try {
      if (archive) {
        await api.send('DELETE', '/admin/products/${p['id']}');
      } else {
        await api.send('POST', '/admin/products/${p['id']}/restore');
      }
      if (!mounted) return;
      messenger.showSnackBar(
          SnackBar(content: Text(archive ? 'Archived' : 'Restored')));
      await _load();
    } catch (e) {
      if (mounted) messenger.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    const filters = {'all': 'All', 'active': 'Active', 'archived': 'Archived'};
    return Scaffold(
      appBar: AppBar(title: const Text('Products'), actions: [
        IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _load),
      ]),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _busy ? null : () => _openForm(),
        icon: const Icon(Icons.add),
        label: const Text('New product'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _load(),
              decoration: InputDecoration(
                hintText: 'Search name or category',
                border: const OutlineInputBorder(),
                isDense: true,
                suffixIcon: IconButton(
                    icon: const Icon(Icons.search), onPressed: _load),
              ),
            ),
          ),
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
                      selected: _show == e.key,
                      onSelected: (_) {
                        setState(() => _show = e.key);
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
                    : _products.isEmpty
                        ? const Center(child: Text('No products'))
                        : ListView.builder(
                            padding:
                                const EdgeInsets.fromLTRB(12, 0, 12, 88),
                            itemCount: _products.length,
                            itemBuilder: (context, i) {
                              final p = _products[i];
                              final active = p['is_active'] == true;
                              final stock = (p['stock'] as num).toInt();
                              return Card(
                                child: ListTile(
                                  onTap: _busy ? null : () => _openForm(p),
                                  title: Text(
                                    '${p['name']}',
                                    style: active
                                        ? null
                                        : const TextStyle(
                                            color: Colors.grey,
                                            decoration:
                                                TextDecoration.lineThrough),
                                  ),
                                  subtitle: Text(
                                      '#${p['id']} | ${p['category']} | Rs ${(p['price'] as num).toStringAsFixed(0)} | stock $stock${active ? '' : ' | archived'}',
                                      style: TextStyle(
                                          color: (active && stock <= 10)
                                              ? Colors.red.shade700
                                              : null)),
                                  trailing: IconButton(
                                    tooltip: active ? 'Archive' : 'Restore',
                                    icon: Icon(active
                                        ? Icons.archive_outlined
                                        : Icons.unarchive_outlined),
                                    onPressed: _busy ? null : () => _toggle(p),
                                  ),
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
