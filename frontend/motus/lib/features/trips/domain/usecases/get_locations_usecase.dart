import 'package:motus/features/trips/domain/repositories/trip_repository.dart';

class GetLocationsUsecase {
  final TripRepository repository;

  GetLocationsUsecase(this.repository);

  Future<List<String>> call()async{
    return await repository.getLocations();
  }
}
