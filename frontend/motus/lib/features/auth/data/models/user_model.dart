import 'package:motus/features/auth/domain/entities/user.dart';

class UserModel extends User {
  UserModel({
    required super.username,
    required super.email,
    required super.token,
  });
    
  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      username: json['username'],
      email: json['email'],
      token: json['token'],
    );
  }

  Map<String, dynamic> toJson(String token, String username, String email) {
    return {'username': username, 'email': email, 'token': token};
  }
}
