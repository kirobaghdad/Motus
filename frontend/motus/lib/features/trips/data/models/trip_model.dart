import 'package:motus/features/trips/domain/entities/trip.dart';

class TripModel extends Trip {
  TripModel({
    required super.destination,
    required super.startLocation,
    required super.tripDateTime,
    required super.id,
    required super.state,
  });

  factory TripModel.fromJson(Map<String, dynamic> json) {
    return TripModel(
      destination: json['destination'],
      startLocation: json['startLocation'],
      tripDateTime: json['tripDateTime'],
      id: json['tripDateTime'],
      state: json['tripDateTime'],
    );
  }
}
