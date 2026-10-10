import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pytest
from rsi_mesh import geometry as g


def program(kind,size):
    return {"schema_version":1,"root":{"kind":kind,"size":size}}


def test_larger_configured_trees_export_and_score(monkeypatch):
    nodes=[{"kind":"sphere","size":[.5]} for _ in range(32)]
    while len(nodes)>1:
        nodes=[{"op":"union","children":nodes[i:i+2]} for i in range(0,len(nodes),2)]
    p={"schema_version":1,"root":nodes[0]}
    monkeypatch.setenv('RSI_MAX_PRIMITIVES','24')
    with pytest.raises(ValueError,match='Too many'):
        g.export_mesh(p,resolution=24)
    monkeypatch.setenv('RSI_MAX_PRIMITIVES','48')
    monkeypatch.setenv('RSI_MAX_DEPTH','16')
    mesh=g.export_mesh(p,resolution=24)
    assert mesh.is_watertight
    assert g.metrics(p,mesh,mesh,grid=12,count=100)['primitive_count']==32
    with pytest.raises(ValueError,match='Too many'):
        g.validate(p,max_leaves=24)
    with pytest.raises(ValueError,match='depth'):
        g.validate(p,max_depth=3)


@pytest.mark.parametrize("kind,size,inside",[
    ("sphere",[.5],[0,0,0]),("box",[.5,.3,.2],[0,0,0]),
    ("cylinder",[.4,.6],[0,0,0]),("cone",[.5,.2,.6],[0,0,0]),
    ("torus",[.6,.15],[.6,0,0]),("capsule",[.2,.5],[0,0,.6])])
def test_primitives_sign_and_closed_surface(kind,size,inside):
    p=program(kind,size); g.validate(p)
    assert g.field(p,np.array([inside,[3,3,3]]))[0]<0
    assert g.field(p,np.array([inside,[3,3,3]]))[1]>0
    mesh=g.export_mesh(p,64)
    assert mesh.is_watertight and mesh.volume>0


def test_nested_booleans_and_transform():
    outer=program("box",[1,1,1])["root"]
    hole=program("cylinder",[.3,2])["root"]
    p={"schema_version":1,"root":{"op":"difference","children":[outer,hole]}}
    assert g.field(p,np.array([[0,0,0],[.5,0,0]])).tolist()==pytest.approx([.3,-.2])
    p["root"]={"op":"intersection","children":[p["root"],program("sphere",[.8])["root"]]}
    assert g.field(p,np.array([[.9,0,0]]))[0]>0
    leaf=program("box",[.8,.2,.2]); leaf["root"]["rotation"]=[0,0,np.pi/2]
    leaf["root"]["center"]=[.3,0,0]
    assert g.field(leaf,np.array([[.3,.5,0]]))[0]<0


def test_invalid_programs():
    with pytest.raises(ValueError): g.validate(program("mesh",[1]))
    with pytest.raises(ValueError): g.validate(program("sphere",[-1]))
    with pytest.raises(ValueError): g.validate(program("torus",[.1,.2]))
    with pytest.raises(ValueError): g.validate(program("sphere",[float('nan')]))
    with pytest.raises(ValueError): g.validate({"schema_version":1,"root":{"op":"union","children":[]}})
    p=program("sphere",[.5])
    p["root"]={"op":"difference","children":[copy.deepcopy(p["root"]),copy.deepcopy(p["root"])]}
    with pytest.raises(ValueError): g.export_mesh(p)


def test_normalization_roundtrip():
    mesh=g.export_mesh(program("box",[.8,.4,.2]),48)
    mesh.vertices=mesh.vertices*3+[2,3,4]
    norm,t=g.normalize(mesh)
    assert max(norm.extents)==pytest.approx(2)
    assert np.allclose(norm.vertices*t["scale"]+t["center"],mesh.vertices)


def test_identical_geometry_score():
    p=program("box",[.7,.5,.3]); mesh=g.export_mesh(p,64)
    m=g.metrics(p,mesh,mesh,grid=24,count=100,seed=5)
    assert m['voxel_iou_24']>.99
    assert m['surface_distance_p95_relative']<1e-6


@pytest.mark.parametrize('kind,size',[
    ('sphere',[.5]),('box',[.5,.3,.2]),('cylinder',[.4,.6]),
    ('cone',[.5,.2,.6]),('torus',[.6,.15]),('capsule',[.2,.5])])
def test_fields_match_sdfcad_reference(kind,size):
    import sdfcad as sdf
    if kind=='sphere': ref=sdf.sphere(radius=size[0])
    elif kind=='box': ref=sdf.box(size=2*np.array(size))
    elif kind=='cylinder': ref=sdf.capped_cylinder([0,0,-size[1]],[0,0,size[1]],radius=size[0])
    elif kind=='cone': ref=sdf.capped_cone([0,0,-size[2]],[0,0,size[2]],size[0],size[1])
    elif kind=='torus': ref=sdf.torus(*size)
    else: ref=sdf.capsule([0,0,-size[1]],[0,0,size[1]],radius=size[0])
    points=np.random.default_rng(19).uniform(-1.5,1.5,(500,3))
    assert np.allclose(g.field(program(kind,size),points),ref(points).ravel(),atol=1e-8)
