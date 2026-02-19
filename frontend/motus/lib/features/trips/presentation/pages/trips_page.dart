import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:motus/core/di/injection_container.dart';
import 'package:motus/features/trips/presentation/bloc/trips_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/trips_event.dart';
import 'package:motus/features/trips/presentation/bloc/trips_state.dart';
import 'package:motus/features/trips/presentation/widgets/trip_card.dart';

class TripsPage extends StatelessWidget {
  const TripsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => sl<TripsBloc>()..add(LoadTrips()),
      child: const _MyTripsView(),
    );
  }
}

class _MyTripsView extends StatelessWidget {
  const _MyTripsView();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          context.go('/book');
        },
        child: const Icon(Icons.add),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "My Trips",
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 20),
              _TripsTabs(),
              const SizedBox(height: 20),
              Expanded(child: _TripsList()),
            ],
          ),
        ),
      ),
    );
  }
}

class _TripsTabs extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return BlocBuilder<TripsBloc, TripsState>(
      builder: (context, state) {
        if (state is! TripsLoaded) return const SizedBox();

        return Row(
          children: [
            _tabButton(context, "Active", true, state.isActiveTab),
            const SizedBox(width: 20),
            _tabButton(context, "Past", false, state.isActiveTab),
          ],
        );
      },
    );
  }

  Widget _tabButton(
    BuildContext context,
    String title,
    bool value,
    bool current,
  ) {
    final isSelected = value == current;

    return GestureDetector(
      onTap: () => context.read<TripsBloc>().add(ChangeTripTab(value)),
      child: Column(
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 16,
              color: isSelected ? Colors.blue : Colors.black54,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            ),
          ),
          if (isSelected)
            Container(
              margin: const EdgeInsets.only(top: 4),
              height: 2,
              width: 40,
              color: Colors.blue,
            ),
        ],
      ),
    );
  }
}

class _TripsList extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return BlocBuilder<TripsBloc, TripsState>(
      builder: (context, state) {
        if (state is TripsLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is TripsLoaded) {
          final trips = state.isActiveTab ? state.activeTrips : state.pastTrips;

          if (trips.isEmpty) {
            return const Center(child: Text("No trips found"));
          }

          return ListView.builder(
            itemCount: trips.length,
            itemBuilder: (_, index) => TripCard(
              tripId: trips[index].id.toString(),
              tripDateTime: trips[index].tripDateTime,
              startLocation: trips[index].startLocation,
              destination: trips[index].destination,
            ),
          );
        }

        return const SizedBox();
      },
    );
  }
}
