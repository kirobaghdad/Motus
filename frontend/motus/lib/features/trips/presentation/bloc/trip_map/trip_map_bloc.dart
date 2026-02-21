import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/features/trips/domain/usecases/get_map_usecase.dart';
import 'package:motus/features/trips/domain/usecases/get_route_usecase.dart';
import 'package:motus/features/trips/domain/usecases/listen_car_position_usecase.dart';
import 'trip_map_event.dart';
import 'trip_map_state.dart';

class TripMapBloc extends Bloc<TripMapEvent, TripMapState> {
  final GetMapImageUsecase getMapImage;
  final GetRouteUsecase getRoute;
  final ListenCarPositionUsecase listenCarPosition;

  TripMapBloc({
    required this.getMapImage,
    required this.getRoute,
    required this.listenCarPosition,
  }) : super(TripMapInitial()) {
    on<LoadTripMap>(_onLoad);
    on<CarPositionUpdated>(_onCarUpdated);
  }

  Future<void> _onLoad(LoadTripMap event, Emitter<TripMapState> emit) async {
    final mapImage = await getMapImage();
    final route = await getRoute();

    emit(TripMapLoaded(mapImage: mapImage, route: route));

    listenCarPosition().listen((position) {
      add(CarPositionUpdated(position));
    });
  }

  void _onCarUpdated(CarPositionUpdated event, Emitter<TripMapState> emit) {
    if (state is TripMapLoaded) {
      final current = state as TripMapLoaded;
      emit(current.copyWith(carPosition: event.position));
    }
  }
}
