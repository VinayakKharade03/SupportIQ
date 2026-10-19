import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../../state/auth_provider.dart';
import '../orders_screen.dart' show formatDate;

class AdminUserDetailScreen extends StatefulWidget {
  final int userId;
  const AdminUserDetailScreen({super.key, required this.userId});

  @override
  State<AdminUserDetailScreen> createState() => _AdminUserDetailScreenState();
}

class _AdminUserDetailScreenState extends State<AdminUserDetailScreen> {
  Map<String, dynamic>? _u;
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
      final res = await context
          .read<ApiClient>()
          .send('GET', '/admin/users/${widget.userId}');
      setState(() {
        _u = jsonDecode(res.body) as Map<String, dynamic>;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = _msg(e);
        _loading = false;
      });
    }
  }

  Future<void> _toggleAdmin() async {
    final messenger = ScaffoldMessenger.of(context);
    final api = context.read<ApiClient>();
    final makeAdmin = _u!['is_admin'] != true;
    final go = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(makeAdmin ? 'Make this user an admin?' : 'Remove admin rights?'),
        content: Text('${_u!['email']}'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Confirm')),
        ],
      ),
    );
    if (go != true) return;
    setState(() => _busy = true);
    try {
      final res = await api.send('PATCH', '/admin/users/${widget.userId}/role',
          body: {'is_admin': makeAdmin});
      if (!mounted) return;
      setState(() {
        _u = jsonDecode(res.body) as Map<String, dynamic>;
        _busy = false;
      });
      messenger.showSnackBar(SnackBar(
          content: Text(makeAdmin ? 'User is now an admin' : 'Admin rights removed')));
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(_msg(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('User #${widget.userId}')),
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
    final u = _u!;
    final me = context.watch<AuthProvider>().user;
    final isSelf = me != null && me['id'] == u['id'];
    final isAdmin = u['is_admin'] == true;
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('${u['full_name'] ?? '(no name)'}',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text('${u['email']}'),
            Text('Joined: ${formatDate(u['created_at'] as String?)}'),
            const SizedBox(height: 8),
            if (isAdmin) const Chip(label: Text('Admin')),
            const SizedBox(height: 24),
            FilledButton.tonal(
              onPressed: (_busy || isSelf) ? null : _toggleAdmin,
              child: Text(isAdmin ? 'Remove admin rights' : 'Make admin'),
            ),
            if (isSelf)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('You cannot change your own admin status.'),
              ),
          ],
        ),
      ),
    );
  }
}
