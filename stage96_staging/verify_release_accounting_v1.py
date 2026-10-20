"""Verify censoring and horizon accounting against hand-computed examples."""
import hashlib
import json
from pathlib import Path

import release_accounting_v1 as model

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT / "stage96_evaluations/accounting_tests_01"


def main():
    plan=[{"id":"a","weight":.25},{"id":"b","weight":.75}]
    def row(status,t,healthy=True):
        return {"status":status,"observed_pv":t,"health_passed":healthy}
    tests=[]
    examples=[
        ("complete",{"a":row("full_window_exit",.2),"b":row("present_at_horizon",2.)},1.,.25,.25),
        ("event_after_query",{"a":row("full_window_exit",.2),"b":row("present_at_horizon",2.)},.1,0.,0.),
        ("unrun_mass",{"a":row("full_window_exit",.2)},1.,.25,1.),
        ("budget_before_query",{"a":row("incomplete_budget",.2),"b":row("present_at_horizon",2.)},1.,0.,.25),
        ("budget_after_query",{"a":row("incomplete_budget",.2),"b":row("present_at_horizon",2.)},.1,0.,0.),
        ("failure_not_retained",{"a":row("numerical_failure",2.,False),"b":row("present_at_horizon",2.)},1.,0.,.25),
        ("short_window_not_retained",{"a":row("present_at_horizon",.1),"b":row("present_at_horizon",2.)},1.,0.,.25),
        ("unhealthy_exit",{"a":row("full_window_exit",.2,False),"b":row("present_at_horizon",2.)},1.,0.,.25),
    ]
    for name,obs,t,lower,upper in examples:
        result=model.release_bounds(plan,obs,t)
        passed=abs(result["release_lower_bound"]-lower)<1e-14 and abs(result["release_upper_bound"]-upper)<1e-14
        tests.append({"name":name,"passed":passed,"result":result})
    for name,bad in (("bad_weights",[{"id":"a","weight":.5}]),
                     ("duplicate_ids",[{"id":"a","weight":.5},{"id":"a","weight":.5}])):
        try:
            model.release_bounds(bad,{},1.)
        except ValueError:
            passed=True
        else:
            passed=False
        tests.append({"name":name,"passed":passed})
    OUT.mkdir(parents=True,exist_ok=False)
    record={"passed":all(t["passed"] for t in tests),"tests":tests,
            "source_hashes":{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (Path(__file__),Path(model.__file__))}}
    path=OUT / "results.json"
    path.write_text(json.dumps(record,indent=2))
    (OUT / "completion.json").write_text(json.dumps({"status":"complete_passed" if record["passed"] else "complete_failed",
        "results_sha256":hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print(json.dumps({"passed":record["passed"],"tests":len(tests)}))
    if not record["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
