import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/theme/theme_provider.dart';
import '../../../domain/state/trading_state_notifier.dart';
import '../../../services/storage/app_storage_service.dart';

class DrawerMenu extends StatefulWidget {
  const DrawerMenu({super.key});

  @override
  State<DrawerMenu> createState() => _DrawerMenuState();
}

class _DrawerMenuState extends State<DrawerMenu> {
  late TextEditingController _serverController;
  double _confThreshold = 85.0;
  double _riskPercent = 1.0;
  bool _soundEnabled = true;
  bool _notifEnabled = true;

  @override
  void initState() {
    super.initState();
    final storage = context.read<AppStorageService>();
    _serverController = TextEditingController(
      text: storage.getString(AppStorageKeys.baseUrl, defaultValue: ApiEndpoints.defaultBaseUrl),
    );
    _confThreshold = storage.getDouble(AppStorageKeys.minConfidence, defaultValue: 85.0);
    _riskPercent = storage.getDouble(AppStorageKeys.maxRiskPercent, defaultValue: 1.0);
    _soundEnabled = storage.getBool(AppStorageKeys.soundAlertsEnabled, defaultValue: true);
    _notifEnabled = storage.getBool(AppStorageKeys.notificationsEnabled, defaultValue: true);
  }

  @override
  void dispose() {
    _serverController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final stateNotifier = context.watch<TradingStateNotifier>();
    final themeProvider = context.watch<ThemeProvider>();
    final storage = context.read<AppStorageService>();
    final isDark = themeProvider.isDarkMode;
    final state = stateNotifier.state;

    final cardBg = isDark ? AppColors.darkCard : AppColors.lightCard;
    final borderCol = isDark ? AppColors.darkCardBorder : AppColors.lightCardBorder;
    final textColor = isDark ? AppColors.darkTextPrimary : AppColors.lightTextPrimary;
    final textSec = isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;

    final modes = [
      {'id': 'swing', 'name': 'Swing', 'desc': 'H4/D1 Bias · M15 Entry'},
      {'id': 'intraday', 'name': 'Intraday', 'desc': 'H1 Bias · M15/M5 Entry'},
      {'id': 'scalp', 'name': 'Scalp', 'desc': 'M15/M5 · M1 Confirm'},
      {'id': 'predict', 'name': 'Predict', 'desc': 'ML AI Path Horizon'},
    ];

    return Drawer(
      backgroundColor: isDark ? AppColors.darkBg : AppColors.lightBg,
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          children: [
            // Drawer Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.goldAccentBg,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.goldAccent.withOpacity(0.3)),
                  ),
                  child: const Icon(Icons.candlestick_chart, color: AppColors.goldAccent, size: 24),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'XAUUSD Signal Desk Pro',
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: textColor),
                      ),
                      Text(
                        'v2.4.0 · Smart Money Engine',
                        style: TextStyle(fontSize: 11, color: textSec),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Trading Profile Modes
            Text('TRADING PROFILE', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: textSec, letterSpacing: 1)),
            const SizedBox(height: 8),
            ...modes.map((m) {
              final isSelected = stateNotifier.currentMode == m['id'];
              return InkWell(
                onTap: () => stateNotifier.setTradingMode(m['id']!),
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: isSelected ? AppColors.goldAccentBg : cardBg,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isSelected ? AppColors.goldAccent : borderCol,
                      width: isSelected ? 1.2 : 0.8,
                    ),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              m['name']!,
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w700,
                                color: isSelected ? AppColors.goldAccent : textColor,
                              ),
                            ),
                            Text(m['desc']!, style: TextStyle(fontSize: 10, color: textSec)),
                          ],
                        ),
                      ),
                      if (isSelected)
                        const Icon(Icons.check_circle, color: AppColors.goldAccent, size: 18),
                    ],
                  ),
                ),
              );
            }),
            const SizedBox(height: 16),

            // Server Connection URL
            Text('SERVER CONNECTION (IP:PORT)', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: textSec, letterSpacing: 1)),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: cardBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: borderCol),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _serverController,
                      style: TextStyle(fontSize: 12, color: textColor),
                      decoration: InputDecoration(
                        hintText: 'http://192.168.1.5:8000',
                        hintStyle: TextStyle(color: textSec, fontSize: 12),
                        border: InputBorder.none,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: () async {
                      final url = _serverController.text.trim();
                      await storage.setString(AppStorageKeys.baseUrl, url);
                      stateNotifier.fetchLatestState();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Server updated: $url'), duration: const Duration(seconds: 1)),
                        );
                      }
                    },
                    child: const Text('Save', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.goldAccent)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Strategy Settings
            Text('SIGNAL CONFIGURATION', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: textSec, letterSpacing: 1)),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: cardBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: borderCol),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Min Confidence', style: TextStyle(fontSize: 12, color: textColor)),
                      Text('${_confThreshold.toStringAsFixed(0)}%', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppColors.goldAccent)),
                    ],
                  ),
                  Slider(
                    value: _confThreshold,
                    min: 50,
                    max: 95,
                    divisions: 9,
                    activeColor: AppColors.goldAccent,
                    onChanged: (val) {
                      setState(() => _confThreshold = val);
                      stateNotifier.updateSettings(minConfidence: val);
                    },
                  ),
                  const Divider(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Max Risk Per Trade', style: TextStyle(fontSize: 12, color: textColor)),
                      DropdownButton<double>(
                        value: _riskPercent,
                        dropdownColor: cardBg,
                        underline: const SizedBox(),
                        items: const [
                          DropdownMenuItem(value: 0.5, child: Text('0.5% (Safe)')),
                          DropdownMenuItem(value: 1.0, child: Text('1.0% (Standard)')),
                          DropdownMenuItem(value: 1.5, child: Text('1.5% (Aggressive)')),
                          DropdownMenuItem(value: 2.0, child: Text('2.0% (High)')),
                        ],
                        onChanged: (val) {
                          if (val != null) {
                            setState(() => _riskPercent = val);
                            stateNotifier.updateSettings(maxRiskPercent: val);
                          }
                        },
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Preferences
            Text('APP PREFERENCES', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: textSec, letterSpacing: 1)),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: cardBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: borderCol),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Dark Theme', style: TextStyle(fontSize: 12, color: textColor)),
                      Switch(
                        value: isDark,
                        activeColor: AppColors.goldAccent,
                        onChanged: (val) => themeProvider.setDarkMode(val),
                      ),
                    ],
                  ),
                  const Divider(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Signal Notifications', style: TextStyle(fontSize: 12, color: textColor)),
                      Switch(
                        value: _notifEnabled,
                        activeColor: AppColors.goldAccent,
                        onChanged: (val) async {
                          setState(() => _notifEnabled = val);
                          await storage.setBool(AppStorageKeys.notificationsEnabled, val);
                        },
                      ),
                    ],
                  ),
                  const Divider(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Audio Chime Alerts', style: TextStyle(fontSize: 12, color: textColor)),
                      Switch(
                        value: _soundEnabled,
                        activeColor: AppColors.goldAccent,
                        onChanged: (val) async {
                          setState(() => _soundEnabled = val);
                          await storage.setBool(AppStorageKeys.soundAlertsEnabled, val);
                        },
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Learner Card
            if (state?.learner != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.blueAccentBg,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.blueAccent.withOpacity(0.3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: const [
                        Icon(Icons.psychology, color: AppColors.blueAccent, size: 18),
                        SizedBox(width: 6),
                        Text('AI Adaptive Learner', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppColors.blueAccent)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Optimizing neural weights dynamically based on historical signal executions.',
                      style: TextStyle(fontSize: 10, color: textColor),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}
