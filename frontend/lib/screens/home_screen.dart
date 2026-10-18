import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/auth_provider.dart';
import '../state/cart_provider.dart';
import 'cart_screen.dart';
import 'connection_check_screen.dart';
import 'orders_screen.dart';
import 'product_list_screen.dart';

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
            onPressed: () {
              context.read<CartProvider>().clear();
              context.read<AuthProvider>().logout();
            },
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
            FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const ProductListScreen()),
              ),
              child: const Text('Browse products'),
            ),
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const CartScreen()),
              ),
              child: const Text('Cart'),
            ),
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const OrdersScreen()),
              ),
              child: const Text('My orders'),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(
                    builder: (_) => const ConnectionCheckScreen()),
              ),
              child: const Text('Connection check'),
            ),
          ],
        ),
      ),
    );
  }
}
