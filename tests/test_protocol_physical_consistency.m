function tests = test_protocol_physical_consistency
%TEST_PROTOCOL_PHYSICAL_CONSISTENCY Check the direction of clogging effects.
tests = functiontests(localfunctions);
end

function testCloggingDoesNotAccelerateFallingHead(testCase)
projectRoot = string(fileparts(fileparts(mfilename('fullpath'))));
addpath(projectRoot);
setup_matdem_microplastic();
config = microplastic_study_config(projectRoot);
config.write_results = false;
result = simulate_microplastic_permeability_study(config);
verifyGreaterThanOrEqual(testCase, ...
    result.protocols.falling_head.mobile.duration_s, ...
    result.protocols.falling_head.time_to_terminal_head_s);
end
