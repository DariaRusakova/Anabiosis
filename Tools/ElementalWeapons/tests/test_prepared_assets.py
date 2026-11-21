from pathlib import Path
import hashlib
import json
import unittest

PROJECT = Path(__file__).resolve().parents[3]


class PreparedWeaponAssets(unittest.TestCase):
    def test_models_have_realistic_dimensions_and_forward_muzzles(self):
        manifest=PROJECT/'Tools/ElementalWeapons/weapons.json'
        self.assertTrue(manifest.is_file(), 'The two source models must be prepared before setup')
        data=json.loads(manifest.read_text())
        for weapon,length in zip(data['weapons'],(90.0,35.0)):
            self.assertAlmostEqual(weapon['dimensions_cm'][0],length,places=3)
            self.assertGreater(weapon['muzzle_cm'][0],length*.65)
            self.assertLess(abs(weapon['muzzle_cm'][1]),length*.1)
            self.assertTrue((PROJECT/weapon['mesh_file']).is_file())
            for texture in weapon['textures'].values():
                self.assertTrue((PROJECT/texture).is_file())

    def test_source_models_are_untouched(self):
        manifest=PROJECT/'Tools/ElementalWeapons/weapons.json'
        self.assertTrue(manifest.is_file())
        data=json.loads(manifest.read_text())
        for item in data['source_files']:
            self.assertEqual(hashlib.sha256((PROJECT/item['file']).read_bytes()).hexdigest(),item['sha256'])


if __name__=='__main__':unittest.main()
