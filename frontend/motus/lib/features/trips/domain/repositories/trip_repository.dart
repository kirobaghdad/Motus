import 'package:motus/features/trips/domain/entities/trip.dart';

abstract class TripRepository {
  Future<void> bookTrip(
    String startLocation,
    String destination,
    DateTime tripDateTime,
  );
  Future<List<String>> getLocations();
  Future<List<Trip>?> getTrips();
}
