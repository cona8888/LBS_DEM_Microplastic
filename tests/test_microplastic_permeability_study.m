function tests = test_microplastic_permeability_study
%TEST_MICROPLASTIC_PERMEABILITY_STUDY Verify reduced study invariants.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
projectRoot = string(fileparts(fileparts(mfilename('fullpath'))));
addpath(projectRoot);
setup_matdem_microplastic();
testCase.TestData.projectRoot = projectRoot;
end

function testCleanSphereBenchmark(testCase)
config = microplastic_study_config(testCase.TestData.projectRoot);
config.write_results = false;
result = simulate_microplastic_permeability_study(config);
verifyLessThan(testCase, ...
    result.summary.clean_benchmark_relative_error, 1.0e-12);
end

function testLeightonBuzzardFractionBInputs(testCase)
config = microplastic_study_config(testCase.TestData.projectRoot);
expectedVoidRatio = 0.79 - 0.50 .* (0.79 - 0.46);
expectedPorosity = expectedVoidRatio ./ (1 + expectedVoidRatio);

verifyEqual(testCase, config.sand_name, ...
    "Leighton Buzzard sand, Fraction B");
verifyEqual(testCase, config.sand_d10_m, 0.65e-3, ...
    'AbsTol', 1.0e-15);
verifyEqual(testCase, config.sand_d50_m, 0.82e-3, ...
    'AbsTol', 1.0e-15);
verifyEqual(testCase, config.sand_uniformity_coefficient, 1.38, ...
    'AbsTol', 1.0e-15);
verifyEqual(testCase, config.sand_void_ratio, expectedVoidRatio, ...
    'AbsTol', 1.0e-15);
verifyEqual(testCase, config.clean_porosity, expectedPorosity, ...
    'AbsTol', 1.0e-15);
verifyEqual(testCase, config.microplastic_diameter_m ./ ...
    config.sand_d50_m, 0.30, 'AbsTol', 1.0e-15);
verifyEqual(testCase, config.fixed_volume_fraction, [0; 0.01], ...
    'AbsTol', 1.0e-15);
end

function testSmallerFixedInclusionsReducePermeability(testCase)
config = microplastic_study_config(testCase.TestData.projectRoot);
config.write_results = false;
result = simulate_microplastic_permeability_study(config);
verifyTrue(testCase, all(diff( ...
    result.fixed.intrinsic_permeability_m2) < 0));
end

function testMobileMassBalanceAndClogging(testCase)
config = microplastic_study_config(testCase.TestData.projectRoot);
config.write_results = false;
result = simulate_microplastic_permeability_study(config);
verifyLessThan(testCase, max( ...
    result.mobile.mass_balance_relative_error), 1.0e-12);
verifyTrue(testCase, all( ...
    result.mobile.intrinsic_permeability_m2(end,:) < ...
    result.mobile.intrinsic_permeability_m2(1,:)));
end
