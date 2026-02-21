class BookingState {
  final bool isLoading;
  final List<String> locations;
  final String? startLocation;
  final String? destination;
  final DateTime? tripDateTime;
  final int currentStep;
  final bool bookingSuccess;
  final String? error;
  final bool isSubmitting;

  BookingState( {
    this.isLoading = false,
    this.locations = const [],
    this.startLocation,
    this.destination,
    this.tripDateTime,
    this.currentStep = 0,
    this.bookingSuccess = false,
    this.error,
    this.isSubmitting=false
  });

  BookingState copyWith({
    bool? isLoading,
    List<String>? locations,
    String? startLocation,
    String? destination,
    DateTime? tripDateTime,
    int? currentStep,
    bool? bookingSuccess,
    String? error,
    bool? isSubmitting,
  }) {
    return BookingState(
      isLoading: isLoading ?? this.isLoading,
      locations: locations ?? this.locations,
      startLocation: startLocation ?? this.startLocation,
      destination: destination ?? this.destination,
      tripDateTime: tripDateTime ?? this.tripDateTime,
      currentStep: currentStep ?? this.currentStep,
      bookingSuccess: bookingSuccess ?? this.bookingSuccess,
      error: error,
      isSubmitting:isSubmitting??this.isSubmitting,
    );
  }
}
