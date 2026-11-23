"""Run inside the Unreal 5.7 editor, or with -ExecutePythonScript=<this file>.

Creates a NEW numbered map and derived assets. Never overwrites an existing map
or edits source meshes/materials. Python is needed only for authoring the map.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from three_islands_layout import make_layout, rotate
from three_islands_material_graph import connect_nodes, connect_property

BUILDER_REVISION = 'three-islands-builder-1.1'

PROJECT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
REPORT_DIR = PROJECT / 'Saved' / 'ThreeIslands'
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / 'latest_build.json'
REPORT = dict(success=False, run_id=os.environ.get('THREE_ISLANDS_RUN_ID', ''),
              builder_revision=BUILDER_REVISION,
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              engine_version=unreal.SystemLibrary.get_engine_version(), warnings=[])


def write_report():
    REPORT_FILE.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


def log(message):
    unreal.log('[ThreeIslands] ' + str(message))


def required_asset(path, asset_class=None):
    asset = unreal.load_asset(path)
    if asset is None or (asset_class is not None and not isinstance(asset, asset_class)):
        raise RuntimeError('Missing or wrong asset type: ' + path)
    return asset


def xyz(v):
    return (v.x, v.y, v.z)


def v3(values):
    return unreal.Vector(x=values[0], y=values[1], z=values[2])


class LevelBuilder:
    def __init__(self, plan):
        self.plan = plan
        self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        self.asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.meshes, self.materials, self.placed = {}, {}, {}
        self.sources, self.textures = {}, {}
        self.stair_profile = None
        self.arch_flip = 0

    def preflight(self):
        if not REPORT['engine_version'].startswith('5.7.'):
            raise RuntimeError('This layout targets UE 5.7.x; refusing a different engine version.')
        if self.levels.is_in_play_in_editor():
            raise RuntimeError('Stop Play In Editor before running the level builder.')
        if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
            raise RuntimeError('Save your currently edited map before running this script.')
        # Resolve every source before opening a new map.
        self.sources = {k: required_asset(p, unreal.StaticMesh) for k,p in self.plan['assets'].items()}
        self.textures = {k: required_asset(p, unreal.Texture) for k,p in self.plan['textures'].items()}
        self.game_mode = unreal.load_class(None,
            '/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode.BP_FirstPersonGameMode_C')
        if self.game_mode is None:
            raise RuntimeError('The existing first-person game mode could not be loaded.')
        index = 1
        while True:
            self.root = f'/Game/LevelDesign/ThreeIslands/Build_{index:03d}'
            self.map_path = self.root + f'/L_ThreeIslands_{index:03d}'
            if not unreal.EditorAssetLibrary.does_directory_exist(self.root):
                break
            index += 1
        REPORT['map'] = self.map_path
        REPORT['generated_folder'] = self.root
        REPORT['source_meshes'] = self.plan['assets']
        REPORT['layout_revision'] = self.plan['revision']
        REPORT['layout_sha256'] = hashlib.sha256(json.dumps(self.plan, sort_keys=True).encode()).hexdigest()
        write_report()

    def create_map(self):
        unreal.EditorAssetLibrary.make_directory(self.root)
        if not self.levels.new_level(self.map_path, is_partitioned_world=False):
            raise RuntimeError('Cannot create map: ' + self.map_path)
        self.world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        settings = self.world.get_world_settings()
        settings.set_editor_property('default_game_mode', self.game_mode)
        settings.set_editor_property('kill_z', -6500.0)

    def mesh(self, key):
        if key in self.meshes:
            return self.meshes[key]
        destination = self.root + '/Meshes/SM_' + key
        copy = unreal.EditorAssetLibrary.duplicate_asset(self.plan['assets'][key], destination)
        if copy is None:
            raise RuntimeError('Cannot duplicate mesh: ' + key)
        if key not in ('crystal',):
            if key in ('cube', 'slab'):
                self.mesh_editor.remove_collisions(copy)
                if self.mesh_editor.add_simple_collisions(copy, unreal.ScriptCollisionShapeType.BOX) < 0:
                    raise RuntimeError('Cannot create floor box collision: ' + key)
            else:
                body = copy.get_editor_property('body_setup')
                if body is None or not body.get_path_name().startswith(copy.get_path_name() + ':'):
                    # Some engine versions use a dot for subobject paths.
                    if body is None or body.get_outer() != copy:
                        raise RuntimeError('Duplicated mesh does not own its BodySetup: ' + key)
                body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                body.set_editor_property('double_sided_geometry', True)
        if not unreal.EditorAssetLibrary.save_loaded_asset(copy, only_if_is_dirty=False):
            raise RuntimeError('Cannot save generated mesh: ' + key)
        self.meshes[key] = copy
        return copy

    def material(self, theme, kind):
        if kind == 'original':
            return None
        key = (theme, kind)
        if key in self.materials:
            return self.materials[key]
        REPORT['current_material'] = f'{theme}/{kind}'
        lib = unreal.MaterialEditingLibrary
        material = self.asset_tools.create_asset(f'M_{theme}_{kind}', self.root+'/Materials',
                                                unreal.Material, unreal.MaterialFactoryNew())
        if material is None:
            raise RuntimeError('Cannot create material: ' + str(key))
        material.set_editor_property('two_sided', False)

        def node(cls, **props):
            expression = lib.create_material_expression(material, cls)
            if expression is None:
                raise RuntimeError('Cannot create material expression: ' + str(cls))
            for name, value in props.items():
                expression.set_editor_property(name, value)
            return expression

        def connect(a, b, input_index=0, output=''):
            connect_nodes(lib, a, b, input_index, output)

        def property_output(expression, output, material_property):
            connect_property(lib, expression, output, material_property)

        def sample(texture, normal=False):
            # Match source compression and colour space instead of assuming all
            # imported maps use a colour sampler. Source textures remain untouched.
            compression=texture.get_editor_property('compression_settings')
            srgb=texture.get_editor_property('srgb')
            virtual=texture.get_editor_property('virtual_texture_streaming')
            if normal or compression==unreal.TextureCompressionSettings.TC_NORMALMAP:
                suffix='NORMAL'
            elif compression==unreal.TextureCompressionSettings.TC_MASKS:
                suffix='MASKS'
            elif compression==unreal.TextureCompressionSettings.TC_GRAYSCALE:
                suffix='GRAYSCALE' if srgb else 'LINEAR_GRAYSCALE'
            else:
                suffix='COLOR' if srgb else 'LINEAR_COLOR'
            sampler=getattr(unreal.MaterialSamplerType,'SAMPLERTYPE_'+('VIRTUAL_' if virtual else '')+suffix)
            return node(unreal.MaterialExpressionTextureSample,texture=texture,sampler_type=sampler)

        palette = self.plan['palettes'][theme]
        texture_kind = 'arch' if kind=='floor' else kind
        tex = sample(self.textures[texture_kind])
        if kind == 'floor':
            position = node(unreal.MaterialExpressionWorldPosition)
            mask = node(unreal.MaterialExpressionComponentMask, r=True, g=True, b=False, a=False)
            scale = node(unreal.MaterialExpressionMultiply)
            units = node(unreal.MaterialExpressionConstant, r=1.0/440.0)
            connect(position, mask)
            connect(mask, scale)
            connect(units, scale, 1)
            connect(scale, tex)
        gray = node(unreal.MaterialExpressionDesaturation)
        fraction = node(unreal.MaterialExpressionConstant, r=0.94)
        # TextureSample's first output is RGB; use the default output selector.
        connect(tex, gray)
        connect(fraction, gray, 1)
        detail = node(unreal.MaterialExpressionMultiply)
        strength = node(unreal.MaterialExpressionConstant, r=palette['detail'])
        connect(gray, detail)
        connect(strength, detail, 1)
        add = node(unreal.MaterialExpressionAdd)
        lift = node(unreal.MaterialExpressionConstant, r=palette['lift'])
        connect(detail, add)
        connect(lift, add, 1)
        tint = node(unreal.MaterialExpressionConstant3Vector,
                    constant=unreal.LinearColor(r=palette['tint'][0],g=palette['tint'][1],b=palette['tint'][2],a=1))
        result = node(unreal.MaterialExpressionMultiply)
        connect(add, result)
        connect(tint, result, 1)
        property_output(result, '', unreal.MaterialProperty.MP_BASE_COLOR)
        roughness = node(unreal.MaterialExpressionConstant, r=0.84)
        property_output(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
        if kind in ('stone', 'arch', 'stairs'):
            normal = sample(self.textures[kind+'_normal'],normal=True)
            property_output(normal, '', unreal.MaterialProperty.MP_NORMAL)
        if kind == 'crystal':
            emissive = sample(self.textures['crystal_emissive'])
            accent = palette['accent']
            color = node(unreal.MaterialExpressionConstant3Vector,
                         constant=unreal.LinearColor(r=accent[0]*1.3,g=accent[1]*1.3,b=accent[2]*1.3,a=1))
            glow = node(unreal.MaterialExpressionMultiply)
            connect(emissive, glow)
            connect(color, glow, 1)
            property_output(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        lib.recompile_material(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False):
            raise RuntimeError('Cannot save generated material: ' + str(key))
        self.materials[key] = material
        return material

    def prepare_materials(self):
        # Check every graph variant before opening a new map or placing actors.
        REPORT['stage'] = 'materials'
        write_report()
        required = sorted({(p['palette'], p['material']) for p in self.plan['pieces']
                           if p['material'] != 'original'})
        unreal.EditorAssetLibrary.make_directory(self.root + '/Materials')
        for theme, kind in required:
            self.material(theme, kind)
        REPORT['materials_prepared'] = len(required)
        REPORT.pop('current_material', None)
        write_report()

    def fit(self, actor, mesh, location, size, yaw=0, correction=(0,0,0)):
        """Normalize arbitrary source units/pivots without modifying the mesh."""
        bounds = mesh.get_bounds()
        native_size = [2*x for x in xyz(bounds.box_extent)]
        if min(native_size) <= 0.000001:
            raise RuntimeError('Degenerate mesh bounds: ' + mesh.get_path_name())
        base = unreal.Rotator(pitch=correction[0], yaw=correction[1], roll=correction[2])
        axes = [xyz(a) for a in base.get_axes()]
        corrected = [sum(abs(axes[i][j])*native_size[i] for i in range(3)) for j in range(3)]
        ratios = [size[j]/corrected[j] for j in range(3)]
        local_scale = [sum(abs(axes[i][j])*ratios[j] for j in range(3)) for i in range(3)]
        rotation = base.combine(unreal.Rotator(yaw=yaw))
        actor.set_actor_rotation(rotation, False)
        actor.set_actor_scale3d(v3(local_scale))
        actor.set_actor_location(unreal.Vector(), False, True)
        origin, extent = actor.get_actor_bounds(False)
        actor.set_actor_location(v3((location[0]-origin.x, location[1]-origin.y,
                                     location[2]-origin.z+extent.z)), False, True)

    def actor(self, mesh_key, label):
        actor = self.actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
        if actor is None:
            raise RuntimeError('Cannot spawn static mesh actor: ' + label)
        actor.set_actor_label(label)
        component = actor.static_mesh_component
        component.set_static_mesh(self.mesh(mesh_key))
        component.set_collision_profile_name('BlockAll')
        return actor

    def trace_component(self, actor, x, y, zmin, zmax):
        hit = actor.static_mesh_component.line_trace_component(
            unreal.Vector(x=x,y=y,z=zmax),unreal.Vector(x=x,y=y,z=zmin),
            trace_complex=True,show_trace=False,persistent_show_trace=False)
        return hit[0] if hit is not None else None

    def calibrate_stairs(self):
        # Measure the actual imported mesh in UE: handrail height must NOT be
        # mistaken for tread height, and FBX handedness may reverse its direction.
        probe = self.actor('stairs', 'TemporaryStairProbe')
        mesh = self.mesh('stairs')
        correction = [0,0,0]
        try:
            for attempt in range(2):
                self.fit(probe,mesh,(0,0,10000),(500,1000,1000),correction=correction)
                samples=[]
                for i in range(101):
                    y=-500+i*10
                    hit=self.trace_component(probe,0,y,9900,11500)
                    if hit is not None:
                        samples.append((y/1000,(hit.z-10000)/1000))
                if len(samples)<20:
                    raise RuntimeError('Stair triangle collision could not be traced.')
                quarter=max(1,len(samples)//4)
                if sum(z for y,z in samples[-quarter:]) > sum(z for y,z in samples[:quarter]):
                    break
                correction[1]=180
            low=min(z for y,z in samples)
            high=max(z for y,z in samples)
            first=min(y for y,z in samples if z<low+.008)
            last=max(y for y,z in samples if z>high-.008)
            if high-low<.25 or last-first<.45:
                raise RuntimeError('Unexpected stair profile; cannot fit reliable walkable steps.')
            levels=sorted(set(round(z,3) for y,z in samples))
            biggest_step=max(b-a for a,b in zip(levels,levels[1:]))
            self.stair_profile=dict(low=low,high=high,first=first,last=last,
                                    biggest_step_fraction=biggest_step,correction=correction)
            REPORT['stair_calibration']=self.stair_profile
            log('Measured actual stair profile: '+str(self.stair_profile))
        finally:
            self.actors.destroy_actor(probe)

    def calibrate_arch(self):
        # FBX's handedness can mirror the baked mesh. Locate its one lower pier
        # in UE, so the two half arches always face inward instead of sealing a door.
        probe=self.actor('arch','TemporaryArchProbe')
        try:
            self.fit(probe,self.mesh('arch'),(0,0,12000),(1000,200,1000),
                     correction=(0,90,0))
            feet=[]
            for x in range(-480,481,20):
                hit=probe.static_mesh_component.line_trace_component(
                    v3((x,-250,12150)),v3((x,250,12150)),trace_complex=True,
                    show_trace=False,persistent_show_trace=False)
                if hit is not None:feet.append(x)
            if len(feet)<3 or abs(sum(feet)/len(feet))<40:
                raise RuntimeError('Cannot identify the single support of the imported half arch.')
            self.arch_flip=180 if sum(feet)<0 else 0
            REPORT['arch_handedness_correction_degrees']=self.arch_flip
        finally:
            self.actors.destroy_actor(probe)

    def place_piece(self,p):
        actor=self.actor(p['asset'],p['id'])
        mesh=self.mesh(p['asset'])
        if p['kind']=='stairs':
            profile=self.stair_profile
            width,run,rise=p['size']
            height=rise/(profile['high']-profile['low'])
            depth=run/(profile['last']-profile['first'])
            if height*profile['biggest_step_fraction']>44:
                raise RuntimeError('A stair rise exceeds the character step limit: '+p['id'])
            offset=-(profile['first']+profile['last'])/2*depth
            dx,dy=rotate(0,offset,p['yaw'])
            location=(p['location'][0]+dx,p['location'][1]+dy,p['location'][2]-profile['low']*height)
            self.fit(actor,mesh,location,(width,depth,height),p['yaw'],profile['correction'])
        else:
            correction=list(p['correction'])
            if p['asset']=='arch':correction[1]+=self.arch_flip
            self.fit(actor,mesh,p['location'],p['size'],p['yaw'],correction)
        material=self.material(p['palette'],p['material'])
        if material is not None:
            for slot in range(actor.static_mesh_component.get_num_materials()):
                actor.static_mesh_component.set_material(slot,material)
        if not p['collision']:
            actor.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        actor.set_folder_path(f"ThreeIslands/{p['palette']}/{p['folder']}")
        actor.set_editor_property('tags',[unreal.Name('ThreeIslands'),unreal.Name(p['role']),unreal.Name(p['palette'])])
        self.placed[p['id']]=actor

    def spawn(self,cls,label,location,rotation=None,folder='00_Lighting'):
        actor=self.actors.spawn_actor_from_class(cls,v3(location),rotation or unreal.Rotator())
        if actor is None:
            raise RuntimeError('Cannot spawn actor: '+label)
        actor.set_actor_label(label)
        actor.set_folder_path('ThreeIslands/'+folder)
        return actor

    def lighting(self):
        self.spawn(unreal.SkyAtmosphere,'SkyAtmosphere',(0,0,-15000))
        sun=self.spawn(unreal.DirectionalLight,'Sun_SoftWarm',(-5000,-7000,12000),
                       unreal.Rotator(pitch=-48,yaw=-30))
        light=sun.get_component_by_class(unreal.DirectionalLightComponent)
        light.set_mobility(unreal.ComponentMobility.MOVABLE)
        light.set_editor_property('intensity',60000.0)
        light.set_editor_property('atmosphere_sun_light',True)
        light.set_editor_property('light_source_angle',3.5)
        sky=self.spawn(unreal.SkyLight,'Sky_Fill',(0,0,5000))
        component=sky.get_component_by_class(unreal.SkyLightComponent)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_editor_property('real_time_capture',True)
        component.set_editor_property('intensity',1.1)
        fog=self.spawn(unreal.ExponentialHeightFog,'CloudSea_BelowIslands',(0,0,-1700))
        component=fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
        component.set_editor_property('fog_density',0.018)
        component.set_editor_property('fog_height_falloff',0.15)
        component.set_editor_property('fog_inscattering_luminance',unreal.LinearColor(r=.52,g=.59,b=.66,a=1))
        component.set_editor_property('enable_volumetric_fog',True)
        post=self.spawn(unreal.PostProcessVolume,'Exposure_Consistent',(0,0,0))
        post.set_editor_property('unbound',True)
        settings=post.get_editor_property('settings')
        for name,value in dict(override_auto_exposure_min_brightness=True,
                               override_auto_exposure_max_brightness=True,
                               auto_exposure_min_brightness=12.0,
                               auto_exposure_max_brightness=12.0,
                               override_bloom_intensity=True,bloom_intensity=.25,
                               override_vignette_intensity=True,vignette_intensity=.2).items():
            settings.set_editor_property(name,value)
        post.set_editor_property('settings',settings)
        for island in self.plan['islands']:
            theme=island['name']
            ox,oy=island['center']
            accent=self.plan['palettes'][theme]['accent']
            for j,(x,y,z) in enumerate([(-700,2300,1050),(700,2300,1050)]):
                actor=self.spawn(unreal.PointLight,f'{theme}_Accent{j}',(ox+x,oy+y,z),
                                 folder=theme+'/00_Lighting')
                c=actor.get_component_by_class(unreal.PointLightComponent)
                c.set_mobility(unreal.ComponentMobility.MOVABLE)
                c.set_light_color(unreal.LinearColor(r=accent[0],g=accent[1],b=accent[2],a=1))
                c.set_editor_property('intensity',8500.0)
                c.set_editor_property('attenuation_radius',1700.0)
                c.set_editor_property('cast_shadows',False)

    def markers_and_cameras(self):
        for marker in self.plan['markers']:
            cls=unreal.PlayerStart if marker['kind']=='spawn' else unreal.TargetPoint
            self.spawn(cls,marker['id'],marker['location'],unreal.Rotator(yaw=marker['yaw']),
                       folder='10_Playtest')
        # Persistent review cameras, with the main viewport restored to overview.
        for name,location,target in [
                ('Overview',(14800,-22500,16500),(0,0,-400)),
                ('Angel',(-3500,-7100,4600),(-8500,400,100)),
                ('Neutral',(5000,-7100,4600),(0,400,100)),
                ('Demon',(13500,-7100,4600),(8500,400,100))]:
            rotation=unreal.MathLibrary.find_look_at_rotation(v3(location),v3(target))
            camera=self.spawn(unreal.CameraActor,'Review_'+name,location,rotation,
                              folder='11_ReviewCameras')
            camera.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',65.0)
        # Viewport APIs are optional in a command-line editor; camera actors are saved regardless.
        try:
            subsystem=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
            subsystem.set_level_viewport_camera_info(v3((14800,-22500,16500)),
                unreal.MathLibrary.find_look_at_rotation(v3((14800,-22500,16500)),v3((0,0,-400))))
        except Exception as exc:
            REPORT['warnings'].append('Viewport preview: '+str(exc))

    def check_collision(self):
        checks=[]
        # Actual UE collision traces, not a substitute for a human PIE walkthrough.
        for p in self.plan['pieces']:
            if p['role'] not in ('ground','bridge','stairs','arch'):
                continue
            actor=self.placed[p['id']]
            x,y,z=p['location']
            if p['role']=='arch':
                side=p['arch_side']
                dx,dy=rotate(side*(p['size'][0]-4)/2,0,p['yaw'])
                cx,cy=x-dx,y-dy
                for across in (-34,0,34):
                    for head in (40,96,192):
                        a,b=rotate(across,-p['size'][1]/2-50,p['yaw'])
                        c,d=rotate(across,p['size'][1]/2+50,p['yaw'])
                        hit=actor.static_mesh_component.line_trace_component(
                            v3((cx+a,cy+b,z+head)),v3((cx+c,cy+d,z+head)),
                            trace_complex=True,show_trace=False,persistent_show_trace=False)
                        if hit is not None:
                            raise RuntimeError('Arch opening is obstructed: '+p['id'])
                checks.append(p['id'])
            elif p['kind']=='stairs':
                run,rise=p['size'][1:]
                for t in (-.4,.4):
                    dx,dy=rotate(0,t*run,p['yaw'])
                    hit=self.trace_component(actor,x+dx,y+dy,z-100,z+rise+300)
                    if hit is None:
                        raise RuntimeError('Stair collision missing: '+p['id'])
                checks.append(p['id'])
            else:
                # Simple collision is what the character actually walks on.
                hit=actor.static_mesh_component.line_trace_component(v3((x,y,50)),v3((x,y,-250)),
                    trace_complex=False,show_trace=False,persistent_show_trace=False)
                expected_top=z+p['size'][2]
                if hit is None or abs(hit[0].z-expected_top)>1:
                    raise RuntimeError('Floor collision missing or not level: '+p['id'])
                checks.append(p['id'])
        REPORT['collision_trace_checks']=len(checks)
        REPORT['pie_playtest']='NOT RUN - inspect in Windows editor'

    def build(self):
        log('Builder revision: ' + BUILDER_REVISION)
        self.preflight()
        self.prepare_materials()
        REPORT['stage'] = 'geometry'
        self.create_map()
        self.calibrate_stairs()
        self.calibrate_arch()
        with unreal.ScopedSlowTask(len(self.plan['pieces']),'Building the three islands') as task:
            task.make_dialog(True)
            for p in self.plan['pieces']:
                REPORT['current_piece'] = p['id']
                if task.should_cancel():
                    raise RuntimeError('Build cancelled; original maps are untouched.')
                self.place_piece(p)
                task.enter_progress_frame(1,p['id'])
        REPORT.pop('current_piece', None)
        REPORT['stage'] = 'lighting'
        self.lighting()
        REPORT['stage'] = 'cameras'
        self.markers_and_cameras()
        REPORT['stage'] = 'collision_checks'
        self.check_collision()
        REPORT['stage'] = 'saving'
        self.actors.select_nothing()
        if not self.levels.save_current_level():
            raise RuntimeError('Unreal could not save the new map.')
        REPORT['success']=True
        REPORT['stage']='complete'
        REPORT['piece_count']=len(self.placed)
        REPORT['counts']=self.plan['counts']
        REPORT['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_report()
        (REPORT_DIR/'layout.json').write_text(json.dumps(self.plan,ensure_ascii=False,indent=2),encoding='utf-8')
        log('SAVED '+self.map_path+' | '+str(len(self.placed))+' mesh actors')


def main():
    write_report()
    try:
        LevelBuilder(make_layout()).build()
    except Exception:
        REPORT['success']=False
        REPORT['error']=traceback.format_exc()
        write_report()
        unreal.log_error('[ThreeIslands] '+REPORT['error'])
        raise


if __name__=='__main__':
    main()
