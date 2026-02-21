import 'dart:typed_data';
import '../entities/pixel.dart';

abstract class TripMapRepository {
  Future<Uint8List> getMapImage();
  Future<List<PixelPoint>> getRoutePixels();
  Stream<PixelPoint> getCarPositionStream();
}
