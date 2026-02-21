import 'dart:async';
import '../../domain/entities/pixel.dart';

class SocketService {
  final _controller = StreamController<PixelPoint>.broadcast();

  Stream<PixelPoint> get positionStream => _controller.stream;

  void connect() {
    // integrate your real socket here
  }

  void emitPosition(double x, double y) {
    _controller.add(PixelPoint(x: x, y: y));
  }

  void dispose() {
    _controller.close();
  }
}
