import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/features/trips/domain/entities/trip.dart';
import 'package:motus/features/trips/domain/usecases/get_trips_usecase.dart';
import 'package:motus/features/trips/presentation/bloc/trips_event.dart';
import 'package:motus/features/trips/presentation/bloc/trips_state.dart';

class TripsBloc extends Bloc<TripsEvent, TripsState> {
  final GetTripsUseCase getTripsUsecase;
  TripsBloc(this.getTripsUsecase) : super(TripsInitial()) {
    on<LoadTrips>(_onLoadTrips);
    on<ChangeTripTab>(_onChangeTab);
  }

  List<Trip>? _allTrips = [];
  bool _isActiveTab = true;

  Future<void> _onLoadTrips(LoadTrips event, Emitter<TripsState> emit) async {
    emit(TripsLoading());

    try {
      _allTrips = await getTripsUsecase();
      _emitLoaded(emit);
    } catch (e) {
      emit(TripsError("Failed to load trips"));
    }
  }

  void _onChangeTab(ChangeTripTab event, Emitter<TripsState> emit) {
    _isActiveTab = event.isActive;
    _emitLoaded(emit);
  }

  void _emitLoaded(Emitter<TripsState> emit) {
    final now = DateTime.now();
    List<Trip> pastTrips=[];
    List<Trip> activeTrips=[];

    if (_allTrips!=null&&_allTrips!.isNotEmpty) {
      activeTrips = _allTrips!
          .where((trip) => trip.tripDateTime.isAfter(now))
          .toList();

      pastTrips = _allTrips!
          .where((trip) => trip.tripDateTime.isBefore(now))
          .toList();
    }

    emit(
      TripsLoaded(
        activeTrips: activeTrips,
        pastTrips: pastTrips,
        isActiveTab: _isActiveTab,
      ),
    );
  }
}
