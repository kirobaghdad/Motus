import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/features/trips/domain/usecases/book_trip_usecase.dart';
import 'package:motus/features/trips/domain/usecases/get_locations_usecase.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_event.dart';
import 'package:motus/features/trips/presentation/bloc/booking/booking_state.dart';

class BookingBloc extends Bloc<BookingEvent, BookingState> {
  final GetLocationsUsecase getLocationsUsecase;
  final BookTripUseCase bookTripUsecase;

  BookingBloc({
    required this.getLocationsUsecase,
    required this.bookTripUsecase,
  }) : super(BookingState()) {
    on<LoadLocations>(_onLoadLocations);

    on<SelectStartLocation>((event, emit) {
      emit(state.copyWith(startLocation: event.startLocation));
    });

    on<SelectDestination>((event, emit) {
      emit(state.copyWith(destination: event.destination));
    });

    on<SelectDateTime>((event, emit) {
      emit(state.copyWith(tripDateTime: event.tripDateTime));
    });

    on<NextStep>((event, emit) {
      if (_canMoveNext()) {
        emit(state.copyWith(currentStep: (state.currentStep + 1) % 4));
      }
    });

    on<PreviousStep>((event, emit) {
      if (state.currentStep > 0) {
        emit(state.copyWith(currentStep: state.currentStep - 1));
      }
    });

    on<ConfirmBooking>(_onConfirmBooking);
  }

  Future<void> _onLoadLocations(
    LoadLocations event,
    Emitter<BookingState> emit,
  ) async {
    emit(state.copyWith(isLoading: true, error: null));

    try {
      final locations = await getLocationsUsecase();

      emit(state.copyWith(isLoading: false, locations: locations));
    } catch (e) {
      emit(state.copyWith(isLoading: false, error: e.toString()));
    }
  }

  Future<void> _onConfirmBooking(
    ConfirmBooking event,
    Emitter<BookingState> emit,
  ) async {
    if (!_isFormValid()) return;

    emit(state.copyWith(isSubmitting: true, error: null));
    try {
      await bookTripUsecase(
        state.startLocation!,
        state.destination!,
        state.tripDateTime!,
      );

      emit(state.copyWith(isSubmitting: false, bookingSuccess: true));
    } catch (e) {
      emit(state.copyWith(isSubmitting: false, error: e.toString()));
    }
  }

  bool _canMoveNext() {
    if (state.currentStep == 0) {
      return state.startLocation != null;
    }
    if (state.currentStep == 1) {
      return state.destination != null;
    }
    if (state.currentStep == 2) {
      return state.tripDateTime != null;
    }
    return true;
  }

  bool _isFormValid() {
    return state.startLocation != null &&
        state.destination != null &&
        state.tripDateTime != null;
  }
}
