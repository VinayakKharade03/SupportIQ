import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../api/api_client.dart';

class ProductDetailScreen extends StatefulWidget {
  final int productId;
  final String? title;
  const ProductDetailScreen({super.key, required this.productId, this.title});

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  Map<String, dynamic>? _p;
  bool _loading = true;
  String? _error;
  int _imageIndex = 0;

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
          .get(Uri.parse('$apiBaseUrl/products/${widget.productId}'))
          .timeout(const Duration(seconds: 15));
      if (res.statusCode == 404) {
        throw Exception('This product is no longer available');
      }
      if (res.statusCode != 200) {
        throw Exception('Server returned ${res.statusCode}');
      }
      setState(() {
        _p = jsonDecode(res.body) as Map<String, dynamic>;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  String _money(num v) => 'Rs ${v.toStringAsFixed(0)}';

  List<Map<String, dynamic>> _list(String key) =>
      ((_p?[key] as List?) ?? const []).cast<Map<String, dynamic>>();

  List<String> _strings(String key) =>
      ((_p?[key] as List?) ?? const []).map((e) => '$e').toList();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_p?['name'] as String? ?? widget.title ?? 'Product')),
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
    final p = _p!;
    final theme = Theme.of(context);
    final images = _list('images');
    final highlights = _strings('highlights');
    final inBox = _strings('in_the_box');
    final specs = _list('specs');
    final brand = p['brand'] as String?;
    final tagline = p['tagline'] as String?;
    final description = p['description'] as String?;
    final price = p['price'] as num;
    final mrp = p['mrp'] as num?;
    final stock = (p['stock'] as num?)?.toInt() ?? 0;
    final discount = (mrp != null && mrp > price)
        ? (((mrp - price) / mrp) * 100).round()
        : null;

    final groups = <String, List<Map<String, dynamic>>>{};
    for (final s in specs) {
      groups.putIfAbsent(s['group_name'] as String, () => []).add(s);
    }

    final safeIndex = images.isEmpty ? 0 : _imageIndex.clamp(0, images.length - 1);

    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            AspectRatio(
              aspectRatio: 1.4,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: images.isEmpty
                    ? Container(
                        color: Colors.grey.shade200,
                        child: const Icon(Icons.headphones, size: 72),
                      )
                    : Image.network(
                        '$apiBaseUrl${images[safeIndex]['url']}',
                        fit: BoxFit.contain,
                        errorBuilder: (_, __, ___) =>
                            const Icon(Icons.broken_image, size: 48),
                      ),
              ),
            ),
            if (images.length > 1) ...[
              const SizedBox(height: 8),
              SizedBox(
                height: 64,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: images.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, i) => GestureDetector(
                    onTap: () => setState(() => _imageIndex = i),
                    child: Container(
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: i == safeIndex
                              ? theme.colorScheme.primary
                              : Colors.transparent,
                          width: 2,
                        ),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: Image.network(
                          '$apiBaseUrl${images[i]['url']}',
                          width: 64,
                          height: 60,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) =>
                              const Icon(Icons.broken_image),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),
            if (brand != null) Text(brand, style: theme.textTheme.labelLarge),
            Text('${p['name']}', style: theme.textTheme.headlineSmall),
            if (tagline != null) ...[
              const SizedBox(height: 4),
              Text(tagline, style: theme.textTheme.bodyLarge),
            ],
            const SizedBox(height: 12),
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 10,
              children: [
                Text(_money(price), style: theme.textTheme.headlineSmall),
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
            if (description != null && description.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(description),
            ],
            if (highlights.isNotEmpty) ...[
              _heading(context, 'Highlights'),
              for (final h in highlights) _bullet(h),
            ],
            if (inBox.isNotEmpty) ...[
              _heading(context, 'In the box'),
              for (final b in inBox) _bullet(b),
            ],
            if (groups.isNotEmpty) ...[
              _heading(context, 'Specifications'),
              for (final entry in groups.entries) ...[
                Padding(
                  padding: const EdgeInsets.only(top: 8, bottom: 4),
                  child: Text(entry.key, style: theme.textTheme.titleSmall),
                ),
                for (final s in entry.value)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          flex: 2,
                          child: Text('${s['name']}',
                              style: const TextStyle(color: Colors.grey)),
                        ),
                        Expanded(flex: 3, child: Text('${s['value']}')),
                      ],
                    ),
                  ),
              ],
            ],
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _heading(BuildContext context, String text) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 6),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium),
      );

  Widget _bullet(String text) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('•  '),
            Expanded(child: Text(text)),
          ],
        ),
      );
}
