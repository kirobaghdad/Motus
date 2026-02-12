import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:motus/core/di/injection_container.dart';
import 'package:motus/core/layout/main_scaffold.dart';
import 'package:motus/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:motus/features/auth/presentation/pages/register_page.dart';
import 'package:motus/features/home/presentation/home_page.dart';

import '../../features/auth/presentation/pages/login_page.dart';

class AppRoutes {
  static GoRouter appRouter = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => BlocProvider(
          create: (context) => sl<AuthBloc>(),
          child: LoginPage(),
        ),
      ),
      GoRoute(
        path: '/register',
        builder: (context, state) => BlocProvider(
          create: (context) => sl<AuthBloc>(),
          child: RegisterPage(),
        ),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return MainScaffold(navigationShell: navigationShell);
        },
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/home',
                builder: (context, state) => const HomePage(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
}
