import 'package:motus/features/auth/domain/entities/user.dart';
import 'package:motus/features/auth/domain/repositories/auth_repository.dart';

class RegisterUsecase {
  final AuthRepository authRepo;

  RegisterUsecase({required this.authRepo});

  Future<User> call(String username, String email, String password) async {
    if (email.isEmpty || password.isEmpty || username.isEmpty) {
      throw Exception("An Empty required field");
    }
    if (!email.contains("@")) {
      throw Exception("Invalid email");
    }
    if (password.length < 6) {
      throw Exception("Password must be at least 6 characters");
    }
    return await authRepo.register(username, email, password);
  }
}
