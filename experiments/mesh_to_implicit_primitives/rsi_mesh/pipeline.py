"""Full mesh RSI protocol, using upstream Phase 1 and Phase 2 state machines."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import time
from types import SimpleNamespace

from .runtime import (DockerVM, RoleSession, BudgetExceeded, atomic_json, tree,
                      install, digest, ROOT, UPSTREAM)
from . import geometry as g
from explore.phase1_wave import evolve_parallel_phase1, WaveDecision, WaveProject, _BranchRuntime
from core.self_evolving_loop import (SelfEvolvingLoopHooks, run_self_evolving_loop,
    ActorLearning, EvolutionResult, EvolutionStatus, TargetVerification, TargetVerdict)
from explore.charter import (self_evolving_actor_memory_distillation_msg,
                            self_evolving_actor_memory_reconciliation_msg)


def read_json(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size > 2_000_000:
        raise ValueError("Unsafe or oversized handoff")
    return json.loads(path.read_text())


def memory_check(files):
    """Representation boundary; semantic memory ownership remains with Actor."""
    if sum(map(len, files.values())) > 2_000_000: raise ValueError("Memory exceeds 2 MB")
    for name, content in files.items():
        if Path(name).suffix not in {".md", ".txt", ".py", ".json"}:
            raise ValueError("Memory allows notes/scripts/JSON, never meshes or binary outputs")
        content.decode("utf-8")
        if Path(name).name in {"program.json", "reconstruction.stl", "mesh.obj"}:
            raise ValueError("Do not carry the target deliverable as memory")
    return files


class MeshProtocol:
    def __init__(self, folder, mesh_path, config, resume=False):
        self.root, self.cfg = Path(folder), config
        self.root.mkdir(parents=True, exist_ok=True)
        self.original=Path(mesh_path).resolve()
        mesh=g.load_mesh(self.original)
        self.target,self.transform=g.normalize(mesh)
        self.input=self.root/"input.obj"
        if not resume:
            self.target.export(self.input)
            atomic_json(self.root/"transform.json",self.transform)
            atomic_json(self.root/"input_summary.json",g.inspect(self.target))
            g.preview(self.target,self.target,self.root/"input.png")
        self.memory=self.root/"memory"; self.memory.mkdir(exist_ok=True)
        self.deadline=time.monotonic()+config["learning_seconds"]
        self.vms=[]
        self.curriculum=RoleSession("Curriculum",self.root/"phase2/curriculum",config)
        self.projects=0; self.target_cycles=0; self.learning_commits=0
        self.phase1_cfg=SimpleNamespace(max_iters=config["agent_turns"])
        self.hooks=SimpleNamespace(install_memory=install, validate_corpus=lambda _:None,
                                   audit_text=lambda *a,**kw:[])
        self.resume=resume
        self.event("PROTOCOL_OPENED", {"resume":resume})

    def event(self, kind, payload=None, **kwargs):
        record={"time":time.time(),"event":kind,"payload":payload or kwargs}
        with (self.root/"events.jsonl").open("a") as f: f.write(json.dumps(record)+"\n")
        print(f"[{self.original.stem}] {kind}", flush=True)

    def vm(self, folder, mesh=None, memory=None, memory_readonly=False):
        if time.monotonic()>=self.deadline: raise BudgetExceeded("phase_wall_budget")
        vm=DockerVM(folder,self.cfg,mesh,memory,self.deadline,memory_readonly)
        self.vms.append(vm); return vm

    def factory(self):
        path=self.root/"phase1/environments"/str(time.time_ns())
        vm=self.vm(path,self.input,tree(self.root/'phase1/memory'),memory_readonly=True)
        return vm,vm

    def push_memory(self,hooks,vm,path):
        if vm.memory_readonly:
            if digest(tree(vm.memory))!=digest(tree(path)): raise RuntimeError("Curriculum memory snapshot mismatch")
        else: install(vm.memory,tree(path))

    def target_instruction(self):
        return ("Reconstruct /input/mesh.obj as an implicit CSG tree. Save the final "
                "schema_version=1 program to /home/user/evolution_project/program.json. "
                "Use geometry and images to reason about missing/excess regions. You own "
                "primitive selection, boolean tree, parameter initialization, revisions and stopping. "
                "Do not just call the historical greedy fitter; it is not installed. "
                f"Requirements: <= {self.cfg['max_primitives']} leaves, depth <= {self.cfg['max_depth']}, "
                f"valid closed nonempty mesh, IoU >= {self.cfg['pass_iou']} at grid 64 and "
                f"symmetric point-to-triangle P95 / input diagonal <= {self.cfg['pass_p95_relative']}. "
                "Freeze candidate program.json before done. Report remaining weaknesses honestly.")

    def curriculum_prompt(self, budget, feedback="", broad=True):
        return ("You select informative synthetic geometry practice for mesh-to-CSG reconstruction. "
            "Study the reference target /input/mesh.obj via tools/rendering. It supplies direction, "
            "not a fixture to copy. Generate prerequisite/contrast/stress shapes using the supported "
            "CSG schema. Do not reconstruct or copy the actual target in these practice projects. "
            "The host will convert your synthetic programs into meshes, keep generating programs "
            "private, and give practice Actors only those meshes. "
            f"Publish /home/user/evolution_project/decision.json with {{\"decision\":\"WAVE\", "
            "\"rationale\":\"...\",\"projects\":[{\"id\":\"short-id\",\"instruction\":\"skills to practice\","
            "\"program\":{\"schema_version\":1,\"root\":...}}]}. "
            f"Choose 1 to {min(2,budget)} independent projects for this wave. "
            + ("If enough diverse knowledge is already learned, publish decision SATURATED with projects: []. " if broad else
               "If the verified target needs no useful further practice, publish decision READY with projects: []; "
               "if no productive practice exists but target remains unsolved, use STALLED. ")
            +"Never change task acceptance thresholds. Choose difficulty and content yourself. "
            "Do not put any generating program or answer in the project instruction. "
            "Feedback from earlier verified work:\n"+feedback)

    def decision(self, session, vm, budget, feedback="", broad=True):
        path=vm.project/"decision.json"
        if path.exists(): path.unlink()
        session.run(self.curriculum_prompt(budget,feedback,broad),vm)
        value=read_json(path)
        if value.get("decision") not in {"WAVE","SATURATED","STALLED","READY"}:
            raise ValueError("Invalid Curriculum decision")
        projects=value.get("projects",[])
        if value["decision"] == "WAVE" and not 1<=len(projects)<=min(2,budget):
            raise ValueError("Curriculum wave violates remaining practice budget")
        if value["decision"] != "WAVE" and projects: raise ValueError("Terminal decision contains projects")
        for p in projects:
            if not p["id"].replace("_","").replace("-","").isalnum(): raise ValueError("Unsafe project ID")
            g.validate(p["program"],self.cfg["max_primitives"],self.cfg["max_depth"])
        if len({p["id"] for p in projects}) != len(projects): raise ValueError("Duplicate project IDs")
        return value

    # The upstream Phase 1 scheduler invokes these domain hooks. It owns the
    # parallel execution barrier, branch error handling and sequential commits.
    def author_wave(self, *, vm, history, sink_root, previous_wave_outcomes, **kw):
        session=RoleSession("Curriculum",sink_root,self.cfg,history)
        state_path=self.root/"phase1/state.json"
        used=read_json(state_path).get("projects",0) if state_path.exists() else 0
        value=self.decision(session,vm,self.cfg["brs_projects"]-used,previous_wave_outcomes,True)
        self.wave_programs=value
        code=value["decision"]
        if code=="READY": raise ValueError("READY is not a Phase 1 decision")
        projects=tuple(WaveProject(p["id"],p["instruction"]) for p in value["projects"])
        return WaveDecision(code,value["rationale"],projects,json.dumps(value)),session.history

    def fixture(self, program, folder):
        folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
        synthetic=g.export_mesh(program)
        normalized,_=g.normalize(synthetic)
        normalized.export(folder/"mesh.obj")
        atomic_json(folder/"generator.host-only.json",program)
        return folder/"mesh.obj"

    def capture_fixtures(self, *, assignments, **kw):
        specs={p["id"]:p for p in self.wave_programs["projects"]}
        for _,project,folder in assignments:
            self.fixture(specs[project.project_id]["program"],folder/"fixtures")

    def work(self, actor, vm, instruction):
        actor.run(instruction,vm)
        return vm.project/"program.json"

    def verify(self, actor_vm, verifier, folder, mesh_path, instruction):
        folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
        try:
            program=read_json(actor_vm.project/"program.json")
            g.validate(program,self.cfg["max_primitives"],self.cfg["max_depth"])
        except (ValueError,FileNotFoundError,KeyError,TypeError) as exc:
            report=f"Invalid or absent candidate program: {exc}"
            atomic_json(folder/"verification.json",{"verdict":"FAIL","report":report})
            return TargetVerification(TargetVerdict.FAIL,report)
        trusted=self.vm(folder/"trusted",mesh_path)
        atomic_json(trusted.project/"program.json",program)
        try:
            result=trusted.run_script("bash", "python -m rsi_mesh.geometry evaluate --mesh /input/mesh.obj --program program.json --out evidence.json", self.cfg["script_timeout"])
            if result.exit_code:
                report="Trusted geometry evaluation failed:\n"+result.stdout
                atomic_json(folder/"verification.json",{"verdict":"FAIL","report":report})
                return TargetVerification(TargetVerdict.FAIL,report)
            evidence=read_json(trusted.project/"evidence.json")
            # Verifier receives only candidate and independently computed evidence.
            view=self.vm(folder/"verifier",mesh_path)
            for name in ["program.json","evidence.json","evidence.png","evidence.stl"]:
                shutil.copyfile(trusted.project/name,view.project/name)
            try:
                verifier.run("Independently verify this candidate against the task. No Actor memory or "
                    "private reasoning is available. Inspect evidence.json and actual geometry; run additional "
                    "checks or Look at evidence.png when useful. Write verdict.json with verdict PASS, FAIL or "
                    "UNVERIFIED and a report citing measured evidence and unmet requirements. "
                    "Do not repair the candidate.\n"+instruction,view)
                v=read_json(view.project/"verdict.json")
            finally: view.close()
            verdict=TargetVerdict(v["verdict"])
            passes=(evidence["voxel_iou_64"] >= self.cfg["pass_iou"] and
                    evidence["surface_distance_p95_relative"] <= self.cfg["pass_p95_relative"] and
                    evidence["reconstructed_watertight"])
            if verdict is TargetVerdict.PASS and not passes:
                verdict=TargetVerdict.FAIL
                v["report"] += "\nHost rejection: precommitted numerical requirements not met."
            report=str(v["report"])+"\nTrusted measurements: "+json.dumps(evidence)
            atomic_json(folder/"verification.json",{"verdict":verdict.value,"report":report,"metrics":evidence})
            return TargetVerification(verdict,report)
        finally: trusted.close()

    def execute_branch(self, *, project_index, project, episode_dir, wave_memory_dir, **kw):
        mesh=episode_dir/"fixtures/mesh.obj"
        memory=tree(wave_memory_dir)
        vm=self.vm(episode_dir/"actor_environment",mesh,memory)
        actor=RoleSession("Actor",episode_dir/"actor",self.cfg)
        verifier=RoleSession("Verifier",episode_dir/"verifier_context",self.cfg)
        instruction=self.target_instruction()+"\nPractice focus: "+project.instruction
        self.work(actor,vm,instruction)
        verification=self.verify(vm,verifier,episode_dir/"verification",mesh,instruction)
        if verification.verdict is TargetVerdict.UNVERIFIED:
            raise RuntimeError("Unresolved branch blocks the whole wave; no memory committed")
        vm.actor_session=actor
        return _BranchRuntime(project_index,project,episode_dir,vm,vm,actor.history,
                              "STATUS: SUBMIT",verification.report,verification.verdict.value,memory)

    def learn(self, actor, vm, memory, verification, folder):
        before=tree(memory); install(vm.memory,before)
        prompt=self_evolving_actor_memory_distillation_msg(verification.verdict.value,verification.report)
        prompt += ("\nStore only reusable notes and scripts in /home/user/.memory. Do not store the input mesh, "
                   "a full target program, target-specific coordinate lists or final output. Preserve uncertainty. "
                   "Allowed UTF-8 extensions: .md .txt .py .json, total <=2 MB. A failed reconstruction "
                   "is useful evidence but is not a verified success.")
        actor.run(prompt,vm)
        actor.run(self_evolving_actor_memory_reconciliation_msg(),vm)
        candidate=memory_check(tree(vm.memory))
        folder=Path(folder)
        install(folder/"before",before); install(folder/"after",candidate)
        record={"before":digest(before),"after":digest(candidate),"verdict":verification.verdict.value}
        atomic_json(folder/"commit.json",record)
        install(memory,candidate)
        self.learning_commits+=1
        self.event("MEMORY_COMMITTED",record)
        return {"before":record["before"],"after":record["after"],
                "changes":{k:("changed" if k in before else "added") for k,v in candidate.items() if before.get(k)!=v}}

    def commit_memory(self, *, branch, canonical_memory_dir, **kw):
        verification=TargetVerification(TargetVerdict(branch.terminal_outcome),branch.verifier_report)
        return self.learn(branch.vm.actor_session,branch.vm,canonical_memory_dir,verification,branch.episode_dir/"memory_commit")

    def phase1(self):
        result=evolve_parallel_phase1(root=str(self.root/"phase1"),target_direction=self.target_instruction(),
            actor_cfg=self.phase1_cfg,curriculum_cfg=self.phase1_cfg,memory_cfg=self.phase1_cfg,
            verifier_control_cfg=self.phase1_cfg,vm_factory=self.factory,corpus_path="mesh-domain:no-benchmark-labels",
            hooks=self.hooks,event_sink=self.event,project_budget=self.cfg["brs_projects"],
            max_parallel=self.cfg["parallel"],target_query_conditioned=True,domain_adapter=self)
        atomic_json(self.root/"phase1/result.json",asdict(result))
        install(self.memory,tree(result.memory_dir))
        if result.status in {"infra","quarantined"}:
            if "BudgetExceeded" in result.reason: raise BudgetExceeded(result.reason)
            raise RuntimeError(result.reason)
        return result.status

    def fresh_target(self, direction, cycle):
        if cycle>self.cfg["drs_cycles"]: raise BudgetExceeded("DRS target cycle budget")
        self.target_cycles=cycle
        folder=self.root/f"phase2/target_{cycle:03d}"
        if folder.exists(): raise RuntimeError("Refuse to overwrite an existing target attempt")
        vm=self.vm(folder,self.input,tree(self.memory))
        vm.cycle=cycle; return vm

    def target_actor(self,memory,cycle):
        return RoleSession("Actor",self.root/f"phase2/target_{cycle:03d}/actor",self.cfg)

    def target_verifier(self,vm,direction,cycle):
        return RoleSession("Verifier",self.root/f"phase2/target_{cycle:03d}/verifier_context",self.cfg)

    def target_work(self,actor,verifier,vm,instruction):
        vm.actor=actor
        for revision in range(3):
            self.work(actor,vm,instruction)
            check=self.verify(vm,verifier,vm.folder/f"check_{revision:03d}",self.input,instruction)
            vm.verification=check
            if check.verdict is TargetVerdict.PASS: break
            instruction="Revise your existing candidate based on independent feedback:\n"+check.report+"\n"+self.target_instruction()
        return str(vm.project/"program.json")

    def target_learn(self,actor,vm,direction,output,verdict,report,memory):
        self.learn(actor,vm,self.memory,TargetVerification(verdict,report),vm.folder/"memory_commit")
        return ActorLearning(tree(self.memory),report)

    def evolve(self,direction,verdict,report,diagnosis,memory,index):
        if self.projects>=self.cfg["drs_projects"]: raise BudgetExceeded("DRS practice budget")
        folder=self.root/f"phase2/evolution_{index:03d}"
        vm=self.vm(folder/"curriculum_environment",self.input,tree(self.memory),memory_readonly=True)
        try:
            decision=self.decision(self.curriculum,vm,self.cfg["drs_projects"]-self.projects,
                                   f"Target verdict: {verdict.value}\n{report}\n{diagnosis}",False)
            atomic_json(folder/"decision.host-only.json",decision)
        finally: vm.close()
        if decision["decision"] != "WAVE":
            if decision["decision"]=="SATURATED": raise ValueError("Phase 2 requires READY or STALLED")
            status=EvolutionStatus.READY_FOR_RETRY if decision["decision"]=="READY" else EvolutionStatus.STALLED
            return EvolutionResult(status,tree(self.memory),0,decision["rationale"])
        count=0
        # DRS is strictly sequential: next practice sees all committed experience.
        for spec in decision["projects"]:
            self.projects+=1; count+=1
            ep=folder/f"practice_{count:03d}"
            self.fixture(spec["program"],ep/"fixtures")
            branch=self.execute_branch(project_index=self.projects,project=WaveProject(spec["id"],spec["instruction"]),
                                       episode_dir=ep,wave_memory_dir=self.memory)
            try: self.commit_memory(branch=branch,canonical_memory_dir=self.memory)
            finally: branch.desktop.close()
        return EvolutionResult(EvolutionStatus.READY_FOR_RETRY,tree(self.memory),count,decision["rationale"])

    def phase2(self):
        hooks=SelfEvolvingLoopHooks(fresh_target_environment=self.fresh_target,
            fresh_target_verifier=self.target_verifier,fresh_target_actor=self.target_actor,
            actor_work=self.target_work,verifier_verify=lambda v,e,d,o:e.verification,
            actor_learn=self.target_learn,evolve=self.evolve,learn_on_pass=True,
            curriculum_after_pass=True,release_target_environment=lambda vm:vm.close(),on_event=self.event)
        result=run_self_evolving_loop(self.target_instruction(),tree(self.memory),hooks)
        result.environment.close()
        atomic_json(self.root/"phase2/result.json",{"termination":result.termination,"verdict":result.verifier_verdict.value,
                    "target_cycles":result.target_cycles,"practice_projects":result.practice_projects})
        return result.termination

    def phase3(self):
        frozen=tree(self.memory); frozen_hash=digest(frozen)
        install(self.root/"frozen_memory",frozen)
        self.deadline=time.monotonic()+self.cfg["final_seconds"]
        self.event("PHASE3_STARTED",{"memory_hash":frozen_hash})
        vm=self.vm(self.root/"phase3/actor_environment",self.input,frozen,memory_readonly=True)
        actor=RoleSession("Actor",self.root/"phase3/actor",self.cfg)
        verifier=RoleSession("Verifier",self.root/"phase3/verifier",self.cfg)
        try:
            instruction=self.target_instruction()+"\nMemory is FROZEN. Work-phase edits will never be committed."
            for revision in range(3):
                self.work(actor,vm,instruction)
                check=self.verify(vm,verifier,self.root/f"phase3/check_{revision:03d}",self.input,instruction)
                if check.verdict is TargetVerdict.PASS: break
                instruction=self.target_instruction()+"\nRepair from feedback: "+check.report
            program=read_json(vm.project/"program.json")
            g.validate(program,self.cfg["max_primitives"],self.cfg["max_depth"])
        finally: vm.close()
        if digest(tree(self.memory))!=frozen_hash or digest(tree(self.root/"frozen_memory"))!=frozen_hash:
            raise RuntimeError("Frozen memory integrity failure")
        # No learning or agent calls occur after the sealed evaluator begins.
        self.event("SEALED_EVALUATION_STARTED")
        reconstructed=g.export_mesh(program)
        measurements=g.metrics(program,self.target,reconstructed,self.cfg["final_grid"],9001)
        # Preserve the original 48^3 evaluation support exactly for historical comparison.
        import numpy as np
        from importlib.util import spec_from_file_location,module_from_spec
        spec=spec_from_file_location("legacy_mesh_fit",ROOT/"fit_cases.py")
        legacy=module_from_spec(spec); spec.loader.exec_module(legacy)
        original_mesh=g.load_mesh(self.original)
        xyz,truth=legacy.evaluation_grid(original_mesh)
        norm=(xyz-np.array(self.transform["center"]))/self.transform["scale"]
        pred=g.field(program,norm)<0
        measurements["voxel_iou_48"]=float((pred&truth).sum()/(pred|truth).sum())
        measurements.update(memory_hash=frozen_hash,verifier_verdict=check.verdict.value,
                            transform=self.transform,coordinate_system="normalized",
                            surface_distances_original_units={k:measurements[k]*self.transform["scale"] for k in ["surface_distance_mean","surface_distance_p95"]})
        final=self.root/"final"; final.mkdir(exist_ok=True)
        program["normalization"]=self.transform
        atomic_json(final/"program.json",program)
        g.preview(self.target,reconstructed,final/"comparison.png")
        reconstructed.vertices=reconstructed.vertices*self.transform["scale"]+self.transform["center"]
        reconstructed.export(final/"reconstruction.stl")
        atomic_json(final/"metrics.json",measurements)
        return measurements

    def run(self):
        statuses={}; started=time.time()
        try:
            if self.resume:
                # Only finished learning is an admissible recovery boundary in v1.
                boundary=read_json(self.root/"learning_boundary.json")
                if digest(tree(self.memory))!=boundary["memory_hash"]: raise RuntimeError("Memory boundary mismatch")
                if (self.root/"phase3").exists():
                    archive=self.root/f"phase3_interrupted_{time.time_ns()}"
                    (self.root/"phase3").rename(archive)
                statuses=boundary["stages"]
            else:
                try:
                    self.event("PHASE1_STARTED"); statuses["phase1"]=self.phase1()
                    self.event("PHASE2_STARTED"); statuses["phase2"]=self.phase2()
                except BudgetExceeded as exc:
                    statuses["learning_truncated"]=str(exc)
                atomic_json(self.root/"learning_boundary.json",{"memory_hash":digest(tree(self.memory)),"stages":statuses})
            measurements=self.phase3()
            result={"status":"completed","stages":statuses,"metrics":measurements,"seconds":time.time()-started}
        except Exception as exc:
            result={"status":"budget_exhausted" if isinstance(exc,BudgetExceeded) else "infrastructure_error",
                    "error":f"{type(exc).__name__}: {exc}","stages":statuses,"seconds":time.time()-started}
            import traceback
            (self.root/"error.txt").write_text(traceback.format_exc())
        finally:
            for vm in self.vms: vm.close()
        atomic_json(self.root/"result.json",result)
        self.event("PROTOCOL_FINISHED",{"status":result["status"]})
        return result
