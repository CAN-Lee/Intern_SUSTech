import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from rsi_mesh.runtime import tree, install, digest
from rsi_mesh.pipeline import memory_check
from core.self_evolving_loop import (SelfEvolvingLoopHooks,run_self_evolving_loop,ActorLearning,
    EvolutionResult,EvolutionStatus,TargetVerification,TargetVerdict)


@pytest.mark.parametrize('status,expected_calls', [(503,3),(400,1)])
def test_gateway_retries_are_bounded_and_preserve_request(monkeypatch,status,expected_calls):
    from types import SimpleNamespace
    from llm import client
    class Failure(Exception):
        status_code=status
        body={'message':'test transport failure'}
    calls=[]
    def create(**kwargs):
        calls.append(kwargs)
        raise Failure()
    monkeypatch.setenv('RSI_LLM_MODE','openai')
    monkeypatch.setattr(client,'_c',lambda:SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(client.time,'sleep',lambda _:None)
    with pytest.raises(client.LLMTransportError):
        client.chat('model','system','user',max_tokens=512)
    assert len(calls)==expected_calls
    assert all(call==calls[0] for call in calls)
    assert calls[0]['max_completion_tokens']==512


def test_memory_snapshots_do_not_alias(tmp_path):
    a,b=tmp_path/'a',tmp_path/'b'
    install(a,{'notes.md':b'first'}); install(b,tree(a))
    before=digest(tree(a)); (b/'notes.md').write_text('edited')
    assert digest(tree(a))==before
    with pytest.raises(ValueError): install(tmp_path/'unsafe',{'../outside':b'x'})
    with pytest.raises(ValueError): memory_check({'mesh.obj':b'v 1 2 3'})


def test_original_phase2_pass_practice_requires_fresh_target():
    events=[]; actors=[]; memories=[]; cycles=[]
    def actor(memory,cycle):
        a=object(); actors.append(a); memories.append(memory); return a
    def learn(a,e,d,o,v,r,m):
        assert a is actors[-1]
        return ActorLearning(m+['learned'],'diagnosis')
    def evolve(d,v,r,diag,m,i):
        return EvolutionResult(EvolutionStatus.READY_FOR_RETRY,m+['practice'] if i==1 else m,1 if i==1 else 0)
    hooks=SelfEvolvingLoopHooks(
        fresh_target_environment=lambda d,c: cycles.append(c) or object(),
        fresh_target_verifier=lambda e,d,c:object(),fresh_target_actor=actor,
        actor_work=lambda a,v,e,d:'candidate',
        verifier_verify=lambda *a:TargetVerification(TargetVerdict.PASS,'checked'),
        actor_learn=learn,evolve=evolve,learn_on_pass=True,curriculum_after_pass=True,
        on_event=lambda e,p:events.append(e))
    result=run_self_evolving_loop('target',[],hooks)
    assert cycles==[1,2] and actors[0] is not actors[1]
    assert memories[1]==['learned','practice']
    assert result.termination=='verifier_pass_curriculum_ready'


def test_failed_wave_never_commits(tmp_path):
    from types import SimpleNamespace
    from explore.phase1_wave import evolve_parallel_phase1,WaveProject,WaveDecision
    class VM:
        def close(self): pass
    commits=[]
    class Adapter:
        def push_memory(self,*a): pass
        def author_wave(self,**kw):
            return WaveDecision('WAVE','test',(WaveProject('a','one'),WaveProject('b','two')),'{}'),[]
        def capture_fixtures(self,**kw): pass
        def execute_branch(self,**kw): raise RuntimeError('isolated branch failed')
        def commit_memory(self,**kw): commits.append(1)
    hooks=SimpleNamespace(install_memory=install,validate_corpus=lambda _:None,audit_text=lambda *a,**k:[])
    result=evolve_parallel_phase1(root=str(tmp_path/'phase1'),target_direction='mesh',actor_cfg=None,
        curriculum_cfg=None,memory_cfg=None,verifier_control_cfg=None,vm_factory=lambda:(VM(),VM()),
        corpus_path='none',hooks=hooks,project_budget=2,domain_adapter=Adapter())
    assert result.status=='infra' and commits==[] and tree(result.memory_dir)=={}


def test_successful_wave_shared_snapshot_and_ordered_commits(tmp_path):
    import time
    from types import SimpleNamespace
    from explore.phase1_wave import evolve_parallel_phase1,WaveProject,WaveDecision,_BranchRuntime
    class VM:
        def close(self): pass
    observed=[]; commits=[]
    class Adapter:
        def push_memory(self,*a): pass
        def author_wave(self,**kw):
            return WaveDecision('WAVE','test',(WaveProject('a','one'),WaveProject('b','two')),'{}'),[]
        def capture_fixtures(self,**kw): pass
        def execute_branch(self,project_index,project,episode_dir,wave_memory_dir,**kw):
            initial=tree(wave_memory_dir); observed.append(digest(initial))
            if project_index==1: time.sleep(.05)  # deliberately reverse completion order
            return _BranchRuntime(project_index,project,episode_dir,VM(),VM(),[],'submitted','checked','PASS',initial)
        def commit_memory(self,branch,canonical_memory_dir,**kw):
            before=tree(canonical_memory_dir)
            assert len(before)==branch.project_index-1
            after={**before,f'{branch.project_index}.md':b'learned'}
            install(canonical_memory_dir,after); commits.append(branch.project_index)
            return {'before':digest(before),'after':digest(after),'changes':{}}
    hooks=SimpleNamespace(install_memory=install,validate_corpus=lambda _:None,audit_text=lambda *a,**k:[])
    result=evolve_parallel_phase1(root=str(tmp_path/'phase1'),target_direction='mesh',actor_cfg=None,
        curriculum_cfg=None,memory_cfg=None,verifier_control_cfg=None,vm_factory=lambda:(VM(),VM()),
        corpus_path='none',hooks=hooks,project_budget=2,domain_adapter=Adapter())
    assert result.status=='budget_exhausted'
    assert observed[0]==observed[1] and commits==[1,2]
    assert len(tree(result.memory_dir))==2
