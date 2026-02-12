import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:motus/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:motus/features/auth/presentation/bloc/auth_event.dart';
import 'package:motus/features/auth/presentation/bloc/auth_state.dart';
import 'package:motus/features/auth/presentation/widgets/app_button.dart';
import 'package:motus/features/auth/presentation/widgets/custom_text_field.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  @override
  Widget build(BuildContext context) {
    final TextEditingController emailController = TextEditingController();
    final TextEditingController passwordController = TextEditingController();
    final TextEditingController usernameController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Color.fromARGB(255, 38, 49, 200),
              Color.fromARGB(255, 45, 193, 227),
            ],
            begin: Alignment.topLeft,
            end: Alignment.topRight,
          ),
        ),
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: MediaQuery.of(context).size.height,
            ),
            child: IntrinsicHeight(
              child: Padding(
                padding: const EdgeInsets.only(top: 75),
                child: Column(
                  children: [
                    // logo
                    Container(
                      height: 150,
                      width: 150,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        image: DecorationImage(
                          image: AssetImage('assets/logo.png'),
                        ),
                      ),
                    ),

                    SizedBox(height: 20),

                    Text(
                      "Motus",
                      style: TextStyle(
                        fontSize: 45,
                        fontWeight: FontWeight.bold,
                      ),
                    ),

                    SizedBox(height: 30),

                    Expanded(
                      child: Container(
                        width: double.infinity,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: const BorderRadius.only(
                            topLeft: Radius.circular(40),
                            topRight: Radius.circular(40),
                          ),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: 40,
                            horizontal: 30,
                          ),
                          child: Form(
                            key: formKey,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                //username Filed
                                Text(
                                  "Username",
                                  style: TextStyle(fontSize: 20),
                                ),
                                CustomTextField(
                                  controller: usernameController,
                                  hintText: 'user123',
                                  obsecureText: false,
                                  validator: (value) {
                                    if (value == null || value.trim().isEmpty) {
                                      return 'Please enter your username';
                                    }
                                    return null;
                                  },
                                ),
                                SizedBox(height: 20),
                                //Email Filed
                                Text("Email", style: TextStyle(fontSize: 20)),
                                CustomTextField(
                                  controller: emailController,
                                  hintText: 'example@st-eng.edu.cu',
                                  obsecureText: false,
                                  validator: (value) {
                                    if (value == null || value.trim().isEmpty) {
                                      return 'Please enter your email';
                                    }
                                    if (!value.contains('@')) {
                                      return 'Please enter a valid email';
                                    }
                                    return null;
                                  },
                                ),
                                SizedBox(height: 20),

                                //Password Filed
                                Text(
                                  "Password",
                                  style: TextStyle(fontSize: 20),
                                ),
                                CustomTextField(
                                  controller: passwordController,
                                  hintText: '********',
                                  obsecureText: true,
                                  validator: (value) {
                                    if (value == null || value.isEmpty) {
                                      return 'Please enter your password';
                                    }
                                    if (value.length < 6) {
                                      return 'Password must be at least 6 characters';
                                    }
                                    return null;
                                  },
                                ),
                                SizedBox(height: 40),
                                BlocBuilder<AuthBloc, AuthState>(
                                  builder: (context, state) {
                                    if (state is AuthLoading) {
                                      return const Center(
                                        child: CircularProgressIndicator(),
                                      );
                                    }

                                    return AppButton(
                                      buttonText: 'Create Account',
                                      onTap: () {
                                        if (!formKey.currentState!
                                            .validate()) {
                                          context.read<AuthBloc>().add(
                                            RegisterRequest(
                                              email: emailController.text
                                                  .trim(),
                                              password: passwordController.text
                                                  .trim(),
                                              username: usernameController.text
                                                  .trim(),
                                            ),
                                          );
                                        }
                                      },
                                    );
                                  },
                                ),

                                SizedBox(height: 10),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      "Already have an account?",
                                      style: TextStyle(fontSize: 20),
                                    ),
                                    GestureDetector(
                                      onTap: () {
                                        context.go("/");
                                      },
                                      child: Text(
                                        'Sign In',
                                        style: TextStyle(
                                          fontSize: 20,
                                          color: Color.fromARGB(
                                            255,
                                            57,
                                            66,
                                            226,
                                          ),
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
