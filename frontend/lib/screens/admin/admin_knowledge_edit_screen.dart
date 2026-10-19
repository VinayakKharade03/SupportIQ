import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';

import '../../api/api_client.dart';

class AdminKnowledgeEditScreen extends StatefulWidget {
  final String? filename; // null = new document
  const AdminKnowledgeEditScreen({super.key, this.filename});

  @override
  State<AdminKnowledgeEditScreen> createState() =>
      _AdminKnowledgeEditScreenState();
}

class _AdminKnowledgeEditScreenState extends State<AdminKnowledgeEditScreen> {
  final _name = TextEditingController();
  final _content = TextEditingController();
  bool _loading = false;
  bool _busy = false;
  String? _error;

  bool get _editing => widget.filename != null;

  @override
  void initState() {
    super.initState();
    if (_editing) {
      _name.text = widget.filename!;
      _load();
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _content.dispose();
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
      final res = await context
          .read<ApiClient>()
          .send('GET', '/admin/knowledge/${widget.filename}');
      final d = jsonDecode(res.body) as Map<String, dynamic>;
      _content.text = '${d['content']}';
      setState(() => _loading = false);
    } catch (e) {
      setState(() {
        _error = _msg(e);
        _loading = false;
      });
    }
  }

  Future<http.Response> _upload(String token, String name, String text) async {
    final req = http.MultipartRequest(
        'POST',
        Uri.parse(
            '$apiBaseUrl/admin/knowledge?overwrite=${_editing ? 'true' : 'false'}'))
      ..headers['Authorization'] = 'Bearer $token'
      ..files.add(http.MultipartFile.fromBytes('file', utf8.encode(text),
          filename: name));
    final streamed = await req.send().timeout(const Duration(seconds: 120));
    return http.Response.fromStream(streamed);
  }

  Future<void> _save() async {
    var name = _name.text.trim();
    final text = _content.text;
    if (name.isEmpty || text.trim().isEmpty) {
      setState(() => _error = 'File name and content are required.');
      return;
    }
    if (!name.toLowerCase().endsWith('.txt')) name = '$name.txt';

    final api = context.read<ApiClient>();
    final nav = Navigator.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      var token = await api.accessToken ?? '';
      var res = await _upload(token, name, text);
      if (res.statusCode == 401) {
        await api.me(); // refreshes the access token
        token = await api.accessToken ?? '';
        res = await _upload(token, name, text);
      }
      if (res.statusCode == 200 || res.statusCode == 201) {
        nav.pop(true);
        return;
      }
      String detail = 'Upload failed (${res.statusCode})';
      try {
        final b = jsonDecode(res.body);
        if (b is Map && b['detail'] is String) detail = b['detail'] as String;
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = detail;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = _msg(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: Text(_editing ? 'Edit ${widget.filename}' : 'New document')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    TextField(
                      controller: _name,
                      enabled: !_editing,
                      decoration: const InputDecoration(
                        labelText: 'File name (a-z, 0-9, - and _ only)',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _content,
                      minLines: 12,
                      maxLines: 24,
                      decoration: const InputDecoration(
                        labelText: 'Content',
                        alignLabelWithHint: true,
                        border: OutlineInputBorder(),
                      ),
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
                              child:
                                  CircularProgressIndicator(strokeWidth: 2))
                          : Text(_editing ? 'Save and re-index' : 'Create and index'),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                        'Saving rebuilds the chatbot index, so it can take a few seconds.',
                        style: TextStyle(fontSize: 12, color: Colors.grey)),
                  ],
                ),
              ),
            ),
    );
  }
}
