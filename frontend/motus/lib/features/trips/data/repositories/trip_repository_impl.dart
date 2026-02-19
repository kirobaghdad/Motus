import 'package:motus/features/trips/data/data_sources/trip_remote_data_sources.dart';
import 'package:motus/features/trips/domain/entities/trip.dart';
import 'package:motus/features/trips/domain/repositories/trip_repository.dart';

class TripRepositoryImpl extends TripRepository {
  final TripRemoteDataSource remoteDataSource;

  TripRepositoryImpl(this.remoteDataSource);

  @override
  Future<void> bookTrip(
    String startLocation,
    String destination,
    DateTime tripDateTime,
  ) async {
    return await remoteDataSource.bookTrip(
      destination,
      startLocation,
      tripDateTime,
    );
  }

  @override
  Future<List<Trip>> getTrips() async {
    final trips = await remoteDataSource.getTrips();
    return trips;
  }

  @override
  Future<List<String>> getLocations() async {
    final locations = await remoteDataSource.getLocations();
    return locations;
  }
}
