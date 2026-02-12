import '../entities/user.dart';
import '../repositories/auth_repository.dart';

class LoginUsecase {
  final AuthRepository authRepo;

  LoginUsecase(this.authRepo);

  Future<User> call(String email, String password) async {
    if(email.isEmpty || password.isEmpty) {
      throw Exception("Email and password cannot be empty");
    }
    if(!email.contains("@")) {
      throw Exception("Invalid email");
    }
    if(password.length < 6) {
      throw Exception("Password must be at least 6 characters");
    }
    return await authRepo.login(email, password);
  }

}
