"""Save the independent evaluator's regression checks without running physics."""
import subprocess
import sys
from pathlib import Path

import corrected_transport_v1 as api


def main():
    output=api.ROOT/"stage115_evaluations/corrected_flow_short_time_20260915/evaluator_regression_01"
    api.require(not output.exists(),"immutable audit already exists")
    test=Path(__file__).with_name("test_evaluate_corrected_diagnostics_v1.py")
    evaluator=Path(__file__).with_name("evaluate_corrected_diagnostics_v1.py")
    result=subprocess.run([sys.executable,"-B",str(test)],capture_output=True,text=True,check=False)
    passed=result.returncode==0 and "Ran 11 tests" in result.stderr
    report={"passed":passed,"test_count":11,"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr,
            "test_sha256":api.sha(test),"evaluator_sha256":api.sha(evaluator),"audit_sha256":api.sha(__file__),
            "design_sha256":api.sha(api.DESIGN),"scope":"Evaluator rejection/unit checks, no trajectory integration."}
    output.mkdir(parents=True)
    api.write(output/"results.json",report)
    api.write(output/"completion.json",{"passed":passed,"results_sha256":api.sha(output/"results.json")})
    print(result.stderr)
    return result.returncode if not passed else 0


if __name__=="__main__":
    raise SystemExit(main())
