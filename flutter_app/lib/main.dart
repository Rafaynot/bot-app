import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_provider.dart';
import 'data/datasources/trading_api_client.dart';
import 'data/repositories/trading_repository.dart';
import 'domain/state/trading_state_notifier.dart';
import 'services/storage/app_storage_service.dart';
import 'services/notifications/local_notification_service.dart';
import 'presentation/screens/main_navigation_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Local Persistent Storage
  final storageService = await AppStorageService.init();

  // Initialize Local Notifications API
  final notificationService = LocalNotificationService();
  await notificationService.init();

  // Initialize API client & repository
  final apiClient = TradingApiClient(storageService);
  final tradingRepository = TradingRepository(apiClient);

  runApp(
    MultiProvider(
      providers: [
        Provider<AppStorageService>.value(value: storageService),
        Provider<LocalNotificationService>.value(value: notificationService),
        ChangeNotifierProvider<ThemeProvider>(
          create: (_) => ThemeProvider(storageService),
        ),
        ChangeNotifierProvider<TradingStateNotifier>(
          create: (_) => TradingStateNotifier(
            tradingRepository,
            storageService,
            notificationService,
          ),
        ),
      ],
      child: const XAUUSDTradingApp(),
    ),
  );
}

class XAUUSDTradingApp extends StatelessWidget {
  const XAUUSDTradingApp({super.key});

  @override
  Widget build(BuildContext context) {
    final themeProvider = context.watch<ThemeProvider>();

    return MaterialApp(
      title: 'XAUUSD Signal Desk Pro',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeProvider.themeMode,
      home: const MainNavigationScreen(),
    );
  }
}
