import 'package:dio/dio.dart';
import 'package:motus/core/constants/constants.dart';
import 'package:motus/features/trips/domain/entities/pixel.dart';
import '../models/pixel_model.dart';
import 'dart:async';
import 'package:flutter/services.dart';
import '../../domain/repositories/trip_map_repository.dart';

abstract class TripMapRemoteDataSource {
  Future<Uint8List> getMapImage();
  Future<List<PixelPointModel>> getRoutePixels();
}

class TripMapRemoteDataSourceImpl implements TripMapRemoteDataSource {
  final Dio dio;

  TripMapRemoteDataSourceImpl(this.dio);

  @override
  Future<Uint8List> getMapImage() async {
    final response = await dio.get(
      '$baseUrl/map',
      options: Options(responseType: ResponseType.bytes),
    );

    return response.data;
  }

  @override
  Future<List<PixelPointModel>> getRoutePixels() async {
    final response = await dio.get('$baseUrl/route');

    return (response.data as List)
        .map((e) => PixelPointModel.fromJson(e))
        .toList();
  }
}


class TripMapRepositoryMock implements TripMapRepository {
  final _controller = StreamController<PixelPoint>.broadcast();

  final List<PixelPoint> _route = [];
  int _currentIndex = 0;

  TripMapRepositoryMock() {
    _generateFakeRoute();
    _startCarSimulation();
  }

  // ----------------------------
  // 1️⃣ Fake Map Image
  // ----------------------------
  @override
  Future<Uint8List> getMapImage() async {
    // Put your campus image inside assets and load it
    final bytes = await rootBundle.load('assets/mock_map.png');
    return bytes.buffer.asUint8List();
  }

  // ----------------------------
  // 2️⃣ Fake Route
  // ----------------------------
  @override
  Future<List<PixelPoint>> getRoutePixels() async {
    return _route;
  }

  void _generateFakeRoute() {
    // simple diagonal path
    for (int i = 0; i < 200; i++) {
      _route.add(
        PixelPoint(
          x: 50 + i * 2,
          y: 100.0 + i,
        ),
      );
    }
  }

  // ----------------------------
  // 3️⃣ Fake Moving Car
  // ----------------------------
  void _startCarSimulation() {
    Timer.periodic(const Duration(milliseconds: 100), (timer) {
      if (_currentIndex >= _route.length) {
        _currentIndex = 0;
      }

      _controller.add(_route[_currentIndex]);
      _currentIndex++;
    });
  }

  @override
  Stream<PixelPoint> getCarPositionStream() {
    return _controller.stream;
  }
}

