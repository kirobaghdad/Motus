class AuthEvent {}

class LoginRequest extends AuthEvent {
  final String email;
  final String password;

  LoginRequest({required this.email, required this.password});
}

class RegisterRequest extends AuthEvent {
  final String username;
  final String email;
  final String password;

  RegisterRequest({
    required this.username,
    required this.email,
    required this.password,
  });
}
