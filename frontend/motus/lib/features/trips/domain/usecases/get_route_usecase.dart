import '../repositories/trip_map_repository.dart';
import '../entities/pixel.dart';

class GetRouteUsecase {
  final TripMapRepository repository;

  GetRouteUsecase(this.repository);

  Future<List<PixelPoint>> call() {
    return repository.getRoutePixels();
  }
}
