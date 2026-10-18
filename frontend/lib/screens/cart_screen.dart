import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/cart_provider.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key});

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CartProvider>().load();
    });
  }

  String _money(num v) => 'Rs ${v.toStringAsFixed(0)}';

  Future<void> _confirm() async {
    final cart = context.read<CartProvider>();
    final messenger = ScaffoldMessenger.of(context);
    final go = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Place this order?'),
        content: Text(
            '${cart.units} item(s), total ${_money(cart.total)}. Stock is reserved when you confirm.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Confirm order')),
        ],
      ),
    );
    if (go != true) return;
    final result = await cart.confirm();
    if (result != null) {
      messenger.showSnackBar(SnackBar(
          content: Text(
              'Order #${result['order_id']} confirmed: ${_money(result['total'] as num)}')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<CartProvider>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Your cart'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: cart.busy ? null : () => cart.load(),
          ),
        ],
      ),
      body: cart.loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                if (cart.error != null)
                  Container(
                    width: double.infinity,
                    color: Colors.red.shade100,
                    padding: const EdgeInsets.all(12),
                    child: Text(cart.error!),
                  ),
                Expanded(
                  child: cart.isEmpty
                      ? const Center(child: Text('Your cart is empty'))
                      : ListView.separated(
                          padding: const EdgeInsets.all(12),
                          itemCount: cart.items.length,
                          separatorBuilder: (_, __) => const Divider(),
                          itemBuilder: (context, i) {
                            final it = cart.items[i];
                            return ListTile(
                              title: Text('${it['name']}'),
                              subtitle: Text(
                                  '${it['quantity']} x ${_money(it['unit_price'] as num)}'),
                              trailing: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  IconButton(
                                    tooltip: 'Decrease',
                                    icon: Icon((it['quantity'] as num) <= 1
                                        ? Icons.delete_outline
                                        : Icons.remove_circle_outline),
                                    onPressed: cart.busy
                                        ? null
                                        : () => cart.setQuantity(
                                            (it['product_id'] as num).toInt(),
                                            (it['quantity'] as num).toInt() - 1),
                                  ),
                                  Text('${it['quantity']}',
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleMedium),
                                  IconButton(
                                    tooltip: 'Increase',
                                    icon: const Icon(Icons.add_circle_outline),
                                    onPressed: cart.busy
                                        ? null
                                        : () => cart.add(
                                            (it['product_id'] as num).toInt()),
                                  ),
                                  const SizedBox(width: 8),
                                  SizedBox(
                                    width: 80,
                                    child: Text(
                                        _money(it['line_total'] as num),
                                        textAlign: TextAlign.end,
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleMedium),
                                  ),
                                  IconButton(
                                    tooltip: 'Remove item',
                                    icon: const Icon(Icons.close),
                                    onPressed: cart.busy
                                        ? null
                                        : () => cart.remove(
                                            (it['product_id'] as num).toInt()),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                ),
                if (!cart.isEmpty)
                  SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text('Total: ${_money(cart.total)}',
                                style:
                                    Theme.of(context).textTheme.titleLarge),
                          ),
                          FilledButton(
                            onPressed: cart.busy ? null : _confirm,
                            child: cart.busy
                                ? const SizedBox(
                                    height: 18,
                                    width: 18,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2),
                                  )
                                : const Text('Confirm order'),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
    );
  }
}
