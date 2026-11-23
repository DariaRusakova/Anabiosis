"""FBX axis/unit calibration, independent of Unreal for regression tests."""
import itertools
import math
import re


def rotation_matrix(pitch, yaw, roll):
    sp, sy, sr = (math.sin(math.radians(a)) for a in (pitch, yaw, roll))
    cp, cy, cr = (math.cos(math.radians(a)) for a in (pitch, yaw, roll))
    # Unreal FRotator axes, expressed as column vectors.
    return ((cp*cy, sr*sp*cy-cr*sy, -cr*sp*cy-sr*sy),
            (cp*sy, sr*sp*sy+cr*cy, cy*sr-cr*sp*sy),
            (sp, -sr*cp, cr*cp))


def calibrate_bounds(actual_min, actual_max, expected_min, expected_max):
    """Require both size AND asymmetric grip origin to match (no recentering)."""
    values = list(actual_min)+list(actual_max)+list(expected_min)+list(expected_max)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite mesh bounds')
    if any(actual_max[i]-actual_min[i] <= 0 for i in range(3)):
        raise ValueError('Degenerate mesh bounds')
    corners = list(itertools.product(*zip(actual_min, actual_max)))
    best = None
    seen = set()
    for angles in itertools.product((0,90,-90,180), repeat=3):
        matrix = rotation_matrix(*angles)
        key = tuple(round(x) for row in matrix for x in row)
        if key in seen:
            continue
        seen.add(key)
        rotated = [tuple(sum(row[i]*p[i] for i in range(3)) for row in matrix) for p in corners]
        low = [min(p[i] for p in rotated) for i in range(3)]
        high = [max(p[i] for p in rotated) for i in range(3)]
        ratios = sorted((expected_max[i]-expected_min[i])/(high[i]-low[i]) for i in range(3))
        scale = ratios[1]
        error = max(abs(scale*p[i]-q[i]) for p,q in ((low,expected_min),(high,expected_max)) for i in range(3))
        rank = (round(error, 6), sum(abs(a) for a in angles))
        if best is None or rank < best[0]:
            best = rank, dict(rotation=list(angles), scale=scale, error_cm=error)
    if best[1]['error_cm'] > .8:
        raise ValueError(f'FBX bounds/pivot differ from prepared grip by {best[1]["error_cm"]:.2f} cm')
    return best[1]


def select_source_map(project, report):
    """Recover a successful island map even after latest_build.json is overwritten.

    A numbered .umap alone is insufficient: new_level can save an empty map
    before the builder finishes. Its SAVED log marker follows all validations.
    """
    def exists(package):
        return (isinstance(package, str) and package.startswith('/Game/') and
                '..' not in package.split('/') and
                (project / ('Content/' + package[6:] + '.umap')).is_file())
    if report.get('success') and exists(report.get('map')):
        return report['map']
    saved = {}
    pattern = r'\[ThreeIslands\]\s+SAVED\s+(/Game/LevelDesign/ThreeIslands/Build_(\d+)/L_ThreeIslands_\d+)\b'
    for log in (project / 'Saved/ThreeIslands').glob('UnrealBuild*.log'):
        for package, index in re.findall(pattern, log.read_text(encoding='utf-8', errors='replace')):
            if exists(package) and package != report.get('map'):
                saved[int(index)] = package
    if saved:
        return saved[max(saved)]
    existing = list((project / 'Content/LevelDesign/ThreeIslands').glob('Build_*/L_ThreeIslands_*.umap'))
    if existing:
        raise ValueError('Existing island maps have no successful build report/log. Rebuild the islands once; refusing to silently select NewWorld.')
    return '/Game/NewWorld'
