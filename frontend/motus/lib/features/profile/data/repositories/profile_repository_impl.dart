import 'package:motus/features/profile/data/data_sources/profile_remote_data_source.dart';
import '../../domain/entities/profile.dart';
import '../../domain/repositories/profile_repository.dart';

class ProfileRepositoryImpl implements ProfileRepository {
  final ProfileRemoteDataSource remoteDataSource;

  ProfileRepositoryImpl(this.remoteDataSource);

  @override
  Future<Profile> getProfile() {
    return remoteDataSource.getProfile();
  }

  @override
  Future<Profile> updateProfile(String username) {
    return remoteDataSource.updateProfile(username);
  }

  @override
  Future<void> logout() {
    return remoteDataSource.logout();
  }
}
