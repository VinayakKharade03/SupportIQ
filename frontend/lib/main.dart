import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'api/api_client.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'state/auth_provider.dart';

void main() {
  runApp(const SupportIQApp());
}

class SupportIQApp extends StatelessWidget {
  const SupportIQApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiClient>(create: (_) => ApiClient()),
        ChangeNotifierProvider<AuthProvider>(
          create: (ctx) =>
              AuthProvider(ctx.read<ApiClient>())..restoreSession(),
        ),
      ],
      child: MaterialApp(
        title: 'SupportIQ',
        theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
        home: const AuthGate(),
      ),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final status = context.watch<AuthProvider>().status;
    switch (status) {
      case AuthStatus.unknown:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.loggedOut:
        return const LoginScreen();
      case AuthStatus.loggedIn:
        return const HomeScreen();
    }
  }
}
