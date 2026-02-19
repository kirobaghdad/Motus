import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:motus/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:motus/features/auth/presentation/bloc/auth_event.dart';
import 'package:motus/features/auth/presentation/widgets/app_button.dart';
import '../bloc/profile_bloc.dart';
import '../bloc/profile_event.dart';
import '../bloc/profile_state.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  @override
  void initState() {
    context.read<ProfileBloc>().add(LoadProfileEvent());
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocConsumer<ProfileBloc, ProfileState>(
        listener: (context, state) {},
        builder: (context, state) {
          if (state is ProfileLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is ProfileLoaded) {
            final profile = state.profile;

            return SingleChildScrollView(
              child: Column(
                children: [
                  Container(
                    height: 180,
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          Color.fromARGB(255, 38, 49, 200),
                          Color.fromARGB(255, 45, 193, 227),
                        ],
                      ),
                      borderRadius: BorderRadius.vertical(
                        bottom: Radius.circular(30),
                      ),
                    ),
                  ),

                  const SizedBox(height: 20),

                  CircleAvatar(
                    radius: 80,
                    backgroundColor: Colors.black,
                    child: Text(
                      profile.username.substring(0, 2).toUpperCase(),
                      style: const TextStyle(color: Colors.white, fontSize: 24),
                    ),
                  ),

                  const SizedBox(height: 10),

                  Text(profile.username, style: const TextStyle(fontSize: 20)),

                  const SizedBox(height: 30),

                  ListTile(
                    leading: const Icon(
                      Icons.person,
                      color: Color.fromARGB(255, 38, 49, 200),
                    ),
                    title: const Text("Username"),
                    subtitle: Text(profile.username),
                  ),

                  ListTile(
                    leading: const Icon(Icons.email, color: Colors.green),
                    title: const Text("Email"),
                    subtitle: Text(profile.email),
                  ),

                  const SizedBox(height: 20),

                  AppButton(buttonText: 'Edit profile', onTap: () {}),

                  const SizedBox(height: 20),

                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(15),
                      ),
                    ),
                    onPressed: () {
                      context.read<AuthBloc>().add(LogoutRequest());
                    },
                    child: Padding(
                      padding: const EdgeInsets.all(10.0),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(
                          minWidth: 200,
                          maxWidth: 240,
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Text(
                              "Log out",
                              style: TextStyle(
                                fontSize: 25,
                                color: Colors.black,
                              ),
                            ),
                            SizedBox(width: 10),
                            Icon(
                              Icons.logout,
                              size: 30,
                              color: const Color.fromARGB(255, 255, 0, 0),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          }

          return const SizedBox();
        },
      ),
    );
  }
}
