import 'package:flutter/material.dart';

/// App color palette matching Binance / TradingView dark & light themes.
class AppColors {
  AppColors._();

  // Primary Dark theme background & cards
  static const Color darkBg = Color(0xFF181A20);
  static const Color darkCard = Color(0xFF1E2329);
  static const Color darkCardBorder = Color(0xFF2B313A);
  static const Color darkSurface = Color(0xFF262930);
  static const Color darkTextPrimary = Color(0xFFEAECEF);
  static const Color darkTextSecondary = Color(0xFF848E9C);

  // Light theme background & cards
  static const Color lightBg = Color(0xFFF5F7FA);
  static const Color lightCard = Color(0xFFFFFFFF);
  static const Color lightCardBorder = Color(0xFFE6E8EA);
  static const Color lightSurface = Color(0xFFECEFF2);
  static const Color lightTextPrimary = Color(0xFF1E2329);
  static const Color lightTextSecondary = Color(0xFF707A8A);

  // Trading Action Colors
  static const Color buyGreen = Color(0xFF0ECB81);
  static const Color buyGreenBg = Color(0x1A0ECB81);
  static const Color sellRed = Color(0xFFF6465D);
  static const Color sellRedBg = Color(0x1AF6465D);
  static const Color goldAccent = Color(0xFFF0B90B);
  static const Color goldAccentBg = Color(0x1AF0B90B);
  static const Color blueAccent = Color(0xFF3B82F6);
  static const Color blueAccentBg = Color(0x1A3B82F6);

  // Indicator lines
  static const Color ma7 = Color(0xFFF0B90B);  // Yellow
  static const Color ma25 = Color(0xFF3B82F6); // Blue
  static const Color ma99 = Color(0xFFEC4899); // Pink / Purple
  static const Color ema200 = Color(0xFFA855F7); // Purple
}
