// Local screenshot harness (not committed): renders the Sticks screens the
// tour captures, on the demo fixtures, with real fonts loaded.
import 'dart:convert';
import 'dart:io';

import 'package:agent_sdk/sticks.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

class FixtureGateway {
  Future<dynamic> call(String cmd, Map<String, dynamic> payload) async {
    final f = File('templates/assets/demo/sticks/$cmd.json');
    dynamic v = jsonDecode(f.readAsStringSync());
    if (v is Map && v.containsKey(r'$demo_select')) {
      final sel = v[r'$demo_select'] as Map;
      final key = payload[(sel['by'] as String).split('.').last]?.toString();
      v = (sel['cases'] as Map)[key] ?? sel['default'];
    }
    return _time(v);
  }

  dynamic _time(dynamic v) {
    if (v is Map) return v.map((k, x) => MapEntry(k, _time(x)));
    if (v is List) return [for (final x in v) _time(x)];
    if (v is String && v.startsWith(r'$now_iso')) {
      final m = RegExp(r'([+-])(\d+)([dmh])').firstMatch(v);
      var t = DateTime.utc(2026, 10, 22, 10, 45);
      if (m != null) {
        final n = int.parse(m.group(2)!) * (m.group(1) == '-' ? -1 : 1);
        t = t.add(switch (m.group(3)) { 'd' => Duration(days: n), 'h' => Duration(hours: n), _ => Duration(minutes: n) });
      }
      return t.toIso8601String();
    }
    return v;
  }
}

Future<void> _font(String family, List<String> files) async {
  final l = FontLoader(family);
  var any = false;
  for (final f in files) {
    final file = File(f);
    if (!file.existsSync()) continue;
    any = true;
    l.addFont(Future.value(ByteData.view(file.readAsBytesSync().buffer)));
  }
  if (any) await l.load();
}

Future<void> _go(WidgetTester t) async {
  for (var i = 0; i < 8; i++) {
    await t.pump(const Duration(milliseconds: 300));
  }
}

void main() {
  final out = Platform.environment['SHOT_DIR'] ?? '/tmp/shots';
  const mf = '/opt/flutter/bin/cache/artifacts/material_fonts';
  setUpAll(() async {
    await _font('Roboto', ['$mf/Roboto-Regular.ttf', '$mf/Roboto-Medium.ttf', '$mf/Roboto-Bold.ttf', '$mf/Roboto-Black.ttf']);
    await _font('MaterialIcons', ['$mf/MaterialIcons-Regular.otf']);
    final home = Platform.environment['HOME'];
    await _font('packages/remixicon/Remix', ['$home/.pub-cache/hosted/pub.dev/remixicon-1.4.1/fonts/Remix.ttf']);
    await _font('packages/agent_sdk/Montserrat', [for (final w in ['Bold', 'ExtraBold', 'Black']) 'lib/assets/fonts/Montserrat-$w.ttf']);
    await _font('packages/agent_sdk/Nunito', [for (final w in ['Regular', 'SemiBold', 'Bold', 'ExtraBold']) 'lib/assets/fonts/Nunito-$w.ttf']);
  });

  for (final dark in [false, true]) {
    testWidgets('shots ${dark ? 'dark' : 'light'}', (t) async {
      t.view.physicalSize = const Size(720, 1520);
      t.view.devicePixelRatio = 2;
      addTearDown(t.view.reset);
      await t.pumpWidget(SticksApp(data: StickRepository(FixtureGateway().call), themeMode: dark ? ThemeMode.dark : ThemeMode.light));
      await _go(t);
      final sfx = dark ? '-dark' : '';
      Future<void> shot(String name) async {
        await expectLater(find.byType(MaterialApp), matchesGoldenFile('$out/$name$sfx.png'));
      }
      final nav = t.state<NavigatorState>(find.byType(Navigator).first);
      Future<void> open(String r, Object? a, String name, [Future<void> Function()? act]) async {
        nav.pushNamed(r, arguments: a);
        await _go(t);
        if (act != null) { await act(); await _go(t); }
        await shot(name);
        nav.pop();
        await _go(t);
      }
      await open('/sticks/ask', 'tumi@acme.rokct.ai', 'ask-tumi');
      await open('/sticks/ask', 'thandi@acme.rokct.ai', 'ask-thandi');
      await open('/sticks/ask', 'kabelo@acme.rokct.ai', 'ask-kabelo');
      await open('/sticks/give', 'tumi@acme.rokct.ai', 'give-tumi');
      await open('/sticks/give', 'tumi@acme.rokct.ai', 'give-typed', () async {
        await t.enterText(find.byType(TextField).first, 'Find every ICT tender in Limpopo closing this month and start the bid packs.');
      });
      await open('/sticks/lock', null, 'lock');
      await open('/sticks/setup', (null, false), 'setup');
      await open('/sticks/setup', (null, false), 'setup-filled', () async {
        await t.enterText(find.byType(TextField).first, 'Lindiwe');
        await t.tap(find.text('Woman'));
        await t.pump();
        final r = find.text('Accounts Clerk');
        await t.ensureVisible(r);
        await t.tap(r);
        await t.pump();
        final f = Platform.environment['SHOT_TOP'];
        if (f != null) await t.drag(find.byType(Scrollable).last, const Offset(0, 2000));
      });
    });
  }

  testWidgets('lock with work shown', (t) async {
    t.view.physicalSize = const Size(720, 1520);
    t.view.devicePixelRatio = 2;
    addTearDown(t.view.reset);
    await t.pumpWidget(SticksApp(data: StickRepository(FixtureGateway().call), prefs: SticksPrefs.memory(lockShowsWork: true), themeMode: ThemeMode.light));
    await _go(t);
    t.state<NavigatorState>(find.byType(Navigator).first).pushNamed('/sticks/lock');
    await _go(t);
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('$out/lock-shown.png'));
    t.state<NavigatorState>(find.byType(Navigator).first).pushNamed('/sticks/settings');
    await _go(t);
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('$out/settings.png'));
  });
}
