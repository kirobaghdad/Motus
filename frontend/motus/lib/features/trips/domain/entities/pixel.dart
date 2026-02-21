import 'package:equatable/equatable.dart';

class PixelPoint extends Equatable {
  final double x;
  final double y;

  const PixelPoint({required this.x, required this.y});

  @override
  List<Object?> get props => [x, y];
}
