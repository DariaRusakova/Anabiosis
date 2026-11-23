"""Offline structural checks and conservative capsule-footprint route checks.

No Unreal imports. This validates the design data, not UE's runtime physics.
Stairs are evaluated as ramps; imported stair treads are calibrated by the UE
builder and still require a human Play In Editor walkthrough.
"""
import ast
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'Content'/'Python'))
from three_islands_layout import make_layout, rotate

CELL=50
RADIUS=34
HEIGHT=192


def cells_for(piece,padding=0):
    x,y,z=piece['location'];w,d,h=piece['size']
    a=math.radians(piece['yaw']);c=math.cos(a);s=math.sin(a)
    ex=abs(c)*w/2+abs(s)*d/2+padding
    ey=abs(s)*w/2+abs(c)*d/2+padding
    for ix in range(math.ceil((x-ex)/CELL),math.floor((x+ex)/CELL)+1):
        for iy in range(math.ceil((y-ey)/CELL),math.floor((y+ey)/CELL)+1):
            dx=ix*CELL-x;dy=iy*CELL-y
            lx=c*dx+s*dy;ly=-s*dx+c*dy
            if abs(lx)<=w/2+padding and abs(ly)<=d/2+padding:
                yield (ix,iy),lx,ly


def navigation(plan):
    heights={}
    for p in plan['pieces']:
        if p['role'] not in ('ground','terrace','bridge','stairs'):continue
        for cell,lx,ly in cells_for(p):
            z=p['location'][2]+p['size'][2]
            if p['kind']=='stairs':
                z=p['location'][2]+(ly/p['size'][1]+.5)*p['size'][2]
            heights[cell]=max(heights.get(cell,-99999),z)
    blocked=set()
    for p in plan['pieces']:
        if not p['collision'] or p['role'] in ('ground','terrace','bridge','stairs'):continue
        for cell,lx,ly in cells_for(p,RADIUS):
            if cell not in heights:continue
            feet=heights[cell]
            z=p['location'][2];h=p['size'][2]
            if z+h<=feet+2 or z>=feet+HEIGHT:continue
            if p['role']=='arch':
                # Half arches have one outer pier and an open inner edge.
                side=p.get('arch_side',1)
                if side*lx < -p['size'][0]*.03-RADIUS and feet+HEIGHT<z+h*.62:continue
            blocked.add(cell)
    return {cell:z for cell,z in heights.items() if cell not in blocked}


def nearest(nav,point):
    x,y,z=point
    candidates=[]
    for dx in range(-2,3):
        for dy in range(-2,3):
            cell=(round(x/CELL)+dx,round(y/CELL)+dy)
            if cell in nav and abs(nav[cell]-z)<45:
                candidates.append(((cell[0]*CELL-x)**2+(cell[1]*CELL-y)**2,cell))
    if not candidates:raise AssertionError('No clear standing space near '+str(point))
    return min(candidates)[1]


def flood(nav,start):
    reached={start};queue=deque([start])
    while queue:
        current=queue.popleft();x,y=current
        for next_cell in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if next_cell not in nav or next_cell in reached:continue
            # No mandatory jump or one-way drop on required routes.
            if abs(nav[next_cell]-nav[current])>44:continue
            reached.add(next_cell);queue.append(next_cell)
    return reached


def main():
    plan=make_layout()
    assert plan==make_layout(),'Layout is not deterministic'
    for script in (PROJECT/'Content'/'Python').glob('*.py'):
        ast.parse(script.read_text(encoding='utf-8'))
    source_paths=list(plan['assets'].items())+list(plan['textures'].items())
    source_paths.extend((asset+'_'+channel,path)
                        for asset,maps in plan['source_materials'].items() for channel,path in maps.items())
    for key,path in source_paths:
        package=PROJECT/('Content'+path.removeprefix('/Game')+'.uasset')
        assert package.is_file(),(key,package)
        # Only inspect static identifiers; never deserialize a UE package offline.
        if path in plan['assets'].values():
            assert b'StaticMesh\x00' in package.read_bytes()[:200000],key
    ids=[p['id'] for p in plan['pieces']]
    assert len(ids)==len(set(ids)),'Actor identifiers must be unique'
    for p in plan['pieces']:
        assert all(math.isfinite(x) and x>0 for x in p['size']),p['id']
        assert all(math.isfinite(x) for x in p['location']),p['id']
    for island in plan['islands']:
        theme=island['name']
        pieces=[p for p in plan['pieces'] if p['palette']==theme]
        assert all(any(p['role']==role for p in pieces) for role in ('foundation','arch','column','stairs','cover'))
        assert any(p['asset']=='crystal' and p['role']=='foundation' for p in pieces)
    assert any(p['id'].endswith('Neutral_StylizedRock_Landmark') for p in plan['pieces'])
    assert sum(m['kind']=='spawn' for m in plan['markers'])==1
    nav=navigation(plan)
    start=nearest(nav,(-8500,-2250,0))
    reached=flood(nav,start)
    targets=[]
    for island in plan['islands']:
        theme=island['name'];ox,oy=island['center']
        targets.append((theme+'_Arrival',(ox,oy-2250,0)))
        if theme=='Neutral':
            targets.extend([(theme+f'_Terrace{side}',(ox+side*1550,1550,360)) for side in (-1,1)])
            targets.extend([(theme+f'_RockBypass{side}',(ox+side*650,370,0)) for side in (-1,1)])
        else:
            targets.append((theme+'_Sanctuary',(ox,1850,600)))
            targets.extend([(theme+f'_Flank{side}',(ox+side*2070,0,300)) for side in (-1,1)])
    for x in (-4250,4250):
        for y in (-1350,1350):targets.append((f'Bridge_{x}_{y}',(x,y,0)))
    for label,point in targets:
        cell=nearest(nav,point)
        assert cell in reached,'Unreachable required destination: '+label+' '+str(point)
    alternate_checks=0
    for island in plan['islands']:
        theme=island['name'];ox=island['center'][0]
        names=(['SanctuaryFrontStairs','SanctuarySideStairs'] if theme!='Neutral' else
               ['ForumFrontStairs-1','ForumInnerStairs-1','ForumFrontStairs1','ForumInnerStairs1'])
        for name in names:
            removed=next(p for p in plan['pieces'] if p['id'].endswith(theme+'_'+name))
            changed={**plan,'pieces':[p for p in plan['pieces'] if p is not removed]}
            alternative=navigation(changed)
            reachable=flood(alternative,nearest(alternative,(ox,-2250,0)))
            destination=((ox,1850,600) if theme!='Neutral' else
                         (ox+(-1550 if name.endswith('-1') else 1550),1550,360))
            assert nearest(alternative,destination) in reachable,'No alternative approach after closing '+removed['id']
            alternate_checks+=1
    result=dict(success=True,revision=plan['revision'],mesh_actors=len(plan['pieces']),
                counts=plan['counts'],source_asset_files=len({path for key,path in source_paths}),
                grid_cell_cm=CELL,character_radius_cm=RADIUS,character_height_cm=HEIGHT,
                reachable_cells=len(reached),required_destinations=len(targets),
                alternative_approach_checks=alternate_checks,
                layout_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),
                scope='Offline data and conservative route graph; UE/PIE not run')
    output=PROJECT/'Tools/ThreeIslands/Preview/offline_validation.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
