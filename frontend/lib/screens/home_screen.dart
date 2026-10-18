import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/auth_provider.dart';
import 'connection_check_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.user ?? {};
    final name = (user['full_name'] as String?)?.trim();
    return Scaffold(
      appBar: AppBar(
        title: const Text('SupportIQ'),
        actions: [
          IconButton(
            tooltip: 'Log out',
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Logged in as ${(name != null && name.isNotEmpty) ? name : user['email']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text('${user['email']}'),
            if (auth.isAdmin) ...[
              const SizedBox(height: 8),
              const Chip(label: Text('Admin')),
            ],
            const SizedBox(height: 24),
            OutlinedButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => const ConnectionCheckScreen(),
                ),
              ),
              child: const Text('Connection check'),
            ),
          ],
        ),
      ),
    );
  }
}
