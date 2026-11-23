"""Deterministic, engine-independent level layout. Units: Unreal centimetres.

All geometry comes from assets already in this project. A mesh location denotes
the centre of its footprint at the BOTTOM of its fitted, upright bounding box.
Stairs use the centre of their walkable run and the bottom tread elevation.
"""
import math
import random
from collections import Counter

REVISION = 'three-islands-1.2-native-materials'
SEED = 574211
ASSETS = {
    'cube': '/Game/LevelPrototyping/Meshes/SM_Cube',
    'slab': '/Game/LevelPrototyping/Meshes/SM_ChamferCube',
    'crystal': '/Game/Models/crystal-stone-rock/source/Mesh',
    'arch': '/Game/Models/Arch/Mesh',
    'pillar': '/Game/Models/column-pillar-gameready/source/pillar_lp',
    'column': '/Game/Models/column/StaticMeshes/column',
    'dwarf': '/Game/Models/dwarf_dungeon_column/StaticMeshes/dwarf_dungeon_column',
    'stairs': '/Game/Models/flying-rock/medieval-staircase/source/Medieval_Staircase_LP_',
    'rock': '/Game/Models/stylized_rock/StaticMeshes/stylized_rock',
    'cliff': '/Game/Models/cliff-rock/cliff_rock1',
    'lava': '/Game/Models/dark_rock_with_lava/StaticMeshes/dark_rock_with_lava',
    'rock_big': '/Game/Models/rock_big/StaticMeshes/rock_big',
    'rock_tower': '/Game/Models/rock_tower/StaticMeshes/rock_tower',
    'basalt': '/Game/Models/flying-rock/rock-basalt/source/ROCK',
    'ruined_arcade': '/Game/Models/Zyklus15_Zeile7/tripo_convert_5f703562-179e-46cc-bd64-f0f73a9ff39a',
}
TEXTURES = {
    'stone': '/Game/Models/fantasy-rock/Stylized_Rock/Rock_MAT_BaseColor',
    'stone_normal': '/Game/Models/fantasy-rock/Stylized_Rock/Rock_MAT_Normal',
    'arch': '/Game/Models/Arch/Arch_BaseColor',
    'arch_normal': '/Game/Models/Arch/Arch_Normal',
    'stairs': '/Game/Models/flying-rock/medieval-staircase/textures/Medieval_Staircase_LP__DefaultMaterial_Bas',
    'stairs_normal': '/Game/Models/flying-rock/medieval-staircase/textures/Medieval_Staircase_LP__DefaultMaterial_Nor',
    'crystal': '/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_BaseColor',
    'crystal_emissive': '/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_Emissive',
}
# The six FBX imports have UVs and matching texture assets, but their assigned
# materials are untextured LegacyPhong instances or WorldGridMaterial. Rebuild
# only those bindings, using each model's own maps without palette recolouring.
SOURCE_MATERIALS = {
    'arch': {
        'base_color':'/Game/Models/Arch/Arch_BaseColor',
        'normal':'/Game/Models/Arch/Arch_Normal',
        'roughness':'/Game/Models/Arch/Arch_Roughness',
    },
    'pillar': {
        'base_color':'/Game/Models/column-pillar-gameready/textures/pillar_lp_DefaultMaterial_BaseColor',
        'normal':'/Game/Models/column-pillar-gameready/textures/testinormal1',
        'roughness':'/Game/Models/column-pillar-gameready/textures/pillar_lp_DefaultMaterial_Roughness',
        'metallic':'/Game/Models/column-pillar-gameready/textures/pillar_lp_DefaultMaterial_Metallic',
        'ao':'/Game/Models/column-pillar-gameready/textures/pillar_lp_DefaultMaterial_cavity',
    },
    'stairs': {
        'base_color':'/Game/Models/flying-rock/medieval-staircase/textures/Medieval_Staircase_LP__DefaultMaterial_Bas',
        'normal':'/Game/Models/flying-rock/medieval-staircase/textures/Medieval_Staircase_LP__DefaultMaterial_Nor',
        'roughness':'/Game/Models/flying-rock/medieval-staircase/textures/Medieval_Staircase_LP__DefaultMaterial_Rou',
        'ao':'/Game/Models/flying-rock/medieval-staircase/textures/AO',
    },
    'cliff': {
        'base_color':'/Game/Models/cliff-rock/textures/rock2_BC',
        'normal':'/Game/Models/cliff-rock/textures/rock2_N',
        'orm':'/Game/Models/cliff-rock/textures/rock2_ORM',
    },
    'crystal': {
        'base_color':'/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_BaseColor',
        'normal':'/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_Normal',
        'roughness':'/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_Roughness',
        'metallic':'/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_Metallic',
        'emissive':'/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_Emissive',
        'ao':'/Game/Models/crystal-stone-rock/textures/stone_low+_Stone_low_1_AO',
    },
    'basalt': {
        'base_color':'/Game/Models/flying-rock/rock-basalt/textures/ROCK_LOW_MESH_Material_003_BaseColor',
        'normal':'/Game/Models/flying-rock/rock-basalt/textures/ROCK_LOW_MESH_Material_003_Normal',
        'roughness':'/Game/Models/flying-rock/rock-basalt/textures/ROCK_LOW_MESH_Material_003_Roughness',
    },
}
PALETTES = {
    'Angel': {'tint': (0.86, 0.88, 0.81), 'lift': 0.43, 'detail': 0.46,
              'accent': (0.28, 0.65, 0.91), 'column': 'pillar'},
    'Neutral': {'tint': (0.45, 0.48, 0.46), 'lift': 0.26, 'detail': 0.62,
                'accent': (0.25, 0.48, 0.43), 'column': 'column'},
    'Demon': {'tint': (0.24, 0.19, 0.21), 'lift': 0.12, 'detail': 0.52,
              'accent': (1.0, 0.095, 0.025), 'column': 'dwarf'},
}
ISLANDS = [
    {'name': 'Angel', 'center': (-8500, 0), 'spawn': (0, -2250),
     'description': 'Ivory sanctuary / two flank terraces / elevated colonnade'},
    {'name': 'Neutral', 'center': (0, 0), 'spawn': (0, -2250),
     'description': 'Grey forum / split approaches / central stylized monolith'},
    {'name': 'Demon', 'center': (8500, 0), 'spawn': (0, -2250),
     'description': 'Obsidian bastion / staggered cover / three-arch crown'},
]


def rotate(x, y, yaw):
    a = math.radians(yaw)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def make_layout():
    rng = random.Random(SEED)
    pieces, markers = [], []

    def mesh(label, asset, palette, x, y, z, size, yaw=0, role='decoration',
             material='original', collision=True, correction=(0, 0, 0), folder=None):
        if material=='original' and asset in SOURCE_MATERIALS:
            material='source'
        pieces.append(dict(id=f'{len(pieces):04d}_{label}', kind='mesh', asset=asset,
                           palette=palette, location=[x, y, z], size=list(size),
                           yaw=yaw, role=role, material=material, collision=collision,
                           correction=list(correction), folder=folder or role))

    def stairs(label, palette, x, y, z, rise, run, width=480, yaw=0):
        pieces.append(dict(id=f'{len(pieces):04d}_{label}', kind='stairs', asset='stairs',
                           palette=palette, location=[x, y, z], size=[width, run, rise],
                           yaw=yaw, role='stairs', material='source', collision=True,
                           correction=[0, 0, 0], folder='03_Stairs'))

    for island in ISLANDS:
        theme = island['name']
        ox, oy = island['center']

        def m(label, asset, x, y, z, size, **kwargs):
            mesh(f'{theme}_{label}', asset, theme, ox+x, oy+y, z, size, **kwargs)

        def s(label, x, y, z, rise, run, width=480, yaw=0):
            stairs(f'{theme}_{label}', theme, ox+x, oy+y, z, rise, run, width, yaw)

        def arch(label, x, y, z, width=900, height=850, yaw=0):
            # The FBX supplies a HALF arch: build a mirrored pair, not a stretched
            # single spandrel. Each outer pier supports one side of the crown.
            for side in (-1,1):
                dx,dy=rotate(side*width/4,0,yaw)
                m(f'{label}_Half{side}', 'arch', x+dx, y+dy, z,
                  (width/2+4, 155, height), yaw=yaw,
                  correction=(0,90 if side==1 else 270,0), material='original',
                  role='arch', folder='05_Arches')
                pieces[-1]['arch_side']=side

        def column(label, x, y, z, height=720, width=165):
            m(label, PALETTES[theme]['column'], x, y, z, (width, width, height),
              role='column', folder='06_Colonnades')

        def colonnade(label, x, y, z, count=4, spacing=420, height=720, yaw=0):
            # Continuous lintels actually rest on columns; open aisles between them.
            for row in (-1, 1):
                ruined = theme == 'Demon' and label == 'SanctuaryColonnade' and row == 1
                for j in range(count):
                    dx, dy = rotate((j-(count-1)/2)*spacing, row*300, yaw)
                    column(f'{label}_C{row}_{j}', x+dx, y+dy, z,
                           height*.34 if ruined and j == 1 else height)
                if ruined:
                    # Only the surviving pair supports a lintel. The other
                    # spans have fallen onto the terrace, leaving an open gap.
                    dx,dy=rotate(spacing,row*300,yaw)
                    m(f'{label}_SurvivingLintel', 'slab',x+dx,y+dy,z+height-10,
                      (spacing+220,200,130),yaw=yaw,role='lintel',material='floor',
                      folder='06_Colonnades')
                    dx,dy=rotate(-spacing,0,yaw)
                    m(f'{label}_FallenLintel', 'slab',x+dx,y+dy,z,
                      (spacing+160,190,115),yaw=yaw+19,role='cover',material='floor',
                      folder='08_Details')
                    continue
                dx, dy = rotate(0, row*300, yaw)
                m(f'{label}_Lintel{row}', 'slab', x+dx, y+dy, z+height-10,
                  ((count-1)*spacing+220, 200, 130), yaw=yaw,
                  role='lintel', material='floor', folder='06_Colonnades')

        # The isolated crystal mesh, never the imported presentation plane.
        foundation_size={'Angel':(7500,6900,4300),'Neutral':(7100,7100,4600),
                         'Demon':(6900,6650,5300)}[theme]
        m('CrystalFoundation', 'crystal', 0, 0, -foundation_size[2]-250, foundation_size,
          role='foundation', material='original', collision=False,
          correction=(0, 0, 180), folder='01_Foundation')
        for j, (x, y, w, d, h) in enumerate([
                (-1850, 900, 2600, 2800, 2650), (1950, -600, 2500, 2550, 2900),
                (-900, -1950, 2200, 2100, 2400)]):
            m(f'CrystalShard{j}', 'crystal', x, y, -h-280, (w, d, h),
              yaw=j*63+18+{'Angel':0,'Neutral':19,'Demon':47}[theme],
              role='foundation', material='original', collision=False,
              correction=(0, 0, 180), folder='01_Foundation')

        # Flat, contiguous collision plane made from existing project cubes.
        # The slightly staggered perimeter is subsequently dressed in rock.
        for ix in range(-6, 7):
            for iy in range(-6, 7):
                x, y = ix*480, iy*480
                if x*x+y*y > 3000**2:
                    continue
                m(f'Ground_{ix}_{iy}', 'cube', x, y, -180, (480, 480, 180),
                  role='ground', material='floor', folder='02_Floors')
                # Shallow bevelled paving, not a high random obstacle field.
                if (ix+iy) % 3 == 0 and x*x+y*y < 2550**2:
                    m(f'Paving_{ix}_{iy}', 'slab', x+7, y-5, 0,
                      (445, 440, 5), yaw=rng.uniform(-1.2, 1.2), role='paving',
                      material='floor', collision=False, folder='02_Floors')

        # Irregular stone shoulder hides the modular ground edge. Bridge mouths
        # remain clear, and the side faces hang below the play surface.
        for j in range(40):
            a = 2*math.pi*j/40
            radius = 2940+rng.uniform(-80, 90)
            x, y = radius*math.cos(a), radius*math.sin(a)
            if abs(x)>2200 and min(abs(y-1350), abs(y+1350)) < 470:
                continue
            rim_asset=({'Angel':'rock_tower','Neutral':'rock','Demon':'lava'}[theme]
                       if j%5==0 else {'Angel':'rock','Neutral':'rock_big','Demon':'basalt'}[theme])
            m(f'RimRock{j}', rim_asset, x, y, -430-rng.uniform(0, 65),
              (rng.uniform(620, 900), rng.uniform(580, 850), rng.uniform(450, 610)),
              yaw=rng.uniform(0, 360), role='rim', folder='01_Foundation')
        for j in range(13):
            a = 2*math.pi*j/13+.2
            m(f'Undercliff{j}', 'basalt' if theme=='Demon' and j%2 else 'cliff',
              3100*math.cos(a), 2850*math.sin(a),
              -1700-rng.uniform(0, 350), (1100, 1050, 1550),
              yaw=j*49, role='foundation', collision=False, folder='01_Foundation')

        if theme != 'Neutral':
            # Broad elevated sanctuary/bastion. Two independent approaches.
            m('SanctuaryTerrace', 'cube', 0, 1850, -10, (2100, 1800, 610),
              role='terrace', material='floor', folder='02_Floors')
            s('SanctuaryFrontStairs', 0, 400, 0, 600, 1100, 600)
            s('SanctuarySideStairs', -1510, 1660, 0, 600, 920, 470, -90)
            arch('SanctuaryGreatArch', 0, 2420, 600, 1160, 1040)
            colonnade('SanctuaryColonnade', 0, 1710, 600, 4, 460, 740)
            for side in (-1, 1):
                m(f'FlankTerrace{side}', 'cube', side*2070, 0, -10,
                  (1000, 1500, 310), role='terrace', material='floor', folder='02_Floors')
                s(f'FlankStairs{side}', side*2070, -1125, 0, 300, 750, 430)
                arch(f'FlankArch{side}', side*2070, 280, 300, 700, 680)
                for k in (-1, 1):
                    column(f'FlankColumn{side}_{k}', side*2070+k*370, -510, 300, 560, 140)
            if theme == 'Angel':
                # Ordered, readable frontage; paired small shrines on the approach.
                arch('EntranceArch', 0, -1690, 0, 1030, 860)
                for side in (-1, 1):
                    colonnade(f'OuterGallery{side}', side*1550, -1900, 0,
                              count=3, spacing=330, height=600, yaw=90)
                    column(f'SanctuarySpire{side}', side*930, 2460, 600,
                           1080 if side==-1 else 940, 170)
            else:
                # Broken triple crown and a denser, asymmetric basalt silhouette.
                for side in (-1, 1):
                    arch(f'CrownArch{side}', side*750, 2400, 600, 610, 850)
                    column(f'CrownTower{side}', side*970, 2410, 600, 1160, 220)
                    colonnade(f'BrokenGallery{side}', side*1400, -1870, 0,
                              count=3, spacing=360, height=650, yaw=90)
                    m(f'LavaSentinel{side}', 'lava', side*550, -2360, 0,
                      (300, 280, 500), yaw=side*35, role='cover',
                      material='original', folder='04_Cover')
        else:
            for side in (-1, 1):
                m(f'ForumTerrace{side}', 'cube', side*1550, 1550, -10,
                  (1400, 1500, 370), role='terrace', material='floor', folder='02_Floors')
                s(f'ForumFrontStairs{side}', side*1550, 350, 0, 360, 900, 500)
                # Rear access makes these firing positions flankable.
                s(f'ForumInnerStairs{side}', side*500, 1850, 0, 360, 700, 430, -side*90)
                colonnade(f'ForumColonnade{side}', side*1550, 1650, 360,
                          count=3, spacing=410, height=650)
                arch(f'ForumArch{side}', side*1550, 1910, 360, 850, 760)
            # Explicitly requested stylized rock: a large central navigation landmark.
            m('StylizedRock_Landmark', 'rock', 0, 370, 0, (650, 560, 920),
              yaw=27, role='landmark', folder='07_Landmarks')
            # Existing textured two-storey arcade gives the central island a
            # different skyline, with its own authored stonework and UVs.
            m('ForumRuinedArcade', 'ruined_arcade', 0, 2410, 0, (1580,360,1280),
              role='landmark',collision=False, folder='07_Landmarks')
            for j in range(3):
                column(f'BrokenForumColumn{j}', -700+j*700, -1800+(j%2)*140,
                       0, (480, 270, 650)[j], 175)

        # Cover belongs to small defensible positions, never a uniform scatter.
        # 1.1 m crouch rocks alternate with 2 m line-of-sight blockers.
        cover_groups = [(-820,-770,20), (900,-500,-25), (-970,610,8), (920,600,-14)]
        if theme == 'Demon':
            cover_groups = [(-850,-680,33), (950,-400,-16), (-1030,650,-12), (1000,650,20)]
        for j, (x, y, yaw) in enumerate(cover_groups):
            cover_asset={'Angel':('rock','rock_tower'),
                         'Neutral':('rock_big','rock'),
                         'Demon':('basalt','lava')}[theme][j%2]
            m(f'CoverRock{j}', cover_asset, x, y, 0, (620, 450, 205 if j%2 else 120),
              yaw=yaw, role='cover', folder='04_Cover')
            dx, dy = rotate(260, 240, yaw)
            m(f'CoverWing{j}', 'basalt' if theme=='Demon' else 'rock',
              x+dx, y+dy, 0, (310, 320, 260),
              yaw=yaw+43, role='cover', folder='04_Cover')
            if theme == 'Demon' and j in (0, 3):
                m(f'LavaCover{j}', 'lava', x-230, y-150, 0, (210, 250, 260),
                  yaw=yaw, role='cover', material='original', folder='04_Cover')

        # Segmented parapets protect rear platforms without sealing their exits.
        platforms = [(0,1850,2100,1800,600)] if theme!='Neutral' else [
            (-1550,1550,1400,1500,360), (1550,1550,1400,1500,360)]
        for k,(x,y,w,d,h) in enumerate(platforms):
            # Stone facing breaks up the large terrace wall. These pieces sit
            # against the existing solid wall and leave its stair mouths open.
            for face in (-1,1):
                for j in range(-2,3):
                    dx=j*w/5
                    if face==-1 and abs(dx)<440:
                        continue
                    m(f'TerraceFacing{k}_{face}_{j}',
                      {'Angel':'rock','Neutral':'rock_big','Demon':'basalt'}[theme], x+dx,
                      y+face*(d/2-35), -20,
                      (w/4.8, 240, h+25), yaw=j*8,
                      role='facing', collision=False, folder='02_Floors')
            for side in (-1,1):
                m(f'TerraceParapet{k}_{side}', 'slab', x+side*(w/2-85), y+d/2-100,
                  h, (160,200,105), role='cover', material='floor', folder='04_Cover')
            for j in (-1,1):
                m(f'TerraceFrontCover{k}_{j}',
                  {'Angel':'rock','Neutral':'rock_big','Demon':'basalt'}[theme],
                  x+j*(w/2-220), y-d/2+90,
                  h, (330,300,115), yaw=j*21, role='cover', folder='04_Cover')

        # A few displaced architectural fragments tell the same ruin story.
        for j,(x,y) in enumerate([(-2350,-1950),(2390,-1900),(-2300,2100),(2350,2050)]):
            m(f'BrokenStone{j}', {'Angel':'rock','Neutral':'rock_big','Demon':'basalt'}[theme],
              x,y,0,(260,230,160),yaw=j*72,
              role='rubble', folder='08_Details')
        for j,(x,y,h) in enumerate([(-2550,650,330),(2250,1550,420),(-450,2500,280)]):
            column(f'IsolatedRuinColumn{j}',x,y,0,h,180)
        if theme=='Neutral':
            m('FallenForumColumn', 'column', -1300,-450,0,(640,180,180),
              yaw=-25,correction=(90,0,0),role='cover',folder='08_Details')
        elif theme=='Demon':
            for j,(x,y,h) in enumerate([(-2280,1860,960),(2110,2130,1360)]):
                m(f'BasaltSpire{j}', 'basalt',x,y,-120,(430,410,h),
                  yaw=37+j*71,role='landmark',folder='07_Landmarks')
        markers.append(dict(id=f'{theme}_Arrival', palette=theme,
                            location=[ox,oy-2250,115], yaw=90, kind='spawn' if theme=='Angel' else 'marker'))
        markers.append(dict(id=f'{theme}_HighGround', palette=theme,
                            location=[ox+(0 if theme!='Neutral' else 1550),oy+(1850 if theme!='Neutral' else 1550),
                                      600 if theme!='Neutral' else 360], yaw=0, kind='marker'))

    # Two 5.2 m-wide routes per island pair; their clear width is 3.6 m.
    # Each deck overlaps the ground by 160+ cm. Rails leave all mouths open.
    for pair, (left,right) in enumerate([(-8500,0),(0,8500)]):
        x0,x1=left+2450,right-2450
        length=x1-x0
        for lane,y in enumerate((-1350,1350)):
            theme='Neutral'
            cx=(x0+x1)/2
            for j in range(10):
                x=x0+(j+.5)*length/10
                mesh(f'Bridge{pair}_{lane}_Deck{j}','cube',theme,x,y,-118,
                     (length/10+2,520,120),role='bridge',material='floor',folder='09_Bridges')
                for side in (-1,1):
                    mesh(f'Bridge{pair}_{lane}_Rail{side}_{j}','slab',theme,x,y+side*220,2,
                         (length/10+2,80,105),role='rail',material='floor',folder='09_Bridges')
            for j in range(3):
                x=cx+(j-1)*850
                for side in (-1,1):
                    mesh(f'Bridge{pair}_{lane}_UnderArch{j}_{side}','arch',theme,x+side*207,y,-580,
                         (420,170,440),yaw=0,correction=(0,90 if side==1 else 270,0),role='bridge_detail',
                         material='original',collision=False,folder='09_Bridges')

    return dict(revision=REVISION,seed=SEED,units='cm',islands=ISLANDS,
                assets=ASSETS,textures=TEXTURES,source_materials=SOURCE_MATERIALS,palettes=PALETTES,
                pieces=pieces,markers=markers,
                metrics=dict(island_diameter_m=64,island_spacing_m=85,
                             bridge_clear_width_cm=360,character_radius_cm=34,
                             character_half_height_cm=96,
                             terrace_heights_cm=[300,360,600]),
                counts=dict(Counter(p['role'] for p in pieces)))


if __name__ == '__main__':
    import json
    print(json.dumps(make_layout(),ensure_ascii=False,indent=2))
