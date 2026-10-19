import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';

class AdminProductFormScreen extends StatefulWidget {
  final Map<String, dynamic>? product; // null = create
  const AdminProductFormScreen({super.key, this.product});

  @override
  State<AdminProductFormScreen> createState() => _AdminProductFormScreenState();
}

class _AdminProductFormScreenState extends State<AdminProductFormScreen> {
  late final TextEditingController _name;
  late final TextEditingController _category;
  late final TextEditingController _description;
  late final TextEditingController _price;
  late final TextEditingController _stock;
  bool _busy = false;
  String? _error;

  bool get _editing => widget.product != null;

  @override
  void initState() {
    super.initState();
    final p = widget.product;
    _name = TextEditingController(text: p?['name'] as String? ?? '');
    _category = TextEditingController(text: p?['category'] as String? ?? '');
    _description =
        TextEditingController(text: p?['description'] as String? ?? '');
    _price = TextEditingController(
        text: p == null ? '' : (p['price'] as num).toString());
    _stock = TextEditingController(
        text: p == null ? '0' : (p['stock'] as num).toInt().toString());
  }

  @override
  void dispose() {
    _name.dispose();
    _category.dispose();
    _description.dispose();
    _price.dispose();
    _stock.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    final category = _category.text.trim();
    final description = _description.text.trim();
    final price = double.tryParse(_price.text.trim());
    final stock = int.tryParse(_stock.text.trim());

    if (name.isEmpty || category.isEmpty || description.isEmpty) {
      setState(() => _error = 'Name, category and description are required.');
      return;
    }
    if (price == null || price <= 0) {
      setState(() => _error = 'Price must be a number above 0.');
      return;
    }
    if (stock == null || stock < 0) {
      setState(() => _error = 'Stock must be a whole number, 0 or more.');
      return;
    }

    final api = context.read<ApiClient>();
    final nav = Navigator.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_editing) {
        final p = widget.product!;
        final changes = <String, dynamic>{};
        if (name != p['name']) changes['name'] = name;
        if (category.toLowerCase() != p['category']) changes['category'] = category;
        if (description != p['description']) changes['description'] = description;
        if (price != (p['price'] as num).toDouble()) changes['price'] = price;
        if (stock != (p['stock'] as num).toInt()) changes['stock'] = stock;
        if (changes.isEmpty) {
          nav.pop(false);
          return;
        }
        await api.send('PATCH', '/admin/products/${p['id']}', body: changes);
      } else {
        await api.send('POST', '/admin/products', body: {
          'name': name,
          'category': category,
          'description': description,
          'price': price,
          'stock': stock,
        });
      }
      nav.pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = e is ApiException
            ? (e.statusCode == 422
                ? 'The server rejected these values. Check every field.'
                : e.message)
            : 'Cannot reach the server. Is the backend running?';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: Text(_editing ? 'Edit product #${widget.product!['id']}' : 'New product')),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 600),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              TextField(
                controller: _name,
                decoration: const InputDecoration(
                    labelText: 'Name', border: OutlineInputBorder()),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _category,
                decoration: const InputDecoration(
                    labelText: 'Category (for example earbuds)',
                    border: OutlineInputBorder()),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _description,
                minLines: 3,
                maxLines: 6,
                decoration: const InputDecoration(
                    labelText: 'Description', border: OutlineInputBorder()),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _price,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                          labelText: 'Price (Rs)',
                          border: OutlineInputBorder()),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _stock,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                          labelText: 'Stock', border: OutlineInputBorder()),
                    ),
                  ),
                ],
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!,
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.error)),
              ],
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _busy ? null : _save,
                child: _busy
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(_editing ? 'Save changes' : 'Create product'),
              ),
              const SizedBox(height: 8),
              const Text(
                  'Brand, specs, images and guides are managed by the import scripts, not here.',
                  style: TextStyle(fontSize: 12, color: Colors.grey)),
            ],
          ),
        ),
      ),
    );
  }
}
