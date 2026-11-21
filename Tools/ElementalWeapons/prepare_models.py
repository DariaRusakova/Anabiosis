"""Prepare the supplied static weapons in Blender; originals are read-only.

blender -b -t 8 --python Tools/ElementalWeapons/prepare_models.py
Output FBX geometry uses a right-hand grip pivot, +X muzzle direction and Z up.
The Windows setup imports it and calibrates its FBX axis/unit conversion.
"""
import bpy
import hashlib
import json
import struct
import tempfile
import zipfile
from pathlib import Path
from mathutils import Vector, Matrix

PROJECT=Path(__file__).resolve().parents[2]
HERE=PROJECT/'Tools/ElementalWeapons'
OUT=HERE/'Prepared'
OUT.mkdir(parents=True,exist_ok=True)
MODELS=PROJECT/'Content/Models'
FLAME_ZIP=MODELS/'flamethrower/source/Flamethrower.zip'
PISTOL=MODELS/'sci-fi_pistol.glb'


def source_record(path):
    return dict(file=path.relative_to(PROJECT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def reset():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def bake_object(source,transform,use_world=True):
    data=source.data.copy()
    data.transform(transform@(source.matrix_world if use_world else Matrix.Identity(4)))
    obj=bpy.data.objects.new('Prepared_'+source.name,data)
    bpy.context.collection.objects.link(obj)
    return obj


def bounds(objects):
    points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    low=Vector([min(p[i] for p in points) for i in range(3)])
    high=Vector([max(p[i] for p in points) for i in range(3)])
    return low,high


def export(objects,name):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    path=OUT/(name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},
        add_leaf_bones=False,bake_anim=False,axis_forward='-Y',axis_up='Z',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        use_mesh_modifiers=True,mesh_smooth_type='FACE',path_mode='AUTO')
    return path.relative_to(PROJECT).as_posix()


def preview_material(name,maps):
    material=bpy.data.materials.new(name)
    material.use_nodes=True
    nodes=material.node_tree.nodes;links=material.node_tree.links
    bsdf=nodes.get('Principled BSDF')
    for kind,file in maps.items():
        if kind in ('flame','ao'):continue
        tex=nodes.new('ShaderNodeTexImage')
        tex.image=bpy.data.images.load(str(PROJECT/file),check_existing=True)
        if kind!='base_color':tex.image.colorspace_settings.name='Non-Color'
        if kind=='normal':
            normal=nodes.new('ShaderNodeNormalMap')
            links.new(tex.outputs['Color'],normal.inputs['Color'])
            links.new(normal.outputs[0],bsdf.inputs['Normal'])
        elif kind=='orm':
            separate=nodes.new('ShaderNodeSeparateColor')
            links.new(tex.outputs['Color'],separate.inputs[0])
            links.new(separate.outputs['Green'],bsdf.inputs['Roughness'])
            links.new(separate.outputs['Blue'],bsdf.inputs['Metallic'])
        else:
            links.new(tex.outputs['Color'],bsdf.inputs[{
                'base_color':'Base Color','roughness':'Roughness','metallic':'Metallic'}[kind]])
    return material


def describe(key,objects,mesh_file,maps):
    low,high=bounds(objects)
    size=(high-low)*100
    # The frontmost slice is the cage/nozzle, not the model's scene origin.
    front=[v.co for o in objects for v in o.data.vertices if v.co.x>high.x-.012]
    muzzle=Vector((high.x-.005,sum(p.y for p in front)/len(front),sum(p.z for p in front)/len(front)))*100
    result=dict(id=key,mesh_file=mesh_file,dimensions_cm=list(size),
        bounds_min_cm=list(low*100),bounds_max_cm=list(high*100),
        muzzle_cm=list(muzzle),textures=maps,flip_normal_green=key=='water_pistol',
        right_hand_cm=[-4.0,0.0,-2.0],
        left_hand_cm=[21.0,-5.0,-11.0] if key=='flamethrower' else [5.0,-3.5,0.0],
        hip_location_cm=[25.0,15.0,-18.0],
        aim_location_cm=[25.0,8.0,-float(muzzle.z)] if key=='flamethrower' else [28.0,0.0,-float(muzzle.z)-1.0],
        hip_rotation=[-3.0,-3.0,0.0],aim_rotation=[0.0,-3.0,0.0] if key=='flamethrower' else [0.0,0.0,0.0],
        hold_pose='/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS' if key=='flamethrower' else '/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS',
        attack_pose='/Game/Characters/Mannequins/Anims/Rifle/MM_Rifle_Fire' if key=='flamethrower' else '/Game/Characters/Mannequins/Anims/Pistol/MM_Pistol_Fire')
    expected=90 if key=='flamethrower' else 35
    assert abs(size.x-expected)<.001,(key,size)
    assert muzzle.x>expected*.65,(key,muzzle)
    return result


def render(objects,name):
    scene=bpy.context.scene
    low,high=bounds(objects);center=(low+high)/2;span=max(high-low)
    bpy.ops.object.light_add(type='AREA',location=center+Vector((1,-2,3))*span)
    light=bpy.context.object;light.data.energy=500*span**2;light.data.size=span*3
    light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=center+Vector((1.3,-2,1.1))*span)
    camera=bpy.context.object;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=span*1.55
    scene.camera=camera;scene.render.engine='CYCLES';scene.cycles.samples=16
    scene.cycles.use_denoising=True;scene.world.color=(.2,.2,.2)
    scene.render.resolution_x=1000;scene.render.resolution_y=700;scene.render.resolution_percentage=100
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)


sources=[source_record(FLAME_ZIP),source_record(PISTOL)]
weapons=[]
reset()
with zipfile.ZipFile(FLAME_ZIP) as archive:
    with tempfile.TemporaryDirectory(prefix='anabiosis_flamethrower_') as temporary:
        fbx=Path(temporary)/'Flamethrower.fbx'
        fbx.write_bytes(archive.read('Flamethrower.fbx'))
        bpy.ops.import_scene.fbx(filepath=str(fbx))
source_objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
physical=[o for o in source_objects if o.name!='Flamethrower_Flame']
low,high=bounds(physical)
scale=.9/(high.y-low.y)
rotation=Matrix.Rotation(1.5707963267948966,4,'Z')
transform=Matrix.Scale(scale,4)@rotation@Matrix.Translation(Vector((0,-9.25,-1.82)))
prepared=[bake_object(o,transform) for o in physical]
for o in source_objects:bpy.data.objects.remove(o,do_unlink=True)
flame_maps={key:(MODELS/'flamethrower/textures'/f'Flamethrower_{suffix}.png').relative_to(PROJECT).as_posix()
            for key,suffix in [('base_color','BaseColor'),('normal','Normal'),('roughness','Roughness'),
                               ('metallic','Metallic'),('ao','AO'),('flame','Flame')]}
for file in flame_maps.values():sources.append(source_record(PROJECT/file))
material=preview_material('Flamethrower_SourcePBR',flame_maps)
for o in prepared:o.data.materials.clear();o.data.materials.append(material)
weapons.append(describe('flamethrower',prepared,export(prepared,'SM_Flamethrower'),flame_maps))
render(prepared,'flamethrower')

reset()
raw=PISTOL.read_bytes();length,tag=struct.unpack_from('<II',raw,12)
assert tag==0x4E4F534A
document=json.loads(raw[20:20+length]);bin_start=20+length
bin_length,bin_tag=struct.unpack_from('<II',raw,bin_start)
assert bin_tag==0x004E4942
binary=raw[bin_start+8:bin_start+8+bin_length]
pistol_maps={}
for kind,index in [('base_color',0),('orm',1),('normal',2)]:
    image=document['images'][document['textures'][index]['source']]
    view=document['bufferViews'][image['bufferView']]
    extension='.png' if image['mimeType']=='image/png' else '.jpg'
    path=OUT/f'WaterPistol_{kind}{extension}'
    offset=view.get('byteOffset',0);path.write_bytes(binary[offset:offset+view['byteLength']])
    pistol_maps[kind]=path.relative_to(PROJECT).as_posix()
bpy.ops.import_scene.gltf(filepath=str(PISTOL))
source=next(o for o in bpy.context.scene.objects if o.type=='MESH')
z_values=[v.co.z for v in source.data.vertices]
scale=.35/(max(z_values)-min(z_values))
rotation=Matrix(((0,0,1,0),(-1,0,0,0),(0,-1,0,0),(0,0,0,1)))
transform=Matrix.Scale(scale,4)@rotation@Matrix.Translation(Vector((0,-1.8,2.7)))
prepared=[bake_object(source,transform,use_world=False)]
for o in list(bpy.context.scene.objects):
    if o not in prepared:bpy.data.objects.remove(o,do_unlink=True)
material=preview_material('WaterPistol_SourcePBR',pistol_maps)
for o in prepared:o.data.materials.clear();o.data.materials.append(material)
weapons.append(describe('water_pistol',prepared,export(prepared,'SM_WaterPistol'),pistol_maps))
render(prepared,'water_pistol')

manifest=dict(version=1,units='cm',forward='+X',up='+Z',weapons=weapons,source_files=sources,
              water_pistol_attribution=document['asset'].get('extras',{}))
(HERE/'weapons.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('PREPARED_ELEMENTAL_WEAPONS',[(w['id'],w['dimensions_cm'],w['muzzle_cm']) for w in weapons])
