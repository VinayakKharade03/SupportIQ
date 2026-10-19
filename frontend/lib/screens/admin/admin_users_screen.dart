import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import 'admin_user_detail_screen.dart';

class AdminUsersScreen extends StatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  State<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends State<AdminUsersScreen> {
  final _search = TextEditingController();
  List<Map<String, dynamic>> _users = [];
  bool _loading = true;
  String? _error;

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

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final q = _search.text.trim();
      final qs = q.isEmpty ? '' : '&search=${Uri.encodeQueryComponent(q)}';
      final res = await context
          .read<ApiClient>()
          .send('GET', '/admin/users?limit=100$qs');
      setState(() {
        _users = (jsonDecode(res.body) as List).cast<Map<String, dynamic>>();
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
      appBar: AppBar(title: const Text('Users'), actions: [
        IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _load),
      ]),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _load(),
              decoration: InputDecoration(
                hintText: 'Search name or email',
                border: const OutlineInputBorder(),
                isDense: true,
                suffixIcon: IconButton(
                    icon: const Icon(Icons.search), onPressed: _load),
              ),
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
                    : _users.isEmpty
                        ? const Center(child: Text('No users'))
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            itemCount: _users.length,
                            itemBuilder: (context, i) {
                              final u = _users[i];
                              final name = (u['full_name'] as String?)?.trim();
                              return Card(
                                child: ListTile(
                                  title: Text(name != null && name.isNotEmpty
                                      ? name
                                      : '${u['email']}'),
                                  subtitle: Text('#${u['id']}  ${u['email']}'),
                                  trailing: u['is_admin'] == true
                                      ? const Chip(label: Text('Admin'))
                                      : null,
                                  onTap: () async {
                                    await Navigator.of(context).push(
                                      MaterialPageRoute(
                                        builder: (_) => AdminUserDetailScreen(
                                            userId: (u['id'] as num).toInt()),
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
