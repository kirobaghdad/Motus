import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:get_it/get_it.dart';
import 'package:dio/dio.dart';
import 'package:motus/core/storage/token_storage.dart';
import 'package:motus/features/auth/domain/usecases/logout_usecase.dart';
import 'package:motus/features/auth/domain/usecases/register_usecase.dart';
import 'package:motus/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:motus/features/profile/data/data_sources/profile_remote_data_source.dart';
import 'package:motus/features/profile/data/repositories/profile_repository_impl.dart';
import 'package:motus/features/profile/domain/repositories/profile_repository.dart';
import 'package:motus/features/profile/domain/usecases/get_profile_usecase.dart';
import 'package:motus/features/profile/domain/usecases/update_profile_usecase.dart';
import 'package:motus/features/profile/presentation/bloc/profile_bloc.dart';
import 'package:motus/features/trips/data/data_sources/trip_remote_data_sources.dart';
import 'package:motus/features/trips/data/repositories/trip_repository_impl.dart';
import 'package:motus/features/trips/domain/repositories/trip_repository.dart';
import 'package:motus/features/trips/domain/usecases/book_trip_usecase.dart';
import 'package:motus/features/trips/domain/usecases/get_locations_usecase.dart';
import 'package:motus/features/trips/domain/usecases/get_trips_usecase.dart';
import 'package:motus/features/trips/presentation/bloc/booking_bloc.dart';
import 'package:motus/features/trips/presentation/bloc/trips_bloc.dart';

import '../../features/auth/data/data_sources/auth_remote_data_source.dart';
import '../../features/auth/data/repositories/auth_repository_impl.dart';
import '../../features/auth/domain/repositories/auth_repository.dart';
import '../../features/auth/domain/usecases/login_usecase.dart';

final sl = GetIt.instance;

Future<void> init() async {
  sl.registerLazySingleton(() => FlutterSecureStorage());
  sl.registerLazySingleton(() => TokenStorage(sl()));

  final dio = Dio();
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await sl<TokenStorage>().getToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
    ),
  );

  sl.registerLazySingleton(() => dio);
  sl.registerLazySingleton<AuthRemoteDataSource>(
    () => AuthRemoteDataSourceImpl(sl()),
  );

  //TODO:change to real implementation
  sl.registerLazySingleton<TripRemoteDataSource>(
    () => TripsRemoteDataSourceMock(),
  );

  sl.registerLazySingleton<ProfileRemoteDataSource>(
    () => ProfileRemoteDataSourceImplMock(sl()),
  );

  sl.registerLazySingleton<AuthRepository>(() => AuthRepositoryImpl(sl()));
  sl.registerLazySingleton<TripRepository>(() => TripRepositoryImpl(sl()));
  sl.registerLazySingleton<ProfileRepository>(
    () => ProfileRepositoryImpl(sl()),
  );

  sl.registerLazySingleton(() => LoginUsecase(sl()));
  sl.registerLazySingleton(() => RegisterUsecase(authRepo: sl()));
  sl.registerLazySingleton(() => LogoutUsecase(authRepo: sl()));
  sl.registerLazySingleton(() => BookTripUseCase(sl()));
  sl.registerLazySingleton(() => GetLocationsUsecase(sl()));
  sl.registerLazySingleton(() => GetTripsUseCase(sl()));
  sl.registerLazySingleton(() => GetProfileUseCase(sl()));
  sl.registerLazySingleton(() => UpdateProfileUseCase(sl()));

  sl.registerFactory(() => AuthBloc(loginUsecase: sl(), registerUsecase: sl()));
  sl.registerFactory(
    () => BookingBloc(getLocationsUsecase: sl(), bookTripUsecase: sl()),
  );
  sl.registerFactory(() => TripsBloc(sl()));
  sl.registerFactory(() => ProfileBloc(getProfile: sl(), updateProfile: sl()));
}
