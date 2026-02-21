import 'package:motus/features/trips/domain/entities/trip.dart';

abstract class TripsState {}

class TripsInitial extends TripsState {}

class TripsLoading extends TripsState {}

class TripsLoaded extends TripsState {
  final List<Trip> activeTrips;
  final List<Trip> pastTrips;
  final bool isActiveTab;

  TripsLoaded({
    required this.activeTrips,
    required this.pastTrips,
    required this.isActiveTab,
  });
}

class TripsError extends TripsState {
  final String message;
  TripsError(this.message);
}
