import 'package:flutter/material.dart';
import 'package:motus/config/routes/app_router.dart';
import 'package:motus/core/di/injection_container.dart' as di;

void main() async{
  WidgetsFlutterBinding.ensureInitialized();

  await di.init(); 
  runApp(const MyApp());
}


class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      routerConfig: AppRoutes.appRouter,
    );
  }
}
