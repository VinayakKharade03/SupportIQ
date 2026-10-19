import 'dart:async';

import 'package:flutter/material.dart';
import 'package:record/record.dart';

void main() => runApp(const MaterialApp(home: AmpTest()));

class AmpTest extends StatefulWidget {
  const AmpTest({super.key});
  @override
  State<AmpTest> createState() => _AmpTestState();
}

class _AmpTestState extends State<AmpTest> {
  final _rec = AudioRecorder();
  Timer? _timer;
  bool _on = false;
  double _cur = -160, _min = 0, _max = -160;
  int _samples = 0;
  String _msg = 'Press Start. Stay quiet 3 s, talk 3 s, stay quiet 3 s.';
  static const _threshold = -40.0; // dB; above this counts as speech

  @override
  void dispose() {
    _timer?.cancel();
    _rec.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    try {
      if (!await _rec.hasPermission()) {
        setState(() => _msg = 'Mic permission denied.');
        return;
      }
      const cfg = RecordConfig(
          encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1);
      await _rec.start(cfg, path: '');
      setState(() {
        _on = true;
        _min = 0;
        _max = -160;
        _samples = 0;
        _msg = 'Reading amplitude every 100 ms...';
      });
      _timer = Timer.periodic(const Duration(milliseconds: 100), (_) async {
        try {
          final a = await _rec.getAmplitude();
          setState(() {
            _cur = a.current;
            if (a.current < _min) _min = a.current;
            if (a.current > _max) _max = a.current;
            _samples++;
          });
        } catch (e) {
          _timer?.cancel();
          setState(() => _msg = 'getAmplitude failed: $e');
        }
      });
    } catch (e) {
      setState(() => _msg = 'Error: $e');
    }
  }

  Future<void> _stop() async {
    _timer?.cancel();
    await _rec.stop();
    setState(() => _on = false);
  }

  @override
  Widget build(BuildContext context) {
    final speech = _cur > _threshold;
    return Scaffold(
      appBar: AppBar(title: const Text('Amplitude test')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(_msg, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            Text('Now: ${_cur.toStringAsFixed(1)} dB   '
                'min: ${_min.toStringAsFixed(1)}   '
                'max: ${_max.toStringAsFixed(1)}   '
                'samples: $_samples'),
            const SizedBox(height: 12),
            SizedBox(
              width: 300,
              child: LinearProgressIndicator(
                  value: ((_cur + 60) / 60).clamp(0.0, 1.0), minHeight: 12),
            ),
            const SizedBox(height: 12),
            Text(_on ? (speech ? 'SPEECH' : 'silence') : 'stopped',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            FilledButton(
                onPressed: _on ? _stop : _start,
                child: Text(_on ? 'Stop' : 'Start')),
          ]),
        ),
      ),
    );
  }
}
