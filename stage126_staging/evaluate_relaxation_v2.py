"""Versioned evaluator: fixed-point spot checks are a stationarity gate, not evidence-integrity gate."""
import evaluate_relaxation_v1 as v1

v1.OUTPUT=v1.job.EVAL/'independent_evaluation_02'

if __name__=='__main__':v1.main()
