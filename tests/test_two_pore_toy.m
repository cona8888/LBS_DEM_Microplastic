function tests = test_two_pore_toy
%TEST_TWO_PORE_TOY MATLAB unit test for the MatDEM pore-network probe.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
projectRoot = string(fileparts(fileparts(mfilename('fullpath'))));
addpath(projectRoot);
testCase.TestData.environment = setup_matdem_microplastic();
testCase.TestData.projectRoot = projectRoot;
end

function testPressureEquilibrates(testCase)
config = two_pore_toy_config(testCase.TestData.projectRoot);
config.write_results = false;
config.run_matdem_core_probe = false;
result = simulate_two_pore_toy(config);

verifyEqual(testCase, result.summary.status, "pass");
verifyGreaterThan(testCase, ...
    result.summary.initial_pressure_difference_pa, 0);
verifyLessThan(testCase, ...
    result.summary.final_pressure_difference_pa, ...
    result.summary.initial_pressure_difference_pa);
verifyTrue(testCase, all(isfinite(result.pressure_pa), 'all'));
verifyLessThan(testCase, ...
    result.summary.mass_balance_relative_error, 1.0e-12);
if result.summary.backend == "reduced_hydraulic_network"
    verifyLessThan(testCase, ...
        result.summary.max_analytical_pressure_error_normalized, 1.0e-2);
end
end

function testNativeProbeExcludedFromDefault(testCase)
config = two_pore_toy_config(testCase.TestData.projectRoot);
verifyFalse(testCase, config.run_matdem_core_probe, ...
    ['The protected MatDEM balance path is intentionally excluded from ' ...
     'the default suite until it advances physical time without a modal.']);
end
