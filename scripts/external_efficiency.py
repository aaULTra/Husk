#!/usr/bin/env python3
"""M3: align supplied external measurements with a Husk export, without inventing power.

Input is a documented normalized CSV, not an assumed Apple Instruments file format.
Raw files and their hashes remain the authority; no acceptance gate is awarded here.
"""
import argparse
import bisect
import csv
import hashlib
import io
import json
import math
from pathlib import Path

MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 500000
SCHEMA = 'HUSK-EXTERNAL-v1'


def number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be finite numeric data')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(name + ' outside supported range')
    return float(value)


def text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(name + ' requires bounded nonempty provenance')
    return value


def load_bytes(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Input exceeds 32 MiB: ' + str(path))
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Input grew beyond 32 MiB: ' + str(path))
    return raw


def read_json(raw):
    def invalid(value):
        raise ValueError('Non-finite JSON constant: ' + value)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(raw, parse_constant=invalid, object_pairs_hook=unique)


def merge(intervals):
    result = []
    for a, b in sorted(intervals):
        if b <= a:
            continue
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return result


def subtract(intervals, exclusions):
    result = list(intervals)
    for a, b in merge(exclusions):
        pieces = []
        for x, y in result:
            if y <= a or x >= b:
                pieces.append([x, y])
            else:
                if x < a:
                    pieces.append([x, a])
                if y > b:
                    pieces.append([b, y])
        result = pieces
    return result


def duration(intervals):
    return sum(b - a for a, b in intervals)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(data):
    meta = data.get('metadata', {})
    return {k: text(meta.get(k), 'metadata.' + k)
            for k in ('session_id', 'build_sha', 'device_identifier')}


def prepare(data, manifest):
    if type(data.get('schema_version')) is not int or data['schema_version'] not in range(1, 15):
        raise ValueError('Unsupported Husk schema')
    if manifest.get('schema') != SCHEMA:
        raise ValueError('Unsupported external manifest schema')
    expected = identity(data)
    if manifest.get('identity') != expected:
        raise ValueError('External session/build/device identity does not match diagnostics')
    seconds = number(data.get('duration_seconds'), 'duration_seconds', 0.000001)
    offset = number(manifest.get('clock_offset_seconds'), 'clock_offset_seconds')
    uncertainty = number(manifest.get('clock_uncertainty_seconds'), 'clock_uncertainty_seconds', 0)
    text(manifest.get('clock_alignment_method'), 'clock_alignment_method')
    gap = number(manifest.get('max_gap_seconds'), 'max_gap_seconds', 0.000001)
    conditions = manifest.get('conditions', {})
    if conditions.get('charging_state') not in ('unplugged', 'charging', 'full'):
        raise ValueError('Explicit unplugged/charging/full conditions are required')
    for k in ('route', 'cache_state', 'brightness', 'case_accessories', 'starting_temperature', 'ambient_conditions'):
        text(conditions.get(k), 'conditions.' + k)
    exclusions = []
    for row in data.get('exclusions', []):
        a = number(row.get('start'), 'exclusion.start', 0, seconds)
        b = number(row.get('end'), 'exclusion.end', a, seconds)
        exclusions.append([max(0, a - uncertainty), min(seconds, b + uncertainty)])
    # Alignment uncertainty cannot silently count data at test/exclusion boundaries.
    included = subtract([[uncertainty, seconds - uncertainty]], exclusions) if seconds > 2 * uncertainty else []
    included_starts = [a for a, b in included]
    power = manifest.get('power')
    if power is not None:
        if conditions['charging_state'] != 'unplugged':
            raise ValueError('Electrical comparison requires explicitly unplugged conditions')
        for sample in data.get('samples', []):
            at = sample.get('t')
            i = bisect.bisect_right(included_starts, at) - 1 if isinstance(at, (int, float)) else -1
            if i >= 0 and at <= included[i][1] and sample.get('battery_state') in (2, 3):
                raise ValueError('Included UIKit battery sample contradicts unplugged power provenance')
        for k in ('instrument', 'method', 'calibration_or_accuracy', 'raw_source_reference'):
            text(power.get(k), 'power.' + k)
        if power.get('units') != 'W' or power.get('quantity') != 'whole_device_system_power':
            raise ValueError('Only W of whole-device system power is supported; USB supply/CPU estimates are different quantities')
    temperature = manifest.get('temperature')
    if temperature is not None:
        for k in ('instrument', 'method', 'calibration_or_accuracy', 'raw_source_reference', 'surface_point'):
            text(temperature.get(k), 'temperature.' + k)
        if temperature.get('units') != 'degC' or temperature.get('quantity') != 'external_surface':
            raise ValueError('Temperature must be external surface degC, never guessed chip/battery temperature')
    if power is None and temperature is None:
        raise ValueError('At least one actual external measurement provenance is required')
    return expected, seconds, offset, uncertainty, gap, included


def samples(raw, offset, manifest):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    fields = reader.fieldnames or []
    required = ['t_seconds', 'power_w', 'surface_c', 'ambient_c']
    if len(set(fields)) != len(fields) or set(fields) != set(required):
        raise ValueError('CSV must have exactly t_seconds,power_w,surface_c,ambient_c columns')
    result, previous = [], -math.inf
    for index, row in enumerate(reader):
        if index >= MAX_ROWS:
            raise ValueError('Too many external samples')
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Malformed CSV row')
        values = {}
        for key, value in row.items():
            value = value.strip()
            try:
                values[key] = None if value == '' else number(float(value), key)
            except (TypeError, ValueError) as error:
                raise ValueError('Invalid external sample ' + str(index + 1) + ': ' + key) from error
        t = values['t_seconds']
        if t is None or t <= previous:
            raise ValueError('External timestamps must be strictly increasing')
        previous = t
        values['t'] = number(t + offset, 'aligned timestamp')
        if values['power_w'] is not None:
            number(values['power_w'], 'power_w', 0)
            if manifest.get('power') is None:
                raise ValueError('Power samples have no instrument provenance')
        for key in ('surface_c', 'ambient_c'):
            if values[key] is not None:
                number(values[key], key, -273.15)
                if manifest.get('temperature') is None:
                    raise ValueError('Temperature samples have no instrument provenance')
        result.append(values)
    return result


def displayed_frames(raw, manifest, included, energy_intervals, offset):
    source = manifest.get('displayed_frames')
    unavailable = {'status': 'UNAVAILABLE', 'energy_per_displayed_frame_joules': None,
                   'reason': 'No complete independently measured display-frame stream covering power intervals'}
    if raw is None:
        return unavailable
    if source is None or source.get('quantity') != 'actually_displayed_frames' or source.get('complete') is not True or source.get('dropped_records') != 0:
        raise ValueError('Display stream must explicitly declare actually displayed frames, complete coverage and zero drops')
    for key in ('instrument', 'method', 'raw_source_reference'):
        text(source.get(key), 'displayed_frames.' + key)
    cover = []
    for row in source.get('coverage_seconds', []):
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError('Invalid display coverage interval')
        a, b = number(row[0], 'display coverage start'), number(row[1], 'display coverage end')
        if b <= a:
            raise ValueError('Invalid display coverage order')
        # The same measured external clock/alignment contract applies to this file.
        u = manifest['clock_uncertainty_seconds']
        if b - a > 2 * u:
            cover.append([a + offset + u, b + offset - u])
    cover = merge(cover)
    cover_starts = [a for a, b in cover]
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if reader.fieldnames != ['t_seconds']:
        raise ValueError('Displayed-frame CSV must have only t_seconds')
    previous, times = -math.inf, []
    for index, row in enumerate(reader):
        if index >= MAX_ROWS or None in row or row.get('t_seconds') is None:
            raise ValueError('Malformed or oversized display stream')
        try:
            t = number(number(float(row['t_seconds']), 'display frame timestamp') + offset, 'aligned display timestamp')
        except (TypeError, ValueError) as error:
            raise ValueError('Invalid display frame timestamp') from error
        if t <= previous:
            raise ValueError('Displayed-frame timestamps must be strictly increasing')
        i = bisect.bisect_right(cover_starts, t + manifest['clock_uncertainty_seconds']) - 1
        if i < 0 or t > cover[i][1] + manifest['clock_uncertainty_seconds']:
            raise ValueError('Display timestamp is outside declared coverage')
        previous = t
        times.append(t)
    if not energy_intervals or duration(subtract(energy_intervals, cover)) > 1e-9:
        return unavailable
    energy_starts = [a for a, b in energy_intervals]
    def within(t):
        i = bisect.bisect_left(energy_starts, t) - 1
        return i >= 0 and t <= energy_intervals[i][1]
    count = sum(within(t) for t in times)
    if count == 0:
        return unavailable
    return {'status': 'EXTERNAL supplied display observations / ESTIMATED aligned denominator',
            'count_over_energy_intervals': count, 'endpoint_convention': '(start,end]',
            'energy_per_displayed_frame_joules': None,
            'scope': 'Only complete externally declared display coverage; no requested cap or host cadence substitution'}


def analyse(data, manifest, raw, frames_raw=None):
    ident, seconds, offset, uncertainty, max_gap, included = prepare(data, manifest)
    rows = samples(raw, offset, manifest)
    energy, power_spans, skipped_gaps = 0.0, [], 0
    included_ends = [b for a, b in included]
    included_starts = [a for a, b in included]
    for before, after in zip(rows, rows[1:]):
        a, b = before['t'], after['t']
        if b - a > max_gap:
            skipped_gaps += 1
            continue
        p, q = before['power_w'], after['power_w']
        if p is None or q is None:
            continue
        index = bisect.bisect_right(included_ends, a)
        while index < len(included) and included[index][0] < b:
            lo, hi = included[index]; index += 1
            x, y = max(a, lo), min(b, hi)
            if y <= x:
                continue
            # No extrapolation; integrate only known adjacent sample pairs.
            px, py = p + (q - p) * (x - a) / (b - a), p + (q - p) * (y - a) / (b - a)
            energy += (px + py) * 0.5 * (y - x)
            power_spans.append([x, y])
    power_spans = merge(power_spans)
    covered = duration(power_spans)
    if not math.isfinite(energy):
        raise ValueError('Power integration overflow')
    temperatures = []
    for row in rows:
        i = bisect.bisect_right(included_starts, row['t']) - 1
        if row['surface_c'] is not None and i >= 0 and row['t'] <= included[i][1]:
            temperatures.append({'t': row['t'], 'surface_c': row['surface_c'], 'ambient_c': row['ambient_c'],
                                 'surface_above_ambient_c': row['surface_c'] - row['ambient_c'] if row['ambient_c'] is not None else None})
    delta = [r['surface_above_ambient_c'] for r in temperatures if r['surface_above_ambient_c'] is not None]
    frames = displayed_frames(frames_raw, manifest, included, power_spans, offset)
    if frames.get('count_over_energy_intervals'):
        frames['energy_per_displayed_frame_joules'] = energy / frames['count_over_energy_intervals']
    return {'schema': SCHEMA, 'plan_ids': ['M1', 'M3'], 'identity': ident,
            'diagnostic_schema': data['schema_version'], 'configuration': data.get('metadata', {}).get('launch_configuration', {}),
            'conditions': manifest['conditions'], 'provenance': {k: manifest.get(k) for k in ('power', 'temperature', 'displayed_frames')},
            'alignment': {k: manifest[k] for k in ('clock_offset_seconds', 'clock_uncertainty_seconds', 'clock_alignment_method', 'max_gap_seconds')},
            'session_seconds': seconds, 'included_intervals_seconds': included,
            'included_seconds': duration(included), 'power_covered_intervals_seconds': power_spans,
            'power_covered_seconds': covered, 'power_coverage_fraction': covered / duration(included) if duration(included) else None,
            'power': {'status': 'ESTIMATED trapezoidal integration of EXTERNAL supplied power' if covered else 'UNAVAILABLE',
                      'energy_joules': energy if covered else None, 'average_watts': energy / covered if covered else None,
                      'scope': 'Whole-device system power over covered included intervals; not isolated Husk power'},
            'temperature': {'status': 'EXTERNAL supplied samples' if temperatures else 'UNAVAILABLE', 'included_samples': temperatures,
                            'max_surface_c': max((r['surface_c'] for r in temperatures), default=None),
                            'max_surface_above_ambient_c': max(delta, default=None),
                            'scope': 'Named external surface point; not internal processor/battery temperature; sampled maxima only'},
            'displayed_frames': frames, 'sample_count': len(rows), 'skipped_oversized_gaps': skipped_gaps,
            'energy_benefit': 'UNVERIFIED: a single session/calculation cannot establish comparative benefit',
            'limitations': ['Instrument accuracy, calibration, attachment and truth of supplied provenance are not verified by this parser.',
                            'Clock uncertainty trims session and expands exclusion boundaries; no extrapolation over missing/oversized gaps.',
                            'Reported average is over covered power intervals, not necessarily the complete gameplay session.',
                            'Temperature is not interpolated; matched device/build/configuration, route and conditions and repeated comparisons are required.']}


def report(result):
    p, t, f = result['power'], result['temperature'], result['displayed_frames']
    return ('# Husk external efficiency analysis\n\n'
            'Plan: M1 → M3; numerical calculation, no automatic acceptance.\n'
            f"Session/build/device: {result['identity']}\n\n"
            f"Power: {p['status']}; average {p['average_watts']} W; energy {p['energy_joules']} J.\n"
            f"Covered {result['power_covered_seconds']} / {result['included_seconds']} included seconds.\n"
            f"Temperature: {t['status']}; maximum sampled surface {t['max_surface_c']} °C; maximum above ambient {t['max_surface_above_ambient_c']} °C.\n"
            f"Displayed frames: {f['status']}; energy/frame {f['energy_per_displayed_frame_joules']} J.\n\n"
            + result['energy_benefit'] + '\n\n' + '\n'.join('- ' + x for x in result['limitations']) + '\n')


def template(data):
    return {'schema': SCHEMA, 'identity': identity(data), 'clock_offset_seconds': None,
            'clock_uncertainty_seconds': None, 'clock_alignment_method': None, 'max_gap_seconds': None,
            'conditions': {k: None for k in ('charging_state', 'route', 'cache_state', 'brightness', 'case_accessories', 'starting_temperature', 'ambient_conditions')},
            'power': {'instrument': None, 'method': None, 'calibration_or_accuracy': None,
                      'raw_source_reference': None, 'units': 'W', 'quantity': 'whole_device_system_power'},
            'temperature': {'instrument': None, 'method': None, 'calibration_or_accuracy': None,
                            'raw_source_reference': None, 'surface_point': None, 'units': 'degC', 'quantity': 'external_surface'},
            'displayed_frames': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('diagnostics', type=Path)
    parser.add_argument('--template', type=Path, help='Write an incomplete provenance template; do not invent missing measurements')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--samples', type=Path)
    parser.add_argument('--displayed-frames', type=Path)
    parser.add_argument('--output-prefix', type=Path)
    args = parser.parse_args()
    try:
        diagnostic_raw = load_bytes(args.diagnostics)
        data = read_json(diagnostic_raw)
        if args.template:
            if any((args.manifest, args.samples, args.output_prefix, args.displayed_frames)):
                raise ValueError('Template generation is separate from measurement analysis')
            if args.template.exists() or args.template.resolve() == args.diagnostics.resolve():
                raise ValueError('Template must be a new file; do not overwrite captured/filled data')
            args.template.write_text(json.dumps(template(data), indent=2, allow_nan=False) + '\n')
            return
        if not all((args.manifest, args.samples, args.output_prefix)):
            raise ValueError('Analysis requires --manifest, --samples and --output-prefix')
        inputs = [p.resolve() for p in (args.diagnostics, args.manifest, args.samples, args.displayed_frames) if p is not None]
        if any(Path(str(args.output_prefix) + suffix).resolve() in inputs for suffix in ('.json', '.md')):
            raise ValueError('Output must not overwrite input evidence')
        manifest_raw, sample_raw = load_bytes(args.manifest), load_bytes(args.samples)
        frame_raw = load_bytes(args.displayed_frames) if args.displayed_frames else None
        result = analyse(data, read_json(manifest_raw), sample_raw, frame_raw)
        result['inputs_sha256'] = {'diagnostics': digest(diagnostic_raw), 'manifest': digest(manifest_raw),
                                   'samples': digest(sample_raw), 'displayed_frames': digest(frame_raw) if frame_raw is not None else None}
        Path(str(args.output_prefix) + '.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        Path(str(args.output_prefix) + '.md').write_text(report(result))
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
