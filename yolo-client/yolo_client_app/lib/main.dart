import 'dart:async';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:image/image.dart' as img;
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:flutter/foundation.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final cameras = await availableCameras();
  final firstCamera = cameras[0];

  runApp(MyApp(camera: firstCamera));
}

class MyApp extends StatelessWidget {
  final CameraDescription camera;

  const MyApp({Key? key, required this.camera}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: CameraStreamPage(camera: camera),
      debugShowCheckedModeBanner: false,
    );
  }
}

class CameraStreamPage extends StatefulWidget {
  final CameraDescription camera;

  const CameraStreamPage({Key? key, required this.camera}) : super(key: key);

  @override
  State<CameraStreamPage> createState() => _CameraStreamPageState();
}

class _CameraStreamPageState extends State<CameraStreamPage> {
  late CameraController _controller;
  late Future<void> _initializeControllerFuture;
  WebSocketChannel? channel;

  Uint8List? processedImage; // Detected frame from server
  bool sendingFrame = false; // Control sending to prevent overlap
  bool connected = true;
  double lastLatency = 0.0; // in milliseconds
  int frameIntervalMs = 100; // Default: send 10 FPS

  void _initWebSocket() {
    try {
      channel = WebSocketChannel.connect(
        Uri.parse("ws://10.77.203.143:8080/ws"),
      );
      print("Socket connecting...");
      connected = true;
      channel!.stream.listen(
        (message) {
          print(
            "Received message from server!..............................................................",
          );
          print(message);
          final receiveTime = DateTime.now().millisecondsSinceEpoch;
          // setState(() {
          //   processedImage = message as Uint8List?;
          // });
        },
        onError: (error) {
          print("❌ WebSocket error: $error");
          connected = false;
          _reconnectWebSocket();
        },
        onDone: () {
          print("❌ WebSocket closed");
          connected = false;
          _reconnectWebSocket();
        },
      );
    } catch (e) {
      print("❌ Failed to connect WebSocket: $e");
      connected = false;
      _reconnectWebSocket();
    }
  }

  void _reconnectWebSocket() async {
    print("🔄 Reconnecting in 2 seconds...");
    await Future.delayed(const Duration(seconds: 2));
    _initWebSocket();
  }

  @override
  void initState() {
    super.initState();

    // Initialize camera
    _controller = CameraController(
      widget.camera,
      ResolutionPreset.medium,
      imageFormatGroup: ImageFormatGroup.bgra8888,
    );

    _initializeControllerFuture = _controller.initialize();
    _initWebSocket();

    _initializeControllerFuture.then((_) {
      _controller.startImageStream((CameraImage image) async {
        // Limit sending frame rate
        if (!sendingFrame) {
          sendingFrame = true;
          if (connected) await sendFrame(image);
          sendingFrame = false;
        }
      });
    });
  }

  Uint8List convertBGRA8888toJPEG(CameraImage image) {
    final width = image.width;
    final height = image.height;

    // Create an image with RGBA
    final img.Image imgRGB = img.Image(
      width: width,
      height: height,
      numChannels: 4,
    );

    final plane = image.planes[0];
    final bytes = plane.bytes;
    final bytesPerRow = plane.bytesPerRow;

    for (int y = 0; y < height; y++) {
      for (int x = 0; x < width; x++) {
        final index = y * bytesPerRow + x * 4;

        // Make sure we do NOT exceed bytes length
        if (index + 3 >= bytes.length) continue;

        final b = bytes[index];
        final g = bytes[index + 1];
        final r = bytes[index + 2];
        final a = bytes[index + 3];

        imgRGB.setPixelRgba(x, y, r, g, b, a);
      }
    }

    return Uint8List.fromList(img.encodeJpg(imgRGB, quality: 50));
  }

  /// Send frame to server and measure latency
  Future<void> sendFrame(CameraImage image) async {
    final sendTime = DateTime.now().millisecondsSinceEpoch;
    Uint8List jpegBytes = convertBGRA8888toJPEG(image);
    try {
      channel!.sink.add(jpegBytes);

      // Latency will be updated when server sends back the frame
      setState(() {
        lastLatency =
            DateTime.now().millisecondsSinceEpoch - sendTime.toDouble();
      });
    } catch (e) {
      print("Error sending frame: $e");
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    channel?.sink.close(status.goingAway);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Self-driving Live Detection")),
      body: FutureBuilder<void>(
        future: _initializeControllerFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.done) {
            return Stack(
              children: [
                // Camera Preview
                CameraPreview(_controller),

                // Detected frame overlay
                if (processedImage != null)
                  Positioned.fill(
                    child: Opacity(
                      opacity: 0.7,
                      child: Image.memory(processedImage!, fit: BoxFit.cover),
                    ),
                  ),

                // Latency display
                Positioned(
                  top: 20,
                  left: 20,
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    color: Colors.black54,
                    child: Text(
                      "Latency: ${lastLatency.toStringAsFixed(1)} ms",
                      style: const TextStyle(color: Colors.white),
                    ),
                  ),
                ),
              ],
            );
          } else {
            return const Center(child: CircularProgressIndicator());
          }
        },
      ),
    );
  }
}
