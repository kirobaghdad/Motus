import 'dart:async';

import 'package:motus/features/auth/domain/entities/user.dart';
import 'package:motus/features/auth/domain/usecases/login_usecase.dart';
import 'package:motus/features/auth/domain/usecases/register_usecase.dart';

import 'auth_event.dart';
import 'auth_state.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final LoginUsecase loginUsecase;
  final RegisterUsecase registerUsecase;

  AuthBloc({required this.registerUsecase, required this.loginUsecase})
    : super(AuthInit()) {
    on<LoginRequest>(_onLogin);
    on<RegisterRequest>(_onRegister);
  }

  Future<void> _onLogin(LoginRequest event, Emitter<AuthState> emit) async {
    emit(AuthLoading());
    try {
      final User user = await loginUsecase(event.email, event.password);
      emit(AuthSuccess(user));
    } catch (e) {
      emit(AuthFailure(e.toString()));
    }
  }

  FutureOr<void> _onRegister(
    RegisterRequest event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoading());

    try {
      final User user = await registerUsecase(
        event.username,
        event.email,
        event.password,
      );
      emit(AuthSuccess(user));
    } catch (e) {
      emit(AuthFailure(e.toString()));
    }
  }
}
