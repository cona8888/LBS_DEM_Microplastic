"""No-GPU checks of deadline/accounting transparency around original updates."""
import time,unittest
from pathlib import Path
import solve_direct_fields_v1 as run

class Fake:
    calls=[]
    def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs
    def step(self,n):self.calls.append(n);return ('unchanged',n)
    def close(self):pass

class Controls(unittest.TestCase):
    def setUp(self):
        self.original=run.legacy.stage13.CudaCandidateSession
        run.legacy.stage13.CudaCandidateSession=Fake;Fake.calls=[]
    def tearDown(self):run.legacy.stage13.CudaCandidateSession=self.original
    def design(self,cap=3):
        return dict(numerical_cutoff_utc=run.datetime.fromtimestamp(time.time()+30,run.timezone.utc).isoformat(),controls=dict(maximum_total_gpu_updates=cap))
    def test_no_changed_update_operands_or_return(self):
        with run.bounded_sessions(self.design(),Path('not_created')) as count:
            session=run.legacy.stage13.CudaCandidateSession('state','phase','case',tau=.8,threads=256,maximum_steps=3)
            self.assertEqual(session.kwargs,dict(tau=.8,threads=256,maximum_steps=3))
            self.assertEqual([session.step(x) for x in (1,2,3)],[('unchanged',1),('unchanged',2),('unchanged',3)])
            self.assertEqual(count['completed_updates'],3)
        self.assertEqual(Fake.calls,[1,2,3]);self.assertIs(run.legacy.stage13.CudaCandidateSession,Fake)
    def test_shared_budget_and_deadline_fail_before_native_update(self):
        d=self.design(1)
        with run.bounded_sessions(d,Path('not_created')):
            session=run.legacy.stage13.CudaCandidateSession();session.step(1)
            with self.assertRaises(Exception):session.step(2)
        self.assertEqual(Fake.calls,[1])
        d['numerical_cutoff_utc']=run.datetime.fromtimestamp(time.time()-1,run.timezone.utc).isoformat()
        with run.bounded_sessions(d,Path('not_created')):
            with self.assertRaises(Exception):run.legacy.stage13.CudaCandidateSession()
        self.assertEqual(Fake.calls,[1]);self.assertIs(run.legacy.stage13.CudaCandidateSession,Fake)

if __name__=='__main__':unittest.main()
