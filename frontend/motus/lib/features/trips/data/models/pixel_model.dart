import '../../domain/entities/pixel.dart';

class PixelPointModel extends PixelPoint {
  const PixelPointModel({required super.x, required super.y});

  factory PixelPointModel.fromJson(Map<String, dynamic> json) {
    return PixelPointModel(x: json['x'].toDouble(), y: json['y'].toDouble());
  }
}
