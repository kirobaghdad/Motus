import 'package:flutter/material.dart';
import 'package:motus/features/trips/domain/entities/pixel.dart';

class RoutePainter extends CustomPainter {
  final List<PixelPoint> route;

  RoutePainter(this.route);

  @override
  void paint(Canvas canvas, Size size) {
    if (route.isEmpty) return;

    final paint = Paint()
      ..color = Colors.blue
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke;

    final path = Path();
    path.moveTo(route.first.x, route.first.y);

    for (int i = 1; i < route.length; i++) {
      path.lineTo(route[i].x, route[i].y);
    }

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
