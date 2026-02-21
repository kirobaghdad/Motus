import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/core/di/injection_container.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_state.dart';
import 'package:motus/features/trips/presentation/widgets/confirmation_step.dart';
import 'package:motus/features/trips/presentation/widgets/date_time_step.dart';
import 'package:motus/features/trips/presentation/widgets/destination_step.dart';
import 'package:motus/features/trips/presentation/widgets/start_location_step.dart';
import 'package:motus/features/trips/presentation/widgets/step_indicator.dart';

class BookTripPage extends StatefulWidget {
  const BookTripPage({super.key});

  @override
  State<BookTripPage> createState() => _BookTripPageState();
}

class _BookTripPageState extends State<BookTripPage> {
  final PageController _controller = PageController();

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) => sl<BookingBloc>(),
      child: Scaffold(
        body: SafeArea(
          child: BlocListener<BookingBloc, BookingState>(
            listenWhen: (previous, current) =>
                previous.currentStep != current.currentStep,
            listener: (context, state) {
              _controller.animateToPage(
                state.currentStep,
                duration: const Duration(milliseconds: 300),
                curve: Curves.easeInOut,
              );
            },
            child: Column(
              children: [
                const SizedBox(height: 20),

                /// Step Indicator
                BlocBuilder<BookingBloc, BookingState>(
                  builder: (context, state) {
                    return StepIndicator(currentStep: state.currentStep);
                  },
                ),

                const SizedBox(height: 20),

                Expanded(
                  child: PageView(
                    controller: _controller,
                    physics: const NeverScrollableScrollPhysics(),
                    children: const [
                      StepStartLocation(),
                      StepDestination(),
                      StepDateTime(),
                      StepConfirmation(),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
