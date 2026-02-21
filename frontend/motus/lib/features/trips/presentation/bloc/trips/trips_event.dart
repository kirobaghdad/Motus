abstract class TripsEvent {}

class LoadTrips extends TripsEvent {}

class ChangeTripTab extends TripsEvent {
  final bool isActive; // true = Active, false = Past
  ChangeTripTab(this.isActive);
}
