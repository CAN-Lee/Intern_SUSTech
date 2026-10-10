#!/usr/bin/env python3
"""CLI for the complete RSIAgent mesh-domain protocol."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import logging
import os
import shutil
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
os.environ.setdefault("MPLCONFIGDIR","/tmp/mesh-rsi-mpl")


def configuration(path):
    import yaml
    cfg=yaml.safe_load(Path(path).read_text())
    for k in ["brs_projects","parallel","drs_cycles","drs_projects","learning_seconds","final_seconds","max_primitives","max_depth"]:
        if type(cfg[k]) is not int or cfg[k]<1: raise ValueError(f"{k} must be positive integer")
    os.environ.update(RSI_LLM_MODE="openai",RSI_LLM_BASE_URL=cfg["base_url"],
        RSI_LLM_API_KEY=os.environ.get(cfg["api_key_env"],cfg["api_key_default"]),
        RSI_LLM_TIMEOUT=str(cfg["request_timeout"]),
        RSI_MAX_PRIMITIVES=str(cfg["max_primitives"]), RSI_MAX_DEPTH=str(cfg["max_depth"]))
    return cfg


def preflight(cfg, folder):
    from rsi_mesh.runtime import docker,DockerVM,RoleSession,atomic_json
    import requests
    from PIL import Image
    from llm.client import chat
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    health=requests.get(cfg["base_url"].removesuffix("/v1")+"/health",timeout=10)
    health.raise_for_status()
    server=docker("info","--format","{{.ServerVersion}}").stdout.decode().strip()
    image=docker("image","inspect",cfg["image"],"--format","{{.Id}}").stdout.decode().strip()
    text=chat(cfg["model"],"Follow instructions.","只回复：连接成功",max_tokens=128)
    data=io.BytesIO(); Image.new("RGB",(64,64),(220,30,30)).save(data,format="PNG")
    vision=chat(cfg["model"],"Describe the image briefly.","What color is this square?",image=data.getvalue(),max_tokens=128)
    if "连接成功" not in text or not ("red" in vision.lower() or "红" in vision):
        raise RuntimeError("Text or image capability probe returned unexpected content")
    vm=DockerVM(folder/"container",cfg,memory={"notes.md":b"immutable"},memory_readonly=True)
    try:
        result=vm.run_script("python3","import numpy, scipy, trimesh, rtree; from rsi_mesh.geometry import validate; assert trimesh.ray.has_embree, 'Embree failed to load'; print('geometry ready with Embree')")
        if result.exit_code: raise RuntimeError(result.stdout)
        isolation=vm.run_script("python3","from pathlib import Path\nassert not Path('/var/run/docker.sock').exists()\nassert not Path('/data/lican').exists()\nprint('isolated')")
        if isolation.exit_code: raise RuntimeError(isolation.stdout)
        memory_probe=vm.run_script("python3","from pathlib import Path\np=Path('/home/user/.memory/notes.md')\ntry:\n p.write_text('changed')\nexcept OSError:\n print('read-only enforced')\nelse:\n raise RuntimeError('memory was writable')")
        if memory_probe.exit_code or (vm.memory/"notes.md").read_bytes()!=b"immutable":
            raise RuntimeError("Read-only memory boundary failed")
        role=RoleSession("Actor",folder/"real_agent",cfg)
        role.run("Execute a Python program that writes the text ready into /home/user/evolution_project/ready.txt, then declare done.",vm)
        if (vm.project/"ready.txt").read_text().strip()!="ready": raise RuntimeError("Actual Agent action smoke failed")
    finally: vm.close()
    result={"status":"passed","docker":server,"image":image,"text_response":text,"vision_response":vision,
            "model":cfg["model"],"base_url":cfg["base_url"]}
    atomic_json(folder/"preflight.json",result); print(json.dumps(result,ensure_ascii=False,indent=2))


def provenance(cfg):
    import importlib.metadata
    from rsi_mesh.runtime import UPSTREAM
    revision=subprocess.check_output(["git","-C",str(UPSTREAM),"rev-parse","HEAD"],text=True).strip()
    patch=subprocess.check_output(["git","-C",str(UPSTREAM),"diff"],text=True)
    source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for base in [ROOT/"rsi_mesh",ROOT/"configs",ROOT/"docker"] for p in sorted(base.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    source["run_rsi.py"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    versions={name:importlib.metadata.version(name) for name in
              ['numpy','scipy','trimesh','embreex','scikit-image','rtree','openai','PyYAML']}
    return {"upstream_revision":revision,"upstream_patch_sha256":hashlib.sha256(patch.encode()).hexdigest(),
            "source_hashes":source,"config":cfg,"host_packages":versions},patch


def report(run):
    from rsi_mesh.runtime import atomic_json
    run=Path(run); rows=[]
    for path in sorted(run.glob("cases/*/result.json")):
        r=json.loads(path.read_text()); m=r.get("metrics",{})
        rows.append({"case":path.parent.name,"status":r["status"],"error":r.get("error"),"stages":r.get("stages"),
                     "iou_48":m.get("voxel_iou_48"),"iou_96":m.get("voxel_iou_96"),
                     "p95_relative":m.get("surface_distance_p95_relative"),"primitives":m.get("primitive_count"),"seconds":r.get("seconds")})
    atomic_json(run/"summary.json",rows)
    lines=["# RSI Mesh 重建运行结果","","旧三基元结果仅作历史参考；表示、预算和误差口径不同，不将差值归因于 RSI。", "",
           "| 案例 | 状态 | IoU 48³ | IoU 96³ | 表面 P95/对角线 | 基元数 |", "|---|---|---:|---:|---:|---:|"]
    for r in rows:
        f=lambda k:f"{r[k]:.4f}" if isinstance(r[k],(float,int)) else "—"
        lines.append(f"| {r['case']} | {r['status']} | {f('iou_48')} | {f('iou_96')} | {f('p95_relative')} | {r['primitives'] or '—'} |")
        if r.get("error"): lines.append(f"\n{r['case']} 错误：`{r['error']}`\n")
    usage=[]
    if (run/"usage.jsonl").exists(): usage=[json.loads(x) for x in (run/"usage.jsonl").read_text().splitlines() if x]
    tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in usage)
    lines+= ["",f"已记录模型调用：{len(usage)}；总 token：{tokens}。", "",
              "各案例 events.jsonl 记录阶段事件；result.json 区分预算截断与自然结束。"]
    (run/"报告.md").write_text("\n".join(lines)); return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["preflight","run","resume","report"])
    parser.add_argument("--config",default=str(ROOT/"configs/rsi_standard.yaml"))
    parser.add_argument("--all",action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--run-dir")
    parser.add_argument("--synthetic",action="store_true",help="Real three-phase synthetic acceptance case")
    args=parser.parse_args(); cfg=configuration(args.config)
    from rsi_mesh.runtime import atomic_json
    run=Path(args.run_dir).resolve() if args.run_dir else ROOT/"rsi_runs"/time.strftime("%Y%m%d_%H%M%S")
    if args.command=="report":
        if not args.run_dir: parser.error("report requires --run-dir")
        print(json.dumps(report(run),indent=2)); return
    if args.command=="resume" and not args.run_dir: parser.error("resume requires --run-dir")
    if args.command!="resume": run.mkdir(parents=True,exist_ok=False)
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(run/"runtime.log"),logging.StreamHandler()])
    os.environ["RSI_LLM_USAGE_LOG"]=str(run/"usage.jsonl")
    manifest,patch=provenance(cfg)
    if args.command=="resume":
        previous=json.loads((run/"manifest.json").read_text())
        for key in ["upstream_revision","upstream_patch_sha256","source_hashes","config","host_packages"]:
            if previous[key]!=manifest[key]: raise RuntimeError(f"Cannot resume changed {key}")
    else:
        atomic_json(run/"manifest.json",manifest); (run/"upstream.patch").write_text(patch)
    from rsi_mesh.runtime import docker
    image_id=docker("image","inspect",cfg["image"],"--format","{{.Id}}").stdout.decode().strip()
    if args.command=="resume":
        if read_image_id(run)!=image_id: raise RuntimeError("Container image changed since original run")
    else:
        atomic_json(run/"image.json",{"image_id":image_id})
        shutil.copytree(ROOT/"rsi_mesh",run/"tool_snapshot/rsi_mesh",ignore=shutil.ignore_patterns('__pycache__'))
    cfg["image"]=image_id
    cfg["_tools_root"]=str(run/"tool_snapshot/rsi_mesh")
    if args.command=="preflight": preflight(cfg,run/"preflight"); return
    from rsi_mesh.pipeline import MeshProtocol
    if args.command=="resume":
        cohort=json.loads((run/"cohort.json").read_text())
    elif args.synthetic:
        from rsi_mesh import geometry as g
        fixture=run/"acceptance.obj"
        g.export_mesh({"schema_version":1,"root":{"kind":"box","size":[.7,.5,.35]}}).export(fixture)
        cohort=[{"name":"synthetic_box","path":str(fixture)}]
    elif args.all:
        cohort=[{"name":f"{p.parent.name}_{p.stem}","path":str(p)} for level in ["easy","medium","hard"]
                for p in sorted((ROOT/"fusion360_gallery"/level).glob("*.obj"))]
        if len(cohort)!=9: raise RuntimeError("Expected all nine existing cases")
    elif args.case:
        p=Path(args.case).resolve(); cohort=[{"name":p.stem,"path":str(p)}]
    else: parser.error("run requires --all, --case or --synthetic")
    for item in cohort:
        sha=hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        if "sha256" in item and item["sha256"]!=sha: raise RuntimeError("Input changed since original run")
        item["sha256"]=sha
    atomic_json(run/"cohort.json",cohort)
    failures=0
    for item in cohort:
        os.environ["RSI_LLM_CASE_ID"]=item["name"]
        folder=run/"cases"/item["name"]
        resume=args.command=="resume" and folder.exists()
        if resume and (folder/"result.json").exists() and json.loads((folder/"result.json").read_text())["status"]=="completed": continue
        if resume and not (folder/"learning_boundary.json").exists():
            print(f"Cannot resume {item['name']}: no completed learning boundary",flush=True); failures+=1; continue
        try:
            result=MeshProtocol(folder,item["path"],cfg,resume).run()
        except Exception as exc:
            result={"status":"infrastructure_error","error":f"Preparation failed: {type(exc).__name__}: {exc}"}
            atomic_json(folder/"result.json",result)
        failures+=result["status"]!="completed"
        report(run)
    atomic_json(run/"batch_status.json",{"status":"completed" if not failures else "completed_with_failures","failed_cases":failures,"cases":len(cohort)})
    print(f"Run artifacts: {run}",flush=True)
    if failures: sys.exit(1)


def read_image_id(run):
    return json.loads((run/"image.json").read_text())["image_id"]


if __name__=="__main__": main()
