#!/usr/bin/env python3
"""Reproducible evidence-gated HUSK-ROADMAP-v1 completion, never power savings."""
import argparse
import json
from fractions import Fraction
from pathlib import Path

WEIGHTS = dict(zip((f'M{i}' for i in range(11)), [2, 12, 10, 18, 6, 8, 7, 8, 7, 12, 10]))
TRACKS = {'I': Fraction(3, 10), 'D': Fraction(3, 10), 'E': Fraction(4, 10)}


def score(ledger):
    if ledger.get('model') != 'HUSK-ROADMAP-v1':
        raise ValueError('Unknown scoring model; explicit rebaseline required')
    rows, seen, total = [], set(), Fraction(0)
    def gates(items):
        if not items or len({g['id'] for g in items}) != len(items):
            raise ValueError('Every track needs stable unique gates')
        for g in items:
            if g['status'] not in ('passed', 'pending', 'inconclusive', 'regression'):
                raise ValueError('Unknown gate status')
            if g['status'] == 'passed' and not g.get('evidence'):
                raise ValueError('Passed gate lacks evidence')
        return Fraction(sum(g['status'] == 'passed' for g in items), len(items))
    for m in ledger['milestones']:
        key, weight = m['id'], m['weight']
        if key in seen or WEIGHTS.get(key) != weight:
            raise ValueError('Duplicate milestone or changed model weights')
        seen.add(key)
        if key == 'M0':
            fractions = {'documentation': gates(m['documentation'])}
            fraction = fractions['documentation']
        else:
            if set(m['tracks']) != set(TRACKS):
                raise ValueError('Missing implementation/device/energy track')
            fractions = {k: gates(m['tracks'][k]) for k in TRACKS}
            fraction = sum((TRACKS[k] * fractions[k] for k in TRACKS), Fraction(0))
        contribution = weight * fraction
        total += contribution
        rows.append({'id': key, 'weight': weight, 'track_percent': {k: float(v*100) for k,v in fractions.items()},
                     'milestone_percent': float(fraction*100), 'overall_contribution_points': float(contribution)})
    if seen != set(WEIGHTS) or sum(r['weight'] for r in rows) != 100:
        raise ValueError('Overall score requires all eleven milestones and 100 points')
    duo = next(r for r in rows if r['id'] == 'M10')['overall_contribution_points']
    return {'model': ledger['model'], 'gate_version': ledger['gate_version'], 'evidence_date': ledger['updated'],
            'overall_percent': float(total), 'overall_rounded_percent': int(total+Fraction(1,2)),
            'm4_scope_percent_excluding_duo': (float(total)-duo)/90*100, 'duo_milestone_percent': duo/10*100,
            'milestones': rows, 'meaning': 'Evidence-gated plan completion, not measured energy saved'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ledger', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = json.dumps(score(json.loads(a.ledger.read_text())), indent=2)
    if a.output:
        a.output.write_text(result+'\n')
    else:
        print(result)


if __name__ == '__main__':
    main()
