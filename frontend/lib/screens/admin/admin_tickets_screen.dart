import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../api/api_client.dart';
import '../orders_screen.dart' show formatDate;
import 'admin_ticket_detail_screen.dart';

Color ticketColor(String s) {
  switch (s) {
    case 'open':
      return Colors.red.shade100;
    case 'in_progress':
      return Colors.orange.shade100;
    case 'resolved':
      return Colors.green.shade100;
    default:
      return Colors.grey.shade200;
  }
}

class AdminTicketsScreen extends StatefulWidget {
  const AdminTicketsScreen({super.key});

  @override
  State<AdminTicketsScreen> createState() => _AdminTicketsScreenState();
}

class _AdminTicketsScreenState extends State<AdminTicketsScreen> {
  List<Map<String, dynamic>> _tickets = [];
  bool _loading = true;
  String? _error;
  String? _status; // null = all

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
      final q = _status == null ? '' : '&status=$_status';
      final res = await context
          .read<ApiClient>()
          .send('GET', '/admin/tickets?limit=100$q');
      setState(() {
        _tickets = (jsonDecode(res.body) as List).cast<Map<String, dynamic>>();
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
    const filters = <String?, String>{
      null: 'All',
      'open': 'Open',
      'in_progress': 'In progress',
      'resolved': 'Resolved',
    };
    return Scaffold(
      appBar: AppBar(title: const Text('Tickets'), actions: [
        IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: _load),
      ]),
      body: Column(
        children: [
          SizedBox(
            height: 56,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: [
                for (final e in filters.entries)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(e.value),
                      selected: _status == e.key,
                      onSelected: (_) {
                        setState(() => _status = e.key);
                        _load();
                      },
                    ),
                  ),
              ],
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
                    : _tickets.isEmpty
                        ? const Center(child: Text('No tickets'))
                        : ListView.builder(
                            padding: const EdgeInsets.all(12),
                            itemCount: _tickets.length,
                            itemBuilder: (context, i) {
                              final t = _tickets[i];
                              final status = '${t['status']}';
                              return Card(
                                child: ListTile(
                                  title: Text('#${t['id']}  ${t['message']}',
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis),
                                  subtitle: Padding(
                                    padding: const EdgeInsets.only(top: 4),
                                    child: Wrap(
                                      spacing: 8,
                                      runSpacing: 4,
                                      crossAxisAlignment:
                                          WrapCrossAlignment.center,
                                      children: [
                                        Text(
                                            '${t['category']} | ${t['sentiment']} | ${t['source']} | ${formatDate(t['created_at'] as String?)}'),
                                        Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: ticketColor(status),
                                            borderRadius:
                                                BorderRadius.circular(10),
                                          ),
                                          child: Text(status,
                                              style: const TextStyle(
                                                  fontSize: 12)),
                                        ),
                                      ],
                                    ),
                                  ),
                                  onTap: () async {
                                    await Navigator.of(context).push(
                                      MaterialPageRoute(
                                        builder: (_) =>
                                            AdminTicketDetailScreen(
                                                ticketId:
                                                    (t['id'] as num).toInt()),
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
