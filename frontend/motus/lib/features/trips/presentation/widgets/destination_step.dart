import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/booking_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/booking_event.dart';
import 'package:motus/features/trips/presentation/bloc/booking_state.dart';

class StepDestination extends StatefulWidget {
  const StepDestination({super.key});

  @override
  State<StepDestination> createState() => _StepDestinationState();
}

class _StepDestinationState extends State<StepDestination> {
  @override
  void initState() {
    super.initState();
    context.read<BookingBloc>().add(LoadLocations());
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<BookingBloc, BookingState>(
      builder: (context, state) {
        return Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "Where to?",
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),

              const SizedBox(height: 20),

              if (state.isLoading)
                const Center(child: CircularProgressIndicator()),

              if (state.error != null)
                Text(state.error!, style: const TextStyle(color: Colors.red)),

              if (!state.isLoading && state.locations.isNotEmpty)
                Expanded(
                  child: ListView.builder(
                    itemCount: state.locations.length,
                    itemBuilder: (context, index) {
                      final location = state.locations[index];

                      final isSelected = state.destination == location;

                      return Card(
                        color: isSelected ? Colors.blue.shade100 : Colors.white,
                        child: ListTile(
                          title: Text(location),
                          trailing: isSelected
                              ? const Icon(Icons.check, color: Colors.blue)
                              : null,
                          onTap: () {
                            context.read<BookingBloc>().add(
                              SelectDestination(location),
                            );
                          },
                        ),
                      );
                    },
                  ),
                ),

              const SizedBox(height: 20),

              ElevatedButton(
                onPressed: state.destination != null
                    ? () {
                        context.read<BookingBloc>().add(NextStep());
                      }
                    : null,
                child: const Text("Next"),
              ),
            ],
          ),
        );
      },
    );
  }
}
