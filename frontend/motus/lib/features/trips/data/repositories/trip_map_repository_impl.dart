import 'dart:typed_data';
import '../../domain/entities/pixel.dart';
import '../../domain/repositories/trip_map_repository.dart';
import '../data_sources/trip_map_remote_data_source.dart';
import '../data_sources/socket_service.dart';

class TripMapRepositoryImpl implements TripMapRepository {
  final TripMapRemoteDataSource remoteDataSource;
  final SocketService socketService;

  TripMapRepositoryImpl({
    required this.remoteDataSource,
    required this.socketService,
  });

  @override
  Future<Uint8List> getMapImage() {
    return remoteDataSource.getMapImage();
  }

  @override
  Future<List<PixelPoint>> getRoutePixels() {
    return remoteDataSource.getRoutePixels();
  }

  @override
  Stream<PixelPoint> getCarPositionStream() {
    return socketService.positionStream;
  }
}
