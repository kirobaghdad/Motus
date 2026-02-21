import 'dart:typed_data';
import 'package:equatable/equatable.dart';
import '../../../domain/entities/pixel.dart';

abstract class TripMapState extends Equatable {
  @override
  List<Object?> get props => [];
}

class TripMapInitial extends TripMapState {}

class TripMapLoaded extends TripMapState {
  final Uint8List mapImage;
  final List<PixelPoint> route;
  final PixelPoint? carPosition;

  TripMapLoaded({
    required this.mapImage,
    required this.route,
    this.carPosition,
  });

  TripMapLoaded copyWith({PixelPoint? carPosition}) {
    return TripMapLoaded(
      mapImage: mapImage,
      route: route,
      carPosition: carPosition ?? this.carPosition,
    );
  }

  @override
  List<Object?> get props => [mapImage, route, carPosition];
}
