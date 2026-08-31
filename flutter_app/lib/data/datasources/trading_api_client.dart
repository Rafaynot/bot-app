import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../core/constants/api_endpoints.dart';
import '../../services/storage/app_storage_service.dart';

class TradingApiClient {
  final AppStorageService _storageService;
  final http.Client _client;

  TradingApiClient(this._storageService, [http.Client? client])
      : _client = client ?? http.Client();

  String get baseUrl {
    final saved = _storageService.getString(AppStorageKeys.baseUrl);
    return saved.isNotEmpty ? saved : ApiEndpoints.defaultBaseUrl;
  }

  Future<Map<String, dynamic>> fetchState() async {
    final url = Uri.parse('$baseUrl${ApiEndpoints.state}');
    final response = await _client.get(url).timeout(const Duration(seconds: 5));
    if (response.statusCode == 200) {
      return json.decode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    }
    throw Exception('Failed to load market state: ${response.statusCode}');
  }

  Future<List<dynamic>> fetchHistory() async {
    final url = Uri.parse('$baseUrl${ApiEndpoints.history}');
    final response = await _client.get(url).timeout(const Duration(seconds: 5));
    if (response.statusCode == 200) {
      return json.decode(utf8.decode(response.bodyBytes)) as List<dynamic>;
    }
    throw Exception('Failed to load history: ${response.statusCode}');
  }

  Future<bool> setTimeframe(String tf) async {
    final url = Uri.parse('$baseUrl${ApiEndpoints.setTimeframe}');
    final response = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'tf': tf}),
    ).timeout(const Duration(seconds: 5));
    return response.statusCode == 200;
  }

  Future<bool> setChartView(String view) async {
    final url = Uri.parse('$baseUrl${ApiEndpoints.setView}');
    final response = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'view': view}),
    ).timeout(const Duration(seconds: 5));
    return response.statusCode == 200;
  }

  Future<bool> setTradingMode(String mode) async {
    final url = Uri.parse('$baseUrl${ApiEndpoints.setMode}');
    final response = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'mode': mode}),
    ).timeout(const Duration(seconds: 5));
    return response.statusCode == 200;
  }

  Future<bool> clearStats() async {
    final url = Uri.parse('$baseUrl${ApiEndpoints.clearStats}');
    final response = await _client.post(url).timeout(const Duration(seconds: 5));
    return response.statusCode == 200;
  }

  Future<bool> updateSettings({double? minConfidence, double? maxRiskPercent}) async {
    final url = Uri.parse('$baseUrl${ApiEndpoints.updateSettings}');
    final payload = <String, dynamic>{};
    if (minConfidence != null) payload['min_confidence'] = minConfidence;
    if (maxRiskPercent != null) payload['max_risk_percent'] = maxRiskPercent;

    final response = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: json.encode(payload),
    ).timeout(const Duration(seconds: 5));
    return response.statusCode == 200;
  }
}
