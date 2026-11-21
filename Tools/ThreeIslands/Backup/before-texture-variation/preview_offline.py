"""Blender preview of the exact layout using the project's original source meshes.

This is an offline composition check, not an Unreal render or a collision test.
Run: blender -b -t 6 --python Tools/ThreeIslands/preview_offline.py
"""
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector, Matrix

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'Content'/'Python'))
from three_islands_layout import make_layout, rotate

PLAN=make_layout()
OUT=PROJECT/'Tools'/'ThreeIslands'/'Preview'
OUT.mkdir(parents=True,exist_ok=True)
SOURCES={
    'crystal':('crystal-stone-rock/source/stone_low+.fbx','Stone_low_1'),
    'arch':('Arch/Arch.fbx','Arch_01'),
    'pillar':('column-pillar-gameready/source/pillar_lp.fbx','lowpoly'),
    'column':('column.glb','defaultMaterial'),
    'dwarf':('dwarf_dungeon_column.glb','Object_2'),
    'stairs':('flying-rock/medieval-staircase/source/Medieval_Staircase_LP .fbx','Medieval_staircase_LP'),
    'rock':('stylized_rock.glb','Rock_Rock_MAT_0'),
    'cliff':('cliff-rock/cliff_rock1.fbx','rock2_lp'),
    'lava':('dark_rock_with_lava.glb','defaultMaterial'),
}
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
mesh_data={}
for key,(source,name) in SOURCES.items():
    before=set(bpy.data.objects)
    filepath=str(PROJECT/'Content'/'Models'/source)
    if source.endswith('.glb'):bpy.ops.import_scene.gltf(filepath=filepath)
    else:bpy.ops.import_scene.fbx(filepath=filepath)
    imported=set(bpy.data.objects)-before
    obj=next(o for o in imported if o.type=='MESH' and o.name==name)
    data=obj.data.copy()
    data.transform(obj.matrix_world)
    # Normalize source geometry into one upright coordinate system.
    mesh_data[key]=data
    for o in imported:bpy.data.objects.remove(o,do_unlink=True)

bpy.ops.mesh.primitive_cube_add()
mesh_data['cube']=bpy.context.object.data.copy()
bpy.data.objects.remove(bpy.context.object,do_unlink=True)
# Offline chamfers approximate the existing SM_ChamferCube; source is a uasset.
mesh_data['slab']=mesh_data['cube'].copy()

def bounds(data,correction):
    points=[correction@v.co for v in data.vertices]
    low=Vector([min(v[i] for v in points) for i in range(3)])
    high=Vector([max(v[i] for v in points) for i in range(3)])
    return low,high

def correction_matrix(values):
    pitch,yaw,roll=map(math.radians,values)
    return Matrix.Rotation(yaw,4,'Z')@Matrix.Rotation(pitch,4,'Y')@Matrix.Rotation(roll,4,'X')

texture_files={
    'stone':PROJECT/'Content/Models/fantasy-rock/Stylized_Rock/Rock_MAT_BaseColor.png',
    'floor':PROJECT/'Content/Models/Arch/Arch_BaseColor.png',
    'arch':PROJECT/'Content/Models/Arch/Arch_BaseColor.png',
    'crystal':PROJECT/'Content/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_BaseColor.png',
}
materials={}
for theme,palette in PLAN['palettes'].items():
    for kind in ('stone','floor','arch','stairs','crystal'):
        mat=bpy.data.materials.new(theme+'_'+kind)
        mat.use_nodes=True
        nodes=mat.node_tree.nodes
        links=mat.node_tree.links
        bsdf=nodes.get('Principled BSDF')
        color=tuple((palette['lift']+.38*palette['detail'])*v for v in palette['tint'])
        bsdf.inputs['Base Color'].default_value=(*color,1)
        bsdf.inputs['Roughness'].default_value=.84
        if kind in texture_files:
            tex=nodes.new('ShaderNodeTexImage')
            tex.image=bpy.data.images.load(str(texture_files[kind]),check_existing=True)
            gray=nodes.new('ShaderNodeRGBToBW')
            strength=nodes.new('ShaderNodeMath');strength.operation='MULTIPLY'
            strength.inputs[1].default_value=palette['detail']
            lift=nodes.new('ShaderNodeMath');lift.operation='ADD'
            lift.inputs[1].default_value=palette['lift']
            tint=nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY'
            tint.inputs[0].default_value=1
            tint.inputs[2].default_value=(*palette['tint'],1)
            links.new(tex.outputs['Color'],gray.inputs[0]);links.new(gray.outputs[0],strength.inputs[0])
            links.new(strength.outputs[0],lift.inputs[0]);links.new(lift.outputs[0],tint.inputs[1])
            links.new(tint.outputs[0],bsdf.inputs['Base Color'])
            if kind=='floor':
                geometry=nodes.new('ShaderNodeNewGeometry')
                scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE'
                scale.inputs[3].default_value=1/4.4
                links.new(geometry.outputs['Position'],scale.inputs[0]);links.new(scale.outputs[0],tex.inputs['Vector'])
        materials[(theme,kind)]=mat

stairs_data=mesh_data['stairs']
low,high=bounds(stairs_data,Matrix.Identity(4))
temp=bpy.data.objects.new('StairProbe',stairs_data);bpy.context.collection.objects.link(temp)
stair_samples=[]
for i in range(101):
    y=low.y+(high.y-low.y)*i/100
    hit,location,normal,index=temp.ray_cast(Vector(((low.x+high.x)/2,y,high.z+1)),Vector((0,0,-1)))
    if hit:stair_samples.append((y,location.z))
bpy.data.objects.remove(temp,do_unlink=True)
stair_low=min(z for y,z in stair_samples);stair_high=max(z for y,z in stair_samples)
stair_first=min(y for y,z in stair_samples if z<stair_low+.008*(high.z-low.z))
stair_last=max(y for y,z in stair_samples if z>stair_high-.008*(high.z-low.z))

for p in PLAN['pieces']:
    data=mesh_data[p['asset']]
    obj=bpy.data.objects.new(p['id'],data)
    bpy.context.collection.objects.link(obj)
    correction=correction_matrix(p['correction'])
    low,high=bounds(data,correction)
    location=Vector(p['location'])/100
    size=Vector(p['size'])/100
    if p['kind']=='stairs':
        size.z=size.z/(stair_high-stair_low)*(high.z-low.z)
        size.y=size.y/(stair_last-stair_first)*(high.y-low.y)
        normlow=(stair_low-low.z)/(high.z-low.z)
        normcenter=((stair_first+stair_last)/2-(low.y+high.y)/2)/(high.y-low.y)
        dx,dy=rotate(0,-normcenter*size.y,p['yaw'])
        location+=Vector((dx,dy,-normlow*size.z))
    scale=Vector([size[i]/max(high[i]-low[i],.000001) for i in range(3)])
    center=Vector(((low.x+high.x)/2,(low.y+high.y)/2,low.z))
    transform=Matrix.Translation(location)@Matrix.Rotation(math.radians(p['yaw']),4,'Z')@Matrix.Diagonal((*scale,1))@Matrix.Translation(-center)@correction
    obj.matrix_world=transform
    if p['material']!='original':
        # Linked geometry has per-object material slots.
        if not obj.data.materials:obj.data.materials.append(materials[(p['palette'],p['material'])])
        for slot in obj.material_slots:
            slot.link='OBJECT';slot.material=materials[(p['palette'],p['material'])]

scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.cycles.use_denoising=True
scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.54,.62,.7,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.35
bpy.ops.object.light_add(type='SUN',location=(-100,-100,200))
bpy.context.object.rotation_euler=(math.radians(28),math.radians(-25),math.radians(-25))
bpy.context.object.data.energy=2
bpy.context.object.data.angle=math.radians(5)
bpy.ops.object.light_add(type='AREA',location=(0,-80,120))
bpy.context.object.data.energy=200000
bpy.context.object.data.size=160
bpy.context.object.rotation_euler=(Vector((0,0,0))-bpy.context.object.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add()
camera=bpy.context.object
camera.data.type='ORTHO';camera.data.clip_end=2000
scene.camera=camera
scene.view_settings.view_transform='AgX'
scene.render.resolution_percentage=100

def render(name,location,target,width,x=1500,y=850):
    camera.location=location
    camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=width
    scene.render.resolution_x=x;scene.render.resolution_y=y
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)

render('overview.png',(130,-205,190),(0,0,-12),265,1800,1000)
for theme,x in [('Angel',-85),('Neutral',0),('Demon',85)]:
    render(theme.lower()+'.png',(x+58,-80,75),(x,3,-7),94,1080,1080)
render('top.png',(0,0,260),(0,0,0),250,1800,700)
(OUT/'layout.json').write_text(json.dumps(PLAN,ensure_ascii=False,indent=2))
print('OFFLINE_PREVIEW_COMPLETE',str(OUT))
