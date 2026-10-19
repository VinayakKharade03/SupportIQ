import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import 'admin_knowledge_edit_screen.dart';

class AdminKnowledgeScreen extends StatefulWidget {
  const AdminKnowledgeScreen({super.key});

  @override
  State<AdminKnowledgeScreen> createState() => _AdminKnowledgeScreenState();
}

class _AdminKnowledgeScreenState extends State<AdminKnowledgeScreen> {
  List<Map<String, dynamic>> _docs = [];
  int _chunks = 0;
  bool _inSync = true;
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
      final res =
          await context.read<ApiClient>().send('GET', '/admin/knowledge');
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _docs = (data['documents'] as List).cast<Map<String, dynamic>>();
        _chunks = (data['total_chunks'] as num).toInt();
        _inSync = data['in_sync'] == true;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = _msg(e);
        _loading = false;
      });
    }
  }

  Future<void> _open([String? filename]) async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
          builder: (_) => AdminKnowledgeEditScreen(filename: filename)),
    );
    if (saved == true) _load();
  }

  Future<void> _rebuild() async {
    final messenger = ScaffoldMessenger.of(context);
    final api = context.read<ApiClient>();
    setState(() => _busy = true);
    try {
      final res = await api.send('POST', '/admin/knowledge/rebuild');
      final d = jsonDecode(res.body) as Map<String, dynamic>;
      messenger.showSnackBar(SnackBar(
          content: Text(
              'Rebuilt: ${d['documents']} documents, ${d['total_chunks']} chunks')));
      await _load();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _delete(String filename) async {
    final messenger = ScaffoldMessenger.of(context);
    final api = context.read<ApiClient>();
    final go = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Delete $filename?'),
        content: const Text(
            'The chatbot stops using it straight away. The last document cannot be deleted.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (go != true) return;
    setState(() => _busy = true);
    try {
      await api.send('DELETE', '/admin/knowledge/$filename');
      messenger.showSnackBar(const SnackBar(content: Text('Deleted')));
      await _load();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Knowledge base'), actions: [
        IconButton(
            tooltip: 'Rebuild index',
            icon: const Icon(Icons.build_circle_outlined),
            onPressed: _busy ? null : _rebuild),
        IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _load),
      ]),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _busy ? null : () => _open(),
        icon: const Icon(Icons.add),
        label: const Text('New document'),
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
              : Column(
                  children: [
                    Container(
                      width: double.infinity,
                      color: _inSync
                          ? Colors.green.shade100
                          : Colors.orange.shade100,
                      padding: const EdgeInsets.all(12),
                      child: Text(_inSync
                          ? '${_docs.length} documents, $_chunks chunks, index in sync'
                          : '${_docs.length} documents, $_chunks chunks. Index is out of sync: tap the rebuild icon.'),
                    ),
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.fromLTRB(12, 12, 12, 88),
                        itemCount: _docs.length,
                        itemBuilder: (context, i) {
                          final d = _docs[i];
                          final name = '${d['filename']}';
                          return Card(
                            child: ListTile(
                              title: Text(name),
                              subtitle: Text(
                                  '${d['size_bytes']} bytes | ${d['chunks']} chunks${d['indexed'] == true ? '' : ' | not indexed'}'),
                              trailing: IconButton(
                                tooltip: 'Delete',
                                icon: const Icon(Icons.delete_outline),
                                onPressed: _busy ? null : () => _delete(name),
                              ),
                              onTap: _busy ? null : () => _open(name),
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
