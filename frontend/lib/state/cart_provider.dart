import 'package:flutter/foundation.dart';

import '../api/api_client.dart';

class CartProvider extends ChangeNotifier {
  final ApiClient api;

  CartProvider(this.api);

  List<Map<String, dynamic>> _items = [];
  num _total = 0;
  bool _loading = false;
  bool _busy = false;
  String? _error;

  List<Map<String, dynamic>> get items => _items;
  num get total => _total;
  bool get loading => _loading;
  bool get busy => _busy;
  String? get error => _error;
  bool get isEmpty => _items.isEmpty;
  int get units =>
      _items.fold<int>(0, (sum, i) => sum + (i['quantity'] as num).toInt());

  void _apply(Map<String, dynamic> data) {
    _items = ((data['items'] as List?) ?? const [])
        .cast<Map<String, dynamic>>();
    _total = (data['total'] as num?) ?? 0;
  }

  String _message(Object e) {
    if (e is ApiException) {
      if (e.statusCode == 401) return 'Session expired. Please log in again.';
      return e.message;
    }
    return 'Cannot reach the server. Is the backend running?';
  }

  Future<void> load() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      final res = await api.send('GET', '/orders/cart');
      _apply(api.decode(res));
    } catch (e) {
      _error = _message(e);
    }
    _loading = false;
    notifyListeners();
  }

  Future<bool> add(int productId, {int quantity = 1}) async {
    return _run(() async {
      final res = await api.send('POST', '/orders/cart/add',
          body: {'product_id': productId, 'quantity': quantity});
      _apply(api.decode(res));
    });
  }

  Future<bool> remove(int productId) async {
    return _run(() async {
      final res = await api.send('POST', '/orders/cart/remove',
          body: {'product_id': productId});
      _apply(api.decode(res));
    });
  }

  /// Sets a line to an exact quantity. Quantity 0 removes the line.
  /// The API has no update endpoint, so this is remove then add.
  Future<bool> setQuantity(int productId, int quantity) async {
    final ok = await _run(() async {
      final res = await api.send('POST', '/orders/cart/remove',
          body: {'product_id': productId});
      _apply(api.decode(res));
      if (quantity > 0) {
        final res2 = await api.send('POST', '/orders/cart/add',
            body: {'product_id': productId, 'quantity': quantity});
        _apply(api.decode(res2));
      }
    });
    if (!ok) {
      final message = _error;
      await load(); // show the true cart state after a partial failure
      _error = message;
      notifyListeners();
    }
    return ok;
  }
  /// Returns the confirm response (order_id, status, total, message) or null.
  Future<Map<String, dynamic>?> confirm() async {
    Map<String, dynamic>? result;
    final ok = await _run(() async {
      final res = await api.send('POST', '/orders/confirm');
      result = api.decode(res);
      _items = [];
      _total = 0;
    });
    return ok ? result : null;
  }

  Future<bool> _run(Future<void> Function() action) async {
    _busy = true;
    _error = null;
    notifyListeners();
    var ok = true;
    try {
      await action();
    } catch (e) {
      _error = _message(e);
      ok = false;
    }
    _busy = false;
    notifyListeners();
    return ok;
  }

  void clear() {
    _items = [];
    _total = 0;
    _error = null;
    notifyListeners();
  }
}
