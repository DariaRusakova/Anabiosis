"""Exercise the authoring code against the relevant Unreal boundary contracts.

This does not compile shaders or Blueprints; the fake engine checks the known
texture/sampler rule and simulates a compiler retaining a stale generated class.
"""
import ast
import datetime
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'Content/Python/setup_elemental_weapons.py'


class Object:
    def __init__(self):
        self.properties = {'compression_settings': 'TC_DEFAULT'}
    def set_editor_property(self, key, value):
        self.properties[key] = value
    def get_editor_property(self, key):
        if key == 'status':
            raise RuntimeError("Blueprint: Property 'Status' is protected and cannot be read")
        return self.properties[key]
    def get_path_name(self):
        return '/Game/TestBlueprint'


def enum(*names):
    return NS(**{name:name for name in names})


class EditorContracts(unittest.TestCase):
    def setUp(self):
        self.samples = []
        def expression(*args):
            result = Object()
            self.samples.append(result)
            return result
        def recompile(material):
            for sample in self.samples:
                texture = sample.properties['texture']
                compression = texture.properties['compression_settings']
                if compression == 'TC_MASKS':
                    self.assertEqual(sample.properties['sampler_type'], 'SAMPLERTYPE_MASKS',
                                     'UE mask texture compression requires a Masks sampler')
        engine = NS(
            TextureCompressionSettings=enum('TC_DEFAULT','TC_MASKS','TC_NORMALMAP'),
            MaterialSamplerType=enum('SAMPLERTYPE_NORMAL','SAMPLERTYPE_COLOR',
                                     'SAMPLERTYPE_LINEAR_COLOR','SAMPLERTYPE_MASKS'),
            MaterialProperty=enum('MP_BASE_COLOR','MP_NORMAL','MP_ROUGHNESS','MP_METALLIC','MP_AMBIENT_OCCLUSION'),
            Material=Object, MaterialFactoryNew=Object, MaterialExpressionTextureSample=Object,
            MaterialEditingLibrary=NS(create_material_expression=expression,
                                      layout_material_expressions=lambda *a:None, recompile_material=recompile),
            BlueprintStatus=enum('BS_ERROR','BS_UP_TO_DATE','BS_UP_TO_DATE_WITH_WARNINGS'),
            ElementalWeaponEditorLibrary=NS(is_blueprint_compiled=lambda bp:
                bp.properties.get('status') in ('BS_UP_TO_DATE','BS_UP_TO_DATE_WITH_WARNINGS')),
            BlueprintEditorLibrary=NS(compile_blueprint=lambda bp:None,
                                     generated_class=lambda bp:'STALE_OR_VALID_GENERATED_CLASS'))
        self.engine = engine
        tree = ast.parse(SOURCE.read_text())
        # Load actual definitions without running the authoring entry point.
        definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef,ast.ClassDef))]
        self.ns = {'unreal':engine, 'connect_property':lambda *a:None}
        exec(compile(ast.Module(body=definitions, type_ignores=[]),str(SOURCE),'exec'),self.ns)

    def test_pbr_data_maps_use_sampler_required_by_their_compression(self):
        setup = object.__new__(self.ns['WeaponSetup'])
        setup.create = lambda *a:Object()
        setup.import_file = lambda *a:Object()
        for channel in ('roughness','metallic','ao','orm'):
            self.samples.clear()
            setup.material(dict(id='test', flip_normal_green=False,
                                textures={'base_color':'color.png',channel:'data.png'}))

    def test_failed_blueprint_compile_cannot_pass_with_stale_generated_class(self):
        blueprint = Object()
        blueprint.properties['status'] = 'BS_ERROR'
        with self.assertRaisesRegex(RuntimeError,'compile|Compile'):
            self.ns['compile_checked'](blueprint)

    def test_success_and_warning_blueprints_are_accepted(self):
        for status in ('BS_UP_TO_DATE','BS_UP_TO_DATE_WITH_WARNINGS'):
            blueprint = Object()
            blueprint.properties['status'] = status
            self.assertEqual(self.ns['compile_checked'](blueprint),'STALE_OR_VALID_GENERATED_CLASS')

    def test_copied_world_is_configured_and_saved_without_switching_editor_maps(self):
        # UE's LoadLevel collects every inactive world. A live Python wrapper
        # for the duplicated world makes that transition fatal (Windows log).
        class World(Object):
            def __init__(self):
                super().__init__()
                self.settings = Object()
                self.settings.properties['default_game_mode'] = 'OriginalMode'
            def get_world_settings(self):
                return self.settings
        source, copied = World(), World()
        saved = []
        def forbid_map_change(*args):
            raise RuntimeError('World Memory Leaks: duplicated world held by FPyReferenceCollector')
        def blueprint(name):
            result = Object()
            result.generated = name
            result.properties['status'] = 'BS_UP_TO_DATE'
            return result
        player, mode = blueprint('PlayerClass'), blueprint('ModeClass')
        cdos = {'PlayerClass':Object(), 'ModeClass':Object()}
        engine = self.engine
        engine.World = World
        engine.BlueprintEditorLibrary.generated_class = lambda bp:bp.generated
        engine.BlueprintEditorLibrary.reparent_blueprint = lambda *args:None
        engine.get_default_object = lambda cls:cdos[cls]
        engine.log = lambda *args:None
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            setup = object.__new__(self.ns['WeaponSetup'])
            setup.source_map = '/Game/Original'
            setup.root = '/Game/Weapons/Elemental/Build_003'
            setup.map_path = setup.root + '/L_ElementalWeapons_003'
            original_file = root / 'Content/Original.umap'
            original_file.parent.mkdir()
            original_file.write_bytes(b'original unchanged')
            setup.source_hashes = {str(original_file):hashlib.sha256(original_file.read_bytes()).hexdigest()}
            setup.preflight = lambda:None
            setup.manifest = {'weapons':[0,1]}
            definitions = [Object(),Object()]
            setup.weapon = lambda index:definitions[index]
            setup.source_player, setup.source_game_mode = Object(),Object()
            setup.char_class = 'NativeCharacter'
            setup.created = [player,mode,*definitions]
            setup.duplicate = lambda original,name:player if 'Character' in name else mode
            setup.tools = NS(duplicate_asset=lambda *args:copied)
            map_file = root / ('Content/' + setup.map_path[6:] + '.umap')
            def save(asset, **kwargs):
                saved.append(asset)
                if asset is copied:
                    map_file.parent.mkdir(parents=True,exist_ok=True)
                    map_file.write_bytes(b'generated world')
                return True
            setup.assets = NS(make_directory=lambda *args:True,save_loaded_asset=save)
            setup.levels = NS(load_level=forbid_map_change, save_current_level=forbid_map_change)
            report = {}
            self.ns.update(PROJECT=root, REPORT=report, Path=Path, hashlib=hashlib,
                           datetime=datetime, write_report=lambda:None,
                           required_asset=lambda *args:source)
            setup.run()
            self.assertTrue(report['success'])
            self.assertEqual(copied.settings.properties['default_game_mode'],'ModeClass')
            self.assertEqual(source.settings.properties['default_game_mode'],'OriginalMode')
            self.assertEqual(original_file.read_bytes(),b'original unchanged')
            self.assertEqual(saved,[*setup.created,copied])


if __name__ == '__main__':
    unittest.main()
