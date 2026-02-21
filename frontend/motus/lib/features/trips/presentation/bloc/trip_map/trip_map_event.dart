import 'package:equatable/equatable.dart';
import 'package:motus/features/trips/domain/entities/pixel.dart';

abstract class TripMapEvent extends Equatable {
  @override
  List<Object?> get props => [];
}

class LoadTripMap extends TripMapEvent {}

class CarPositionUpdated extends TripMapEvent {
  final PixelPoint position;

  CarPositionUpdated(this.position);

  @override
  List<Object?> get props => [position];
}
