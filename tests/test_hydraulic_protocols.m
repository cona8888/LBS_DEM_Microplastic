function tests = test_hydraulic_protocols
%TEST_HYDRAULIC_PROTOCOLS Verify geometry and hydraulic-test equations.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
projectRoot = string(fileparts(fileparts(mfilename('fullpath'))));
addpath(projectRoot);
setup_matdem_microplastic();
testCase.TestData.projectRoot = projectRoot;
end

function testSpecifiedSpecimenAndProtocols(testCase)
config = microplastic_study_config(testCase.TestData.projectRoot);
verifyEqual(testCase, config.specimen_diameter_m, 0.05, ...
    'AbsTol', eps);
verifyEqual(testCase, config.specimen_length_m, 0.02, ...
    'AbsTol', eps);
verifyEqual(testCase, sort(config.hydraulic_protocols), ...
    sort(["constant_head"; "falling_head"]));
end

function testRecoveryConvergenceAndMobileBalance(testCase)
config = microplastic_study_config(testCase.TestData.projectRoot);
config.write_results = false;
result = simulate_microplastic_permeability_study(config);
verifyLessThan(testCase, max( ...
    result.protocols.constant_head.recovery_relative_error), 1.0e-12);
verifyLessThan(testCase, max( ...
    result.protocols.falling_head.recovery_relative_error), 1.0e-12);
errors = result.protocols.falling_head.verification_normalized_error;
verifyTrue(testCase, all(diff(errors) < 0));
verifyLessThan(testCase, errors(end), 1.0e-2);
verifyTrue(testCase, all( ...
    result.protocols.falling_head.mobile.terminal_head_reached));
verifyLessThan(testCase, max( ...
    result.protocols.falling_head.mobile.mass_balance_relative_error), ...
    1.0e-12);
end
