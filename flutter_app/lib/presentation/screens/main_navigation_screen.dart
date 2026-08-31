import 'package:flutter/material.dart';
import '../widgets/common/custom_app_bar.dart';
import '../widgets/common/drawer_menu.dart';
import '../widgets/common/sub_nav_ribbon.dart';
import '../widgets/common/actionable_banner.dart';
import '../widgets/common/app_bottom_navbar.dart';
import '../widgets/tabs/chart_tab/chart_tab_view.dart';
import '../widgets/tabs/signals_tab/signals_tab_view.dart';
import '../widgets/tabs/analysis_tab/analysis_tab_view.dart';
import '../widgets/tabs/order_book_tab/order_book_tab_view.dart';
import '../widgets/tabs/history_tab/history_tab_view.dart';

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentTabIndex = 0;

  final List<Widget> _tabs = const [
    ChartTabView(),
    SignalsTabView(),
    AnalysisTabView(),
    OrderBookTabView(),
    HistoryTabView(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(),
      drawer: const DrawerMenu(),
      body: SafeArea(
        child: Column(
          children: [
            const SubNavRibbon(),
            const ActionableBanner(),
            Expanded(
              child: IndexedStack(
                index: _currentTabIndex,
                children: _tabs,
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: AppBottomNavbar(
        currentIndex: _currentTabIndex,
        onTap: (index) => setState(() => _currentTabIndex = index),
      ),
    );
  }
}
