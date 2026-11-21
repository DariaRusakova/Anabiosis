"""UE 5.7.4 editor authoring step; execute through Setup_Elemental_Weapons.bat."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from elemental_weapon_import_math import calibrate_bounds, select_source_map
from three_islands_material_graph import connect_nodes, connect_property

PROJECT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
REPORT_DIR = PROJECT / 'Saved/ElementalWeapons'
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / 'latest_setup.json'
REPORT = dict(success=False, revision='elemental-weapons-1.0.2',
              run_id=os.environ.get('ELEMENTAL_WEAPONS_RUN_ID', ''),
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              engine_version=unreal.SystemLibrary.get_engine_version(), weapons=[])


def write_report():
    REPORT_FILE.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


def required_asset(path, cls=None):
    asset = unreal.load_asset(path)
    if asset is None or (cls is not None and not isinstance(asset, cls)):
        raise RuntimeError('Missing or wrong asset type: ' + path)
    return asset


def vec(values):
    return unreal.Vector(x=values[0], y=values[1], z=values[2])


def rot(values):
    return unreal.Rotator(pitch=values[0], yaw=values[1], roll=values[2])


def xyz(value):
    return [value.x, value.y, value.z]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_checked(blueprint):
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    # UE 5.7.4 protects Blueprint.Status from Python. Inspect compiler state
    # through the native API instead of reflecting that property.
    if not unreal.ElementalWeaponEditorLibrary.is_blueprint_compiled(blueprint):
        raise RuntimeError('Blueprint compile failed: ' + blueprint.get_path_name())
    generated = unreal.BlueprintEditorLibrary.generated_class(blueprint)
    if not generated:
        raise RuntimeError('Blueprint compile produced no class: ' + blueprint.get_path_name())
    return generated


class WeaponSetup:
    def __init__(self):
        self.tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
        self.levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.created = []
        self.source_hashes = {}
        self.manifest = json.loads((PROJECT / 'Tools/ElementalWeapons/weapons.json').read_text(encoding='utf-8'))

    def preflight(self):
        if not REPORT['engine_version'].startswith('5.7.4'):
            raise RuntimeError('Use the project-associated Unreal Engine 5.7.4.')
        if self.levels.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
            raise RuntimeError('Stop PIE and save your map before setting up weapons.')
        self.char_class = unreal.load_class(None, '/Script/Anabiosis.ElementalFirstPersonCharacter')
        self.def_class = unreal.load_class(None, '/Script/Anabiosis.ElementalWeaponDefinition')
        if not self.char_class or not self.def_class:
            raise RuntimeError('Native weapon classes are absent. Build AnabiosisEditor first using the launcher.')
        library = getattr(unreal, 'ElementalWeaponEditorLibrary', None)
        if not callable(getattr(library, 'is_blueprint_compiled', None)):
            raise RuntimeError('Native Blueprint check is absent. Run Setup_Elemental_Weapons.bat to rebuild the editor module.')
        self.source_player = required_asset('/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter', unreal.Blueprint)
        self.source_game_mode = required_asset('/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode', unreal.Blueprint)
        for source in self.manifest['source_files']:
            path = PROJECT / source['file']
            if not path.is_file() or digest(path) != source['sha256']:
                raise RuntimeError('Source asset changed since model preparation: ' + str(path))
        for weapon in self.manifest['weapons']:
            for filename in [weapon['mesh_file'], *weapon['textures'].values()]:
                if not (PROJECT / filename).is_file():
                    raise RuntimeError('Missing prepared/source file: ' + filename)
            hold = required_asset(weapon['hold_pose'], unreal.AnimSequence)
            attack = required_asset(weapon['attack_pose'], unreal.AnimSequence)
            if hold.get_editor_property('skeleton') != attack.get_editor_property('skeleton'):
                raise RuntimeError('Incompatible hold/attack skeletons: ' + weapon['id'])
        previous = PROJECT / 'Saved/ThreeIslands/latest_build.json'
        try:
            previous_data = json.loads(previous.read_text(encoding='utf-8-sig')) if previous.is_file() else {}
        except (OSError, ValueError):
            previous_data = {}
        self.source_map = select_source_map(PROJECT, previous_data)
        required_asset(self.source_map, unreal.World)
        for package in (self.source_map, '/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter',
                        '/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode'):
            extension = '.umap' if package == self.source_map else '.uasset'
            path = PROJECT / ('Content/' + package.removeprefix('/Game/') + extension)
            if not path.is_file():
                raise RuntimeError('Missing original package on disk: ' + str(path))
            self.source_hashes[str(path)] = digest(path)
        index = 1
        while self.assets.does_directory_exist(f'/Game/Weapons/Elemental/Build_{index:03d}'):
            index += 1
        self.root = f'/Game/Weapons/Elemental/Build_{index:03d}'
        self.map_path = self.root + f'/L_ElementalWeapons_{index:03d}'
        REPORT.update(generated_folder=self.root, map=self.map_path, source_map=self.source_map)
        write_report()

    def create(self, name, folder, cls, factory):
        asset = self.tools.create_asset(name, self.root + '/' + folder, cls, factory)
        if not asset:
            raise RuntimeError('Cannot create asset: ' + name)
        self.created.append(asset)
        return asset

    def import_file(self, filename, folder, name, options=None):
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', str(PROJECT / filename))
        task.set_editor_property('destination_path', self.root + '/' + folder)
        task.set_editor_property('destination_name', name)
        task.set_editor_property('automated', True)
        task.set_editor_property('replace_existing', False)
        task.set_editor_property('save', False)
        if options:
            task.set_editor_property('factory', unreal.FbxFactory())
            task.set_editor_property('options', options)
        self.tools.import_asset_tasks([task])
        imported = [unreal.load_asset(p) for p in task.get_editor_property('imported_object_paths')]
        wanted = unreal.StaticMesh if options else unreal.Texture2D
        objects = [obj for obj in imported if isinstance(obj, wanted)]
        if len(objects) != 1:
            raise RuntimeError(f'Expected one {wanted.__name__} importing {filename}; got {imported}')
        self.created.extend(obj for obj in imported if obj)
        return objects[0]

    def texture(self, filename, name, channel, flip_green=False):
        texture = self.import_file(filename, 'Textures', name)
        texture.set_editor_property('srgb', channel == 'base_color')
        if channel == 'normal':
            texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
            texture.set_editor_property('flip_green_channel', flip_green)
        elif channel != 'base_color':
            texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
        return texture

    def material(self, weapon):
        material = self.create('M_' + weapon['id'], 'Materials', unreal.Material, unreal.MaterialFactoryNew())
        lib = unreal.MaterialEditingLibrary
        textures = {}
        for channel, filename in weapon['textures'].items():
            if channel == 'flame':
                continue  # Source image is a gradient, not a billboard flame sprite.
            texture = self.texture(filename, 'T_' + weapon['id'] + '_' + channel,
                                   channel, weapon['flip_normal_green'])
            sample = lib.create_material_expression(material, unreal.MaterialExpressionTextureSample)
            sample.set_editor_property('texture', texture)
            sampler = (unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if channel == 'normal' else
                       unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if channel == 'base_color' else
                       unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
            sample.set_editor_property('sampler_type', sampler)
            textures[channel] = sample
        for channel, prop in [('base_color', unreal.MaterialProperty.MP_BASE_COLOR),
                              ('normal', unreal.MaterialProperty.MP_NORMAL),
                              ('roughness', unreal.MaterialProperty.MP_ROUGHNESS),
                              ('metallic', unreal.MaterialProperty.MP_METALLIC),
                              ('ao', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)]:
            if channel in textures:
                connect_property(lib, textures[channel], '' if channel in ('base_color','normal') else 'R', prop)
        if 'orm' in textures:
            for pin, prop in [('R',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
                              ('G',unreal.MaterialProperty.MP_ROUGHNESS), ('B',unreal.MaterialProperty.MP_METALLIC)]:
                connect_property(lib, textures['orm'], pin, prop)
        lib.layout_material_expressions(material)
        lib.recompile_material(material)
        return material

    def stream_material(self, weapon):
        material = self.create('M_Stream_' + weapon['id'], 'Materials', unreal.Material, unreal.MaterialFactoryNew())
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
        material.set_editor_property('two_sided', True)
        lib = unreal.MaterialEditingLibrary
        def node(cls, **properties):
            result = lib.create_material_expression(material, cls)
            for key, value in properties.items():
                result.set_editor_property(key, value)
            return result
        color = [8,1.4,.08] if weapon['id'] == 'flamethrower' else [.03,1.5,4]
        tint = node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*color, 1))
        time = node(unreal.MaterialExpressionTime)
        sine = node(unreal.MaterialExpressionSine, period=.12)
        multiply = node(unreal.MaterialExpressionMultiply, const_b=.12)
        add = node(unreal.MaterialExpressionAdd, const_b=.8)
        emission = node(unreal.MaterialExpressionMultiply)
        opacity = node(unreal.MaterialExpressionConstant, r=.65)
        connect_nodes(lib, time, sine)
        connect_nodes(lib, sine, multiply)
        connect_nodes(lib, multiply, add)
        connect_nodes(lib, tint, emission)
        connect_nodes(lib, add, emission, 1)
        connect_property(lib, emission, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        connect_property(lib, opacity, '', unreal.MaterialProperty.MP_OPACITY)
        lib.layout_material_expressions(material)
        lib.recompile_material(material)
        return material

    def weapon(self, data):
        options = unreal.FbxImportUI()
        for key, value in dict(import_mesh=True, import_as_skeletal=False, import_animations=False,
                               import_materials=False, import_textures=False,
                               automated_import_should_detect_type=False,
                               mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():
            options.set_editor_property(key, value)
        mesh_options = options.get_editor_property('static_mesh_import_data')
        for key, value in dict(combine_meshes=True, auto_generate_collision=False,
                               transform_vertex_to_absolute=True, bake_pivot_in_vertex=False,
                               import_uniform_scale=1.0, import_translation=unreal.Vector(),
                               import_rotation=unreal.Rotator(), convert_scene=True, convert_scene_unit=True,
                               normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS).items():
            mesh_options.set_editor_property(key, value)
        mesh = self.import_file(data['mesh_file'], 'Meshes', 'SM_' + data['id'], options)
        bounds = mesh.get_bounding_box()
        calibration = calibrate_bounds(xyz(bounds.min), xyz(bounds.max), data['bounds_min_cm'], data['bounds_max_cm'])
        material = self.material(data)
        slots = mesh.get_editor_property('static_materials')
        if not slots:
            raise RuntimeError('Imported mesh has no material slots: ' + data['id'])
        for index in range(len(slots)):
            mesh.set_material(index, material)
        factory = unreal.DataAssetFactory()
        factory.set_editor_property('data_asset_class', self.def_class)
        definition = self.create('DA_' + data['id'], 'Definitions', self.def_class, factory)
        for name, value in dict(mesh=mesh, mesh_rotation=rot(calibration['rotation']),
                                mesh_scale=calibration['scale'],
                                hold_pose=required_asset(data['hold_pose']), attack_pose=required_asset(data['attack_pose']),
                                stream_material=self.stream_material(data),
                                stream_range=260.0 if data['id']=='flamethrower' else 520.0,
                                stream_width=20.0 if data['id']=='flamethrower' else 2.5,
                                aim_fov=62.0 if data['id']=='flamethrower' else 55.0).items():
            definition.set_editor_property(name, value)
        for prop, key in [('hip_location','hip_location_cm'),('aim_location','aim_location_cm'),
                          ('right_hand_offset','right_hand_cm'),('left_hand_offset','left_hand_cm'),
                          ('muzzle_offset','muzzle_cm')]:
            definition.set_editor_property(prop, vec(data[key]))
        definition.set_editor_property('hip_rotation', rot(data['hip_rotation']))
        definition.set_editor_property('aim_rotation', rot(data['aim_rotation']))
        REPORT['weapons'].append(dict(id=data['id'], mesh=mesh.get_path_name(),
                                      definition=definition.get_path_name(), calibration=calibration,
                                      material=material.get_path_name(), textures=data['textures']))
        return definition

    def duplicate(self, source, name):
        asset = self.tools.duplicate_asset(name, self.root + '/Blueprints', source)
        if not asset:
            raise RuntimeError('Cannot duplicate: ' + source.get_path_name())
        self.created.append(asset)
        return asset

    def run(self):
        self.preflight()
        self.assets.make_directory(self.root)
        definitions = [self.weapon(w) for w in self.manifest['weapons']]
        player = self.duplicate(self.source_player, 'BP_ElementalFirstPersonCharacter')
        unreal.BlueprintEditorLibrary.reparent_blueprint(player, self.char_class)
        player_class = compile_checked(player)
        player_cdo = unreal.get_default_object(player_class)
        player_cdo.set_editor_property('weapon_loadout', definitions)
        # Compile AFTER editing defaults, then verify the surviving CDO values.
        player_class = compile_checked(player)
        if list(unreal.get_default_object(player_class).get_editor_property('weapon_loadout')) != definitions:
            raise RuntimeError('Weapon loadout did not persist on the copied player.')
        mode = self.duplicate(self.source_game_mode, 'BP_ElementalGameMode')
        mode_class = compile_checked(mode)
        unreal.get_default_object(mode_class).set_editor_property('default_pawn_class', player_class)
        mode_class = compile_checked(mode)
        if unreal.get_default_object(mode_class).get_editor_property('default_pawn_class') != player_class:
            raise RuntimeError('Copied game mode did not retain the new player class.')
        # AssetTools supports world duplication; no filesystem copy or source map edits.
        world = self.tools.duplicate_asset(self.map_path.rsplit('/',1)[1], self.root,
                                          required_asset(self.source_map, unreal.World))
        if not isinstance(world, unreal.World):
            raise RuntimeError('Cannot duplicate source map: ' + self.source_map)
        # Configure the duplicated asset directly. LoadLevel would unload all
        # inactive worlds while this Python wrapper still holds the copy,
        # triggering UE's fatal World Memory Leaks check. The launcher opens
        # the saved map in a fresh editor process after this authoring run exits.
        world.get_world_settings().set_editor_property('default_game_mode', mode_class)
        # Save only generated assets, never all dirty project packages.
        for asset in self.created:
            if not self.assets.save_loaded_asset(asset, only_if_is_dirty=False):
                raise RuntimeError('Cannot save generated asset: ' + asset.get_path_name())
        if not self.assets.save_loaded_asset(world, only_if_is_dirty=False):
            raise RuntimeError('Cannot save copied map.')
        for filename, before in self.source_hashes.items():
            if digest(Path(filename)) != before:
                raise RuntimeError('Original package changed unexpectedly: ' + filename)
        map_file = PROJECT / ('Content/' + self.map_path.removeprefix('/Game/') + '.umap')
        if not map_file.is_file():
            raise RuntimeError('Saved weapon map file is absent.')
        REPORT.update(success=True, player=player.get_path_name(), game_mode=mode.get_path_name(),
                      source_packages_unchanged=True,
                      verification='Imported/saved/configured only; Windows PIE and visual grip checks still required',
                      completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write_report()
        unreal.log('[ElementalWeapons] Saved ' + self.map_path)


write_report()
try:
    WeaponSetup().run()
except Exception:
    REPORT.update(success=False, error=traceback.format_exc())
    write_report()
    unreal.log_error(REPORT['error'])
    raise
