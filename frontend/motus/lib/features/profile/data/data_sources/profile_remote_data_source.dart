import 'package:dio/dio.dart';
import 'package:motus/core/constants/constants.dart';
import '../models/profile_model.dart';

abstract class ProfileRemoteDataSource {
  Future<ProfileModel> getProfile();
  Future<ProfileModel> updateProfile(String username);
  Future<void> logout();
}

class ProfileRemoteDataSourceImpl implements ProfileRemoteDataSource {
  final Dio dio;

  ProfileRemoteDataSourceImpl(this.dio);

  @override
  Future<ProfileModel> getProfile() async {
    try {
      final response = await dio.get('$baseUrl/profile');
      return ProfileModel.fromJson(response.data);
    } on DioException catch (e) {
      throw Exception(e.message);
    }
  }

  @override
  Future<ProfileModel> updateProfile(String username) async {
    final response = await dio.put(
      '$baseUrl/edit/profile',
      data: {'username': username},
    );

    return ProfileModel.fromJson(response.data);
  }

  @override
  Future<void> logout() async {
    await dio.post('/logout');
  }
}