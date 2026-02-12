import 'package:get_it/get_it.dart';
import 'package:dio/dio.dart';
import 'package:motus/features/auth/domain/usecases/register_usecase.dart';
import 'package:motus/features/auth/presentation/bloc/auth_bloc.dart';

import '../../features/auth/data/data_sources/auth_remote_data_source.dart';
import '../../features/auth/data/repositories/auth_repository_impl.dart';
import '../../features/auth/domain/repositories/auth_repository.dart';
import '../../features/auth/domain/usecases/login_usecase.dart';

final sl = GetIt.instance;

Future<void> init() async {
  sl.registerLazySingleton(() => Dio());

  sl.registerLazySingleton<AuthRemoteDataSource>(
    () => AuthRemoteDataSourceImpl(sl()),
  );

  sl.registerLazySingleton<AuthRepository>(() => AuthRepositoryImpl(sl()));

  sl.registerLazySingleton(() => LoginUsecase(sl()));
  sl.registerLazySingleton(() => RegisterUsecase(authRepo: sl()));

  sl.registerFactory(() => AuthBloc(loginUsecase: sl(), registerUsecase: sl()));
}
