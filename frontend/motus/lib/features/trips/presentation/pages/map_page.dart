import 'package:flutter/material.dart';

class CampusMapPage extends StatelessWidget {
  const CampusMapPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Text('Campus Map'),
            Expanded(
              child: InteractiveViewer(
                minScale: 1,
                maxScale: 6,
                boundaryMargin: const EdgeInsets.all(20),
                child: Image.asset('assets/map.jpg', fit: BoxFit.cover),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
