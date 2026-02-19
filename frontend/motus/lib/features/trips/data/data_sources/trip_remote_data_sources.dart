import 'package:motus/core/constants/constants.dart';

import '../models/trip_model.dart';
import 'package:dio/dio.dart';

abstract class TripRemoteDataSource {
  Future<List<TripModel>> getTrips();
  Future<List<String>> getLocations();
  Future<void> bookTrip(
    String destination,
    String startLocation,
    DateTime tripDateTime,
  );
  Future<TripModel> getLiveTrip();
}

class TripRemoteDataSourceImpl implements TripRemoteDataSource {
  final Dio dio;
  TripRemoteDataSourceImpl(this.dio);

  @override
  Future<List<TripModel>> getTrips() async {
    try {
      final response = await dio.get('$baseUrl/trips');

      return (response.data as List)
          .map((json) => TripModel.fromJson(json))
          .toList();
    } on DioException catch (e) {
      throw Exception(e.response?.data['message'] ?? 'Server error');
    }
  }

  @override
  Future<void> bookTrip(
    String destination,
    String startLocation,
    DateTime tripDateTime,
  ) async {
    try {
      await dio.post(
        '$baseUrl/trips/book',
        data: {
          "destination": destination,
          "startLocation": startLocation,
          "tripDateTime": tripDateTime,
        },
      );
    } on DioException catch (e) {
      throw Exception(e.response?.data['message'] ?? 'Server error');
    }
  }

  @override
  Future<TripModel> getLiveTrip() async {
    final response = await dio.get('$baseUrl/trips/live');
    return TripModel.fromJson(response.data);
  }

  @override
  Future<List<String>> getLocations() async {
    try {
      final response = await dio.get('$baseUrl/locations');
      return List<String>.from(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data['message'] ?? 'Server error');
    }
  }
}

//mock data sourecs
class TripsRemoteDataSourceMock implements TripRemoteDataSource {
  @override
  Future<List<TripModel>> getTrips() async {
    await Future.delayed(const Duration(seconds: 1)); // simulate loading

    return [
      TripModel(
        id: 1,
        destination: "Zed",
        startLocation: 'Main Gate',
        tripDateTime: DateTime.now(),
        state: 'Live',
      ),
      TripModel(
        id: 2,
        destination: "El-sawy",
        startLocation: 'Main Gate',
        tripDateTime: DateTime.now(),
        state: 'Live',
      ),
    ];
  }

  @override
  Future<void> bookTrip(
    String destination,
    String startLocation,
    DateTime tripDateTime,
  ) {
    // TODO: implement bookTrip
    throw UnimplementedError();
  }

  @override
  Future<TripModel> getLiveTrip() {
    // TODO: implement getLiveTrip
    throw UnimplementedError();
  }

  @override
  Future<List<String>> getLocations() async {
    await Future.delayed(const Duration(seconds: 1));

    return ['Main Gate', 'Zed', 'El-sawy'];
  }
}
