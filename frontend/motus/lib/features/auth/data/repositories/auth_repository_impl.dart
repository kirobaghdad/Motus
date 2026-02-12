import "package:motus/features/auth/domain/repositories/auth_repository.dart";
import 'package:motus/features/auth/data/data_sources/auth_remote_data_source.dart';
import "package:motus/features/auth/domain/entities/user.dart";

class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource remoteDataSource;
  AuthRepositoryImpl(this.remoteDataSource);

  @override
  Future<User> login(String email, String password) async {
    final user = await remoteDataSource.login(email, password);
    return user;
  }

  @override
  Future<void> logout() {
    // TODO: implement logout
    throw UnimplementedError();
  }

  @override
  Future<User> register(String username, String email, String password) async {
    final user = await remoteDataSource.register(username, email, password);
    return user;
  }
}
