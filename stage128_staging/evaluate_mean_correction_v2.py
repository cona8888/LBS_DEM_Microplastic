"""Versioned Stage128 evaluator correcting long-window versus adjacent-row classification."""
import evaluate_mean_correction_v1 as v1
v1.OUTPUT=v1.job.EVAL/'independent_evaluation_02'
if __name__=='__main__':v1.main()
