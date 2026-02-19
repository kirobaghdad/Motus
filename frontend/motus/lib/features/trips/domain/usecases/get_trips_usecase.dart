import 'package:motus/features/trips/domain/entities/trip.dart';
import 'package:motus/features/trips/domain/repositories/trip_repository.dart';

class GetTripsUseCase {
  final TripRepository repository;

  GetTripsUseCase(this.repository);

  Future<List<Trip>?> call() async {
    return await repository.getTrips();
  }
}
