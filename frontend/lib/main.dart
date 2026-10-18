import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const String _envBaseUrl = String.fromEnvironment('API_BASE_URL');

String get apiBaseUrl {
  if (_envBaseUrl.isNotEmpty) return _envBaseUrl;
  if (!kIsWeb && Platform.isAndroid) return 'http://10.0.2.2:8000';
  return 'http://localhost:8000';
}

void main() {
  runApp(const SupportIQApp());
}

class SupportIQApp extends StatelessWidget {
  const SupportIQApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SupportIQ',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      home: const ConnectionCheckScreen(),
    );
  }
}

class ConnectionCheckScreen extends StatefulWidget {
  const ConnectionCheckScreen({super.key});

  @override
  State<ConnectionCheckScreen> createState() => _ConnectionCheckScreenState();
}

class _ConnectionCheckScreenState extends State<ConnectionCheckScreen> {
  String _status = 'Checking...';
  bool _ok = false;
  bool _loading = true;
  List<dynamic> _products = [];

  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    setState(() {
      _loading = true;
      _status = 'Checking $apiBaseUrl ...';
    });
    try {
      final health = await http
          .get(Uri.parse('$apiBaseUrl/health'))
          .timeout(const Duration(seconds: 10));
      if (health.statusCode != 200) {
        throw Exception('/health returned ${health.statusCode}');
      }
      final res = await http
          .get(Uri.parse('$apiBaseUrl/products?limit=100'))
          .timeout(const Duration(seconds: 10));
      if (res.statusCode != 200) {
        throw Exception('/products returned ${res.statusCode}');
      }
      final data = jsonDecode(res.body) as List<dynamic>;
      setState(() {
        _products = data;
        _ok = true;
        _status = 'Connected: health ok, ${data.length} products';
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _products = [];
        _ok = false;
        _status = 'Failed: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('SupportIQ connection check')),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            color: _loading
                ? Colors.grey.shade300
                : (_ok ? Colors.green.shade100 : Colors.red.shade100),
            padding: const EdgeInsets.all(12),
            child: Text(_status),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: _products.length,
              itemBuilder: (context, i) {
                final p = _products[i] as Map<String, dynamic>;
                final imageUrl = p['image_url'] as String?;
                return ListTile(
                  leading: imageUrl == null
                      ? const SizedBox(width: 56, height: 56)
                      : Image.network(
                          '$apiBaseUrl$imageUrl',
                          width: 56,
                          height: 56,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) =>
                              const Icon(Icons.broken_image),
                        ),
                  title: Text('${p['name']}'),
                  subtitle: Text('${p['category']}  |  Rs ${p['price']}'),
                );
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _check,
        child: const Icon(Icons.refresh),
      ),
    );
  }
}
