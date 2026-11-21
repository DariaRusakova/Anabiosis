import importlib.util
from pathlib import Path
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[3]


class ImportCalibration(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'Content/Python/elemental_weapon_import_math.py'
        spec = importlib.util.spec_from_file_location('import_math', path)
        self.math = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.math)

    def test_axis_and_unit_conversion_preserves_asymmetric_grip(self):
        # Simulate a 100x-small FBX with X forward becoming -Y and Z unchanged.
        result = self.math.calibrate_bounds([-.067,-.844,-.28], [.067,.056,.022],
                                             [-5.6,-6.7,-28], [84.4,6.7,2.2])
        self.assertAlmostEqual(result['scale'], 100, places=5)
        self.assertLess(result['error_cm'], .001)
        self.assertEqual(result['rotation'], [0,90,0])

    def test_recentered_or_malformed_import_is_rejected(self):
        with self.assertRaises(ValueError):
            self.math.calibrate_bounds([-45,-6.7,-15], [45,6.7,15],
                                       [-5.6,-6.7,-28], [84.4,6.7,2.2])
        with self.assertRaises(ValueError):
            self.math.calibrate_bounds([0,0,0], [0,1,1], [0,0,0], [1,1,1])

    def test_failed_latest_islands_attempt_keeps_previous_successful_saved_map(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in (3,4):
                path = root / f'Content/LevelDesign/ThreeIslands/Build_{index:03d}/L_ThreeIslands_{index:03d}.umap'
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'package')
            saved = '/Game/LevelDesign/ThreeIslands/Build_003/L_ThreeIslands_003'
            failed = '/Game/LevelDesign/ThreeIslands/Build_004/L_ThreeIslands_004'
            logs = root / 'Saved/ThreeIslands'
            logs.mkdir(parents=True)
            (logs/'UnrealBuild-backup.log').write_text('[ThreeIslands] SAVED '+saved+' | 950 mesh actors\n')
            self.assertEqual(self.math.select_source_map(root,{'success':False,'map':failed}),saved)

    def test_unknown_existing_islands_never_silently_fall_back_to_newworld(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(self.math.select_source_map(root,{}),'/Game/NewWorld')
            path = root / 'Content/LevelDesign/ThreeIslands/Build_001/L_ThreeIslands_001.umap'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'package')
            with self.assertRaises(ValueError):
                self.math.select_source_map(root,{'success':False})


if __name__ == '__main__':
    unittest.main()
