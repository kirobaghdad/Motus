import 'package:motus/features/trips/domain/repositories/trip_repository.dart';

class BookTripUseCase {
  final TripRepository repository;

  BookTripUseCase(this.repository);

  Future<void> call(
    String startLocation,
    String destination,
    DateTime tripDateTime,
  ) {
    try {
      return repository.bookTrip(startLocation, destination, tripDateTime);
    } catch (e) {
      throw Exception(e);
    }
  }
}
