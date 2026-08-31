import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import '../constants/app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get darkTheme {
    final textTheme = GoogleFonts.interTextTheme(ThemeData.dark().textTheme);
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.darkBg,
      primaryColor: AppColors.goldAccent,
      cardColor: AppColors.darkCard,
      dividerColor: AppColors.darkCardBorder,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.darkBg,
        elevation: 0,
        centerTitle: false,
        systemOverlayStyle: SystemUiOverlayStyle.light,
        iconTheme: IconThemeData(color: AppColors.darkTextPrimary),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.darkCard,
        selectedItemColor: AppColors.goldAccent,
        unselectedItemColor: AppColors.darkTextSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: TextStyle(fontSize: 10, fontWeight: FontWeight.w700),
        unselectedLabelStyle: TextStyle(fontSize: 10, fontWeight: FontWeight.w500),
      ),
      textTheme: textTheme.copyWith(
        bodyLarge: textTheme.bodyLarge?.copyWith(color: AppColors.darkTextPrimary),
        bodyMedium: textTheme.bodyMedium?.copyWith(color: AppColors.darkTextPrimary),
        bodySmall: textTheme.bodySmall?.copyWith(color: AppColors.darkTextSecondary),
      ),
      colorScheme: const ColorScheme.dark(
        primary: AppColors.goldAccent,
        surface: AppColors.darkCard,
        error: AppColors.sellRed,
        onPrimary: Colors.black,
        onSurface: AppColors.darkTextPrimary,
      ),
    );
  }

  static ThemeData get lightTheme {
    final textTheme = GoogleFonts.interTextTheme(ThemeData.light().textTheme);
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppColors.lightBg,
      primaryColor: AppColors.goldAccent,
      cardColor: AppColors.lightCard,
      dividerColor: AppColors.lightCardBorder,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.lightCard,
        elevation: 0.5,
        centerTitle: false,
        systemOverlayStyle: SystemUiOverlayStyle.dark,
        iconTheme: IconThemeData(color: AppColors.lightTextPrimary),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.lightCard,
        selectedItemColor: AppColors.goldAccent,
        unselectedItemColor: AppColors.lightTextSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: TextStyle(fontSize: 10, fontWeight: FontWeight.w700),
        unselectedLabelStyle: TextStyle(fontSize: 10, fontWeight: FontWeight.w500),
      ),
      textTheme: textTheme.copyWith(
        bodyLarge: textTheme.bodyLarge?.copyWith(color: AppColors.lightTextPrimary),
        bodyMedium: textTheme.bodyMedium?.copyWith(color: AppColors.lightTextPrimary),
        bodySmall: textTheme.bodySmall?.copyWith(color: AppColors.lightTextSecondary),
      ),
      colorScheme: const ColorScheme.light(
        primary: AppColors.goldAccent,
        surface: AppColors.lightCard,
        error: AppColors.sellRed,
        onPrimary: Colors.black,
        onSurface: AppColors.lightTextPrimary,
      ),
    );
  }
}
