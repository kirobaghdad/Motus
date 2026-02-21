import '../entities/user.dart';
import '../repositories/auth_repository.dart';

class LoginUsecase {
  final AuthRepository authRepo;

  LoginUsecase(this.authRepo);

  Future<User> call(String username, String password) async {
    if (username.isEmpty || password.isEmpty) {
      throw Exception("username and password cannot be empty");
    }
    if (password.length < 6) {
      throw Exception("Password must be at least 6 characters");
    }
    final User user = await authRepo.login(username, password);
    return user;
  }
}
