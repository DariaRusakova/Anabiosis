"""Contracts for preserving authored textures and varied cover in the layout."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Content' / 'Python'))
from three_islands_layout import make_layout


class LayoutMaterialTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_layout()

    def test_imported_models_keep_native_or_model_specific_textures(self):
        overridden = [p['id'] for p in self.plan['pieces']
                      if p['asset'] not in ('cube', 'slab') and p['material'] not in ('original','source')]
        self.assertEqual(overridden, [], 'Imported models must not receive the shared tinted atlas')

    def test_incomplete_fbx_imports_restore_their_matching_color_maps(self):
        expected={
            'pillar':'/Game/Models/column-pillar-gameready/textures/pillar_lp_DefaultMaterial_BaseColor',
            'stairs':'/Game/Models/flying-rock/medieval-staircase/textures/Medieval_Staircase_LP__DefaultMaterial_Bas',
            'arch':'/Game/Models/Arch/Arch_BaseColor',
            'cliff':'/Game/Models/cliff-rock/textures/rock2_BC',
            'crystal':'/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_BaseColor',
            'basalt':'/Game/Models/flying-rock/rock-basalt/textures/ROCK_LOW_MESH_Material_003_BaseColor',
        }
        for asset,path in expected.items():
            with self.subTest(asset=asset):
                binding=self.plan.get('source_materials',{}).get(asset,{})
                self.assertEqual(binding.get('base_color'),path)
                pieces=[p for p in self.plan['pieces'] if p['asset']==asset]
                self.assertTrue(pieces)
                self.assertTrue(all(p['material']=='source' for p in pieces))

    def test_packed_cliff_map_preserves_ao_roughness_and_metallic_channels(self):
        cliff=self.plan.get('source_materials',{}).get('cliff',{})
        self.assertEqual(cliff.get('orm'),'/Game/Models/cliff-rock/textures/rock2_ORM')

    def test_decorative_arcade_does_not_use_full_triangle_collision(self):
        arcade=next(p for p in self.plan['pieces'] if p['asset']=='ruined_arcade')
        self.assertFalse(arcade['collision'])

    def test_prototype_floors_do_not_show_the_template_grid(self):
        floors = [p for p in self.plan['pieces'] if p['role'] in ('ground', 'bridge', 'terrace')]
        self.assertTrue(floors)
        self.assertTrue(all(p['material'] == 'floor' for p in floors))

    def test_each_island_uses_multiple_cover_meshes(self):
        for theme in ('Angel', 'Neutral', 'Demon'):
            with self.subTest(theme=theme):
                assets = {p['asset'] for p in self.plan['pieces']
                          if p['palette'] == theme and p['role'] == 'cover'
                          and p['asset'] not in ('cube', 'slab')}
                self.assertGreaterEqual(len(assets), 2, 'Cover should vary in shape and native texture')


if __name__ == '__main__':
    unittest.main()
