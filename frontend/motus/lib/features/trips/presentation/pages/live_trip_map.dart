import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/trip_map/trip_map_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/trip_map/trip_map_event.dart';
import 'package:motus/features/trips/presentation/bloc/trip_map/trip_map_state.dart';
import 'package:motus/features/trips/presentation/widgets/route_painter.dart';

class LiveTripMapPage extends StatefulWidget {
  const LiveTripMapPage({super.key});

  @override
  State<LiveTripMapPage> createState() => _LiveTripMapPageState();
}

class _LiveTripMapPageState extends State<LiveTripMapPage> {
  @override
  void initState() {
    super.initState();
    context.read<TripMapBloc>().add(LoadTripMap());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocBuilder<TripMapBloc, TripMapState>(
        builder: (context, state) {
          if (state is TripMapLoaded) {
            return InteractiveViewer(
              minScale: 1,
              maxScale: 4,
              child: Stack(
                children: [
                  Image.memory(state.mapImage),

                  CustomPaint(painter: RoutePainter(state.route)),

                  if (state.carPosition != null)
                    Positioned(
                      left: state.carPosition!.x,
                      top: state.carPosition!.y,
                      child: const Icon(
                        Icons.directions_car,
                        color: Colors.red,
                        size: 28,
                      ),
                    ),
                ],
              ),
            );
          }

          return const Center(child: CircularProgressIndicator());
        },
      ),
    );
  }
}
