import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:motus/core/di/injection_container.dart';
import 'package:motus/core/layout/main_scaffold.dart';
import 'package:motus/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:motus/features/auth/presentation/pages/register_page.dart';
import 'package:motus/features/home/presentation/pages/home_page.dart';
import 'package:motus/features/profile/presentation/bloc/profile_bloc.dart';
import 'package:motus/features/profile/presentation/bloc/profile_event.dart';
import 'package:motus/features/profile/presentation/pages/profile_page.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/trips/trips_bloc.dart';
import 'package:motus/features/trips/presentation/pages/book_trip.dart';
import 'package:motus/features/trips/presentation/pages/map_page.dart';
import 'package:motus/features/trips/presentation/pages/trips_page.dart';

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
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/map',
                builder: (context, state) => BlocProvider(
                  create: (context) => sl<AuthBloc>(),
                  child: const CampusMapPage(),
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/book',
                builder: (context, state) => BlocProvider(
                  create: (context) => sl<BookingBloc>(),
                  child: const BookTripPage(),
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/trips',
                builder: (context, state) => BlocProvider(
                  create: (context) => sl<TripsBloc>(),
                  child: const TripsPage(),
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                builder: (context, state) => BlocProvider(
                  create: (context) =>
                      sl<ProfileBloc>()..add(LoadProfileEvent()),
                  child: const ProfilePage(),
                ),
              ),
            ],
          ),
        ],
      ),
    ],
  );
}
