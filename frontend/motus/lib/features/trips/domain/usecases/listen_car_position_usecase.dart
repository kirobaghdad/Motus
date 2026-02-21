import '../repositories/trip_map_repository.dart';
import '../entities/pixel.dart';

class ListenCarPositionUsecase {
  final TripMapRepository repository;

  ListenCarPositionUsecase(this.repository);

  Stream<PixelPoint> call() {
    return repository.getCarPositionStream();
  }
}
