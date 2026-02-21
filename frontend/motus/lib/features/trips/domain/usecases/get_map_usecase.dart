import 'dart:typed_data';
import '../repositories/trip_map_repository.dart';

class GetMapImageUsecase {
  final TripMapRepository repository;

  GetMapImageUsecase(this.repository);

  Future<Uint8List> call() {
    return repository.getMapImage();
  }
}
