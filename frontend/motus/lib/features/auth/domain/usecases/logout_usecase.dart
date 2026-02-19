import 'package:motus/features/auth/domain/repositories/auth_repository.dart';

class LogoutUsecase {
  final AuthRepository authRepo;

  LogoutUsecase({required this.authRepo});

  Future<void> call() async {
    await authRepo.logout();
  }
}
