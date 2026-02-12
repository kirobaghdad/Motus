import 'package:motus/features/auth/data/models/user_model.dart';
import 'package:dio/dio.dart';
import 'package:motus/core/constants/constants.dart';

abstract class AuthRemoteDataSource {
  Future<UserModel> login(String email, String password);
  Future<UserModel> register(String username, String email, String password);
  Future<void> logout(String token);
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  final Dio dio;
  AuthRemoteDataSourceImpl(this.dio);

  @override
  Future<UserModel> login(String email, String password) async {
    try {
      final response = await dio.post(
        "$baseUrl/login",
        data: {"email": email, "password": password},
      );
      return UserModel.fromJson(response.data);
    } catch (e) {
      throw Exception("Error while login : $e");
    }
  }

  @override
  Future<UserModel> register(
    String username,
    String email,
    String password,
  ) async {
    final response = await dio.post(
      '$baseUrl/register',
      data: {"email": email, "password": password, "username": username},
    );
    return UserModel.fromJson(response.data);
  }

  @override
  Future<void> logout(String token) {
    // TODO: implement Logout
    throw UnimplementedError();
  }
}
