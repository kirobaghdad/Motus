abstract class ProfileEvent {}

class LoadProfileEvent extends ProfileEvent {}

class UpdateProfileEvent extends ProfileEvent {
  final String username;

  UpdateProfileEvent(this.username);
}

class LogoutEvent extends ProfileEvent {}
