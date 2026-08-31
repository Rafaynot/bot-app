# XAUUSD Signal Desk Pro — Flutter Mobile App

Production-grade cross-platform Flutter mobile application designed for real-time institutional Smart Money Concepts (SMC), ICT algorithms, live order book depth, high-confidence signal alerts, and multi-timeframe top-down trading analytics.

---

## 🏛️ Architecture & Folder Structure

The project follows clean modular architecture with separated layers:

```
flutter_app/
├── android/                           # Android native configuration & signed APK setup
│   ├── app/
│   │   ├── build.gradle               # Release signingConfigs & build flavors
│   │   └── src/main/AndroidManifest.xml # Permissions (INTERNET, POST_NOTIFICATIONS, VIBRATE)
│   └── key.properties.example         # Release keystore template
├── assets/
│   └── icons/                         # App & notification icons
└── lib/
    ├── main.dart                      # App entry point, DI & provider setup
    ├── core/                          # Core configs, design tokens & themes
    │   ├── constants/                 # Colors, API endpoints & typography
    │   ├── theme/                     # Light & Dark themes + ThemeProvider
    │   └── utils/                     # Formatters, sound manager
    ├── data/                          # Data sources, network client & repositories
    │   ├── datasources/               # TradingApiClient (REST hits to /api/state, /api/tf, etc.)
    │   ├── models/                    # Candle, Signal, OrderBook, MTF, ICT/SMC, History models
    │   └── repositories/              # TradingRepository
    ├── domain/                        # Domain logic & algorithms
    │   ├── algorithms/                # ConfluenceCalculator & RiskCalculator
    │   └── state/                     # TradingStateNotifier (central reactive state)
    ├── services/                      # Persistent services
    │   ├── storage/                   # AppStorageService (SharedPreferences)
    │   └── notifications/             # LocalNotificationService (flutter_local_notifications)
    └── presentation/                  # UI Components, Screens & 5-Tab System
        ├── screens/
        │   └── main_navigation_screen.dart # Master navigation controller
        └── widgets/
            ├── common/                # CustomAppBar, DrawerMenu, SubNavRibbon, ActionableBanner, AppBottomNavbar
            └── tabs/
                ├── chart_tab/         # Custom Canvas Candlestick & Depth Charts
                ├── signals_tab/       # Hero Signal card, confidence gauge, trade setup grid
                ├── analysis_tab/      # MTF Top-Down matrix & ICT/SMC radar
                ├── order_book_tab/    # Live depth ladder & bid/ask dominance
                └── history_tab/       # Win-rate statistics & track record
```

---

## 🚀 How to Run Locally

1. **Start the Python Web Server**:
   ```bash
   python web_server.py --port 8000 --source demo
   # or with MT5:
   python web_server.py --port 8000 --source mt5
   ```

2. **Install Flutter Dependencies**:
   ```bash
   cd flutter_app
   flutter pub get
   ```

3. **Run on Android Device / Emulator**:
   ```bash
   flutter run
   ```

4. **Connect Mobile App to PC Server**:
   - Open the side drawer menu in the app.
   - Enter your PC's LAN IP (e.g., `http://192.168.1.100:8000`) and tap **Save**.

---

## 📦 How to Build Signed Release APK

1. Generate a keystore (if not already created):
   ```bash
   keytool -genkey -v -keystore android/upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
   ```

2. Create `android/key.properties`:
   ```properties
   storePassword=your_keystore_password
   keyPassword=your_key_password
   keyAlias=upload
   storeFile=../upload-keystore.jks
   ```

3. Build the release APK:
   ```bash
   flutter build apk --release
   ```
   The signed APK will be output at:
   `build/app/outputs/flutter-apk/app-release.apk`
