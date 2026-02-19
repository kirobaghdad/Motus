import 'package:dio/dio.dart';
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
    final response = await dio.get('/profile');
    return ProfileModel.fromJson(response.data);
  }

  @override
  Future<ProfileModel> updateProfile(String username) async {
    final response = await dio.put('/profile', data: {'username': username});

    return ProfileModel.fromJson(response.data);
  }

  @override
  Future<void> logout() async {
    await dio.post('/logout');
  }
}

class ProfileRemoteDataSourceImplMock implements ProfileRemoteDataSource {
  final Dio dio;

  ProfileRemoteDataSourceImplMock(this.dio);

  @override
  Future<ProfileModel> getProfile() async {
    await Future.delayed(const Duration(seconds: 1));
    return ProfileModel(
      username: 'Rawan Ahmed',
      email: 'rawan.a.anber@gmail.com',
    );
  }

  @override
  Future<ProfileModel> updateProfile(String username) async {
    await Future.delayed(const Duration(seconds: 1));
    return ProfileModel(username: username, email: 'rawan.a.anber@gmail.com');
  }

  @override
  Future<void> logout() async {
    await Future.delayed(const Duration(seconds: 1));
  }
}
