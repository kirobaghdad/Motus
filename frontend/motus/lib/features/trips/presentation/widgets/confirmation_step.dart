import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:motus/features/auth/presentation/widgets/app_button.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_event.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_state.dart';
import 'package:motus/features/trips/presentation/widgets/trip_card.dart';

class StepConfirmation extends StatelessWidget {
  const StepConfirmation({super.key});

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
                "Confirm your trip",
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 20),

              // Trip Card
              TripCard(
                tripDateTime: state.tripDateTime,
                startLocation: state.startLocation ?? "",
                destination: state.destination ?? "",
              ),

              const Spacer(),

              //Confirm Button
              AppButton(
                buttonText: 'Confirm Trip',
                onTap: () {
                  context.read<BookingBloc>().add(ConfirmBooking());
                  context.go('/trips');
                },
              ),
            ],
          ),
        );
      },
    );
  }
}
