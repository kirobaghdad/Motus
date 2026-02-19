import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/booking_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/booking_event.dart';
import 'package:motus/features/trips/presentation/bloc/booking_state.dart';

class StepDateTime extends StatelessWidget {
  const StepDateTime({super.key});

  @override
  Widget build(BuildContext context) {
    final bloc = context.read<BookingBloc>();

    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          const Text(
            "Select Date & Time",
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 20),

          // Date & Time Picker Button
          ElevatedButton(
            onPressed: () async {
              final DateTime? pickedDate = await showDatePicker(
                context: context,
                initialDate: DateTime.now(),
                firstDate: DateTime.now(),
                lastDate: DateTime(2100),
              );

              if (pickedDate != null) {
                final TimeOfDay? pickedTime = await showTimePicker(
                  // ignore: use_build_context_synchronously
                  context: context,
                  initialTime: TimeOfDay.now(),
                );

                if (pickedTime != null) {
                  final DateTime dateTime = DateTime(
                    pickedDate.year,
                    pickedDate.month,
                    pickedDate.day,
                    pickedTime.hour,
                    pickedTime.minute,
                  );

                  bloc.add(SelectDateTime(dateTime));
                }
              }
            },
            child: const Text("Pick Date and Time"),
          ),

          const SizedBox(height: 20),

          // Show selected date-time
          BlocBuilder<BookingBloc, BookingState>(
            builder: (context, state) {
              if (state.tripDateTime != null) {
                return Column(
                  children: [
                    Text(
                      "Selected: ${state.tripDateTime?.toLocal()}",
                      style: const TextStyle(fontSize: 16),
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: () {
                        context.read<BookingBloc>().add(NextStep());
                      },
                      child: const Text("Next"),
                    ),
                  ],
                );
              } else {
                return ElevatedButton(
                  onPressed: null,
                  child: const Text("Next"),
                );
              }
            },
          ),
        ],
      ),
    );
  }
}
