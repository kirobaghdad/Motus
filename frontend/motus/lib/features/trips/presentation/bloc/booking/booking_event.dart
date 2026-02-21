abstract class BookingEvent {}

class LoadLocations extends BookingEvent {}

class SelectStartLocation extends BookingEvent {
  final String startLocation;

  SelectStartLocation(this.startLocation);
}

class SelectDestination extends BookingEvent {
  final String destination;

  SelectDestination(this.destination);
}

class SelectDateTime extends BookingEvent {
  final DateTime tripDateTime;

  SelectDateTime(this.tripDateTime);
}

class NextStep extends BookingEvent {}

class PreviousStep extends BookingEvent {}

class ConfirmBooking extends BookingEvent {}
