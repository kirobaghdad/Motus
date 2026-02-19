import '../../domain/entities/profile.dart';

class ProfileModel extends Profile {
  ProfileModel({required super.username, required super.email});

  factory ProfileModel.fromJson(Map<String, dynamic> json) {
    return ProfileModel(username: json['username'], email: json['email']);
  }

  Map<String, dynamic> toJson() {
    return {'username': username};
  }
}
