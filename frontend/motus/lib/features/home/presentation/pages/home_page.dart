import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:motus/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:motus/features/auth/presentation/bloc/auth_state.dart';
import 'package:motus/features/home/presentation/widgets/card_button.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final TextEditingController destinationController = TextEditingController();
  final List<String> destinations = ['Main Gate', 'Zed'];

  @override
  void dispose() {
    destinationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, state) {
          final userName = state is AuthSuccess ? state.user.username : 'Guest';

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Container(
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [
                      Color.fromARGB(255, 38, 49, 200),
                      Color.fromARGB(255, 45, 193, 227),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.topRight,
                  ),
                  borderRadius: const BorderRadius.only(
                    bottomLeft: Radius.circular(40),
                    bottomRight: Radius.circular(40),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 50, 20, 20),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Welcome back,\n$userName',
                            style: const TextStyle(
                              fontSize: 25,
                              color: Color.fromARGB(255, 255, 255, 255),
                            ),
                          ),
                          IconButton(
                            icon: const Icon(
                              Icons.person,
                              size: 35,
                              color: Colors.white,
                            ),
                            onPressed: () {
                              context.go('/profile');
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: destinationController,
                        decoration: InputDecoration(
                          filled: true,
                          fillColor: const Color.fromARGB(46, 255, 255, 255),
                          hintText: 'Where to?',
                          hintStyle: const TextStyle(color: Colors.white70),
                          contentPadding: const EdgeInsets.symmetric(
                            vertical: 12,
                            horizontal: 10,
                          ),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(15.0),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Book Trip & My Trips cards
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    CardButton(
                      icon: Icons.calendar_today,
                      label: 'Book\nTrip',
                      iconColor: const Color.fromARGB(255, 198, 15, 15),
                      onTap: () {
                        context.go('/book');
                      },
                    ),
                    CardButton(
                      icon: Icons.location_on_rounded,
                      label: 'My\nTrips',
                      iconColor: const Color.fromARGB(255, 15, 198, 15),
                      onTap: () {
                        context.go('/trips');
                      },
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // Popular Destinations
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                child: Text(
                  'Popular Destinations',
                  style: TextStyle(fontSize: 25),
                ),
              ),

              // Destinations List
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20.0),
                  child: ListView.builder(
                    itemCount: destinations.length,
                    padding: EdgeInsets.all(0),
                    itemBuilder: (context, index) {
                      return Card(
                        margin: const EdgeInsets.only(bottom: 10),
                        elevation: 3,
                        child: ListTile(
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 8,
                          ),
                          leading: const Icon(Icons.location_on),
                          title: Text(
                            destinations[index],
                            style: const TextStyle(fontSize: 18),
                          ),
                          onTap: () {
                            context.go('/book');
                          },
                        ),
                      );
                    },
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
