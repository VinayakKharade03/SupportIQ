import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../api/api_client.dart';
import 'product_detail_screen.dart';

class ProductListScreen extends StatefulWidget {
  const ProductListScreen({super.key});

  @override
  State<ProductListScreen> createState() => _ProductListScreenState();
}

class _ProductListScreenState extends State<ProductListScreen> {
  List<Map<String, dynamic>> _products = [];
  bool _loading = true;
  String? _error;
  String? _category; // null = all

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
      final res = await http
          .get(Uri.parse('$apiBaseUrl/products?limit=100'))
          .timeout(const Duration(seconds: 15));
      if (res.statusCode != 200) {
        throw Exception('Server returned ${res.statusCode}');
      }
      final data = jsonDecode(res.body) as List<dynamic>;
      setState(() {
        _products = data.cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Could not load products: $e';
        _loading = false;
      });
    }
  }

  String _money(num v) => 'Rs ${v.toStringAsFixed(0)}';

  @override
  Widget build(BuildContext context) {
    final categories = _products
        .map((p) => p['category'] as String)
        .toSet()
        .toList()
      ..sort();
    final shown = _category == null
        ? _products
        : _products.where((p) => p['category'] == _category).toList();

    return PopScope(
      canPop: _category == null,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) setState(() => _category = null);
      },
      child: _scaffold(categories, shown),
    );
  }

  Widget _scaffold(
      List<String> categories, List<Map<String, dynamic>> shown) {
    return Scaffold(
      appBar: AppBar(title: const Text('Products')),
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
              : Column(
                  children: [
                    SizedBox(
                      height: 56,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
                        children: [
                          Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: ChoiceChip(
                              label: const Text('All'),
                              selected: _category == null,
                              onSelected: (_) =>
                                  setState(() => _category = null),
                            ),
                          ),
                          for (final c in categories)
                            Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ChoiceChip(
                                label: Text(c),
                                selected: _category == c,
                                onSelected: (_) =>
                                    setState(() => _category = c),
                              ),
                            ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: RefreshIndicator(
                        onRefresh: _load,
                        child: ListView.builder(
                          padding: const EdgeInsets.all(12),
                          itemCount: shown.length,
                          itemBuilder: (context, i) => _card(shown[i]),
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }

  Widget _card(Map<String, dynamic> p) {
    final imageUrl = p['image_url'] as String?;
    final tagline = p['tagline'] as String?;
    final brand = p['brand'] as String?;
    final price = p['price'] as num;
    final mrp = p['mrp'] as num?;
    final stock = (p['stock'] as num?)?.toInt() ?? 0;
    final discount = (mrp != null && mrp > price)
        ? (((mrp - price) / mrp) * 100).round()
        : null;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ProductDetailScreen(
              productId: (p['id'] as num).toInt(),
              title: p['name'] as String?,
            ),
          ),
        ),
        child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: SizedBox(
                width: 96,
                height: 96,
                child: imageUrl == null
                    ? Container(
                        color: Colors.grey.shade200,
                        child: const Icon(Icons.headphones, size: 40),
                      )
                    : Image.network(
                        '$apiBaseUrl$imageUrl',
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) =>
                            const Icon(Icons.broken_image),
                      ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (brand != null)
                    Text(brand,
                        style: Theme.of(context).textTheme.labelMedium),
                  Text('${p['name']}',
                      style: Theme.of(context).textTheme.titleMedium),
                  if (tagline != null)
                    Text(tagline,
                        maxLines: 2, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 6),
                  Wrap(
                    crossAxisAlignment: WrapCrossAlignment.center,
                    spacing: 8,
                    children: [
                      Text(_money(price),
                          style: Theme.of(context).textTheme.titleMedium),
                      if (mrp != null && mrp > price)
                        Text(
                          _money(mrp),
                          style: const TextStyle(
                              decoration: TextDecoration.lineThrough,
                              color: Colors.grey),
                        ),
                      if (discount != null)
                        Text('$discount% off',
                            style: TextStyle(color: Colors.green.shade700)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    stock > 0 ? 'In stock' : 'Out of stock',
                    style: TextStyle(
                        color: stock > 0
                            ? Colors.green.shade700
                            : Colors.red.shade700),
                  ),
                ],
              ),
            ),
          ],
        ),
        ),
      ),
    );
  }
}
