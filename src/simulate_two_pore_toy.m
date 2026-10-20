function result = simulate_two_pore_toy(config)
%SIMULATE_TWO_PORE_TOY Verify pressure equilibration with an available backend.
%
% backend="auto" uses MatDEM pore3d when that class is installed. Otherwise
% it uses a transparent two-reservoir hydraulic model and labels the result
% reduced_hydraulic_network. The reduced model is a verification fallback,
% not a claim that MatDEM pore3d was executed.

arguments
    config (1,1) struct
end

requiredFields = ["backend", "particle_radius_m", ...
    "pressure_gradient_pa_per_m", "rate_scale", "step_count", ...
    "fluid_dynamic_viscosity_pa_s", ...
    "fluid_compressibility_pa_inverse", "pore_volume_m3", ...
    "throat_radius_m", "throat_length_m", ...
    "time_step_fraction_of_pressure_time_constant", ...
    "run_matdem_core_probe", "matdem_core_step_count", ...
    "write_results", "output_directory", ...
    "matdem_core_output_directory"];
for fieldName = requiredFields
    assert(isfield(config, fieldName), ...
        'matdem_microplastic:MissingConfig', ...
        'Missing configuration field: %s', fieldName);
end

validateConfig(config);
backend = selectBackend(string(config.backend));
geometry = createTwoPoreGeometry(config.particle_radius_m);

switch backend
    case "matdem_pore3d"
        result = runMatDEMPore3d(config, geometry);
    case "reduced_hydraulic_network"
        result = runReducedHydraulicNetwork(config, geometry);
    otherwise
        error('matdem_microplastic:UnsupportedPoreBackend', ...
            'Unsupported pore backend: %s', backend);
end

if config.run_matdem_core_probe
    coreConfig = struct();
    coreConfig.step_count = config.matdem_core_step_count;
    coreConfig.write_results = config.write_results;
    coreConfig.output_directory = config.matdem_core_output_directory;
    try
        result.matdem_core = simulate_matdem_two_balls_toy(coreConfig);
        result.summary.matdem_core_status = ...
            result.matdem_core.summary.status;
        result.summary.matdem_core_backend = ...
            result.matdem_core.summary.backend;
        if result.matdem_core.summary.status ~= "pass"
            result.summary.status = "partial_pass";
        end
    catch exception
        result.matdem_core = struct();
        result.matdem_core.summary = struct();
        result.matdem_core.summary.status = "error";
        result.matdem_core.summary.backend = "matdem_cpu";
        result.matdem_core.summary.error_identifier = ...
            string(exception.identifier);
        result.matdem_core.summary.error_message = string(exception.message);
        result.matdem_core.error_stack = exception.stack;
        result.summary.status = "partial_pass";
        result.summary.matdem_core_status = "error";
        result.summary.matdem_core_backend = "matdem_cpu";
        result.summary.matdem_core_error_identifier = ...
            string(exception.identifier);
        result.summary.matdem_core_error_message = string(exception.message);
        warning('matdem_microplastic:MatDEMCoreProbeFailed', ...
            ['Reduced hydraulic verification passed, but the native ' ...
             'MatDEM core probe failed: %s'], exception.message);
    end
else
    result.summary.matdem_core_status = "not_run";
    result.summary.matdem_core_backend = "not_run";
end

if config.write_results
    writeResult(config.output_directory, result, config);
end

fprintf(['TWO_PORE_TOY_PASS backend=%s initial_delta_pa=%.9g ' ...
    'final_delta_pa=%.9g reduction_ratio=%.9g mass_error=%.3e ' ...
    'overall_status=%s\n'], ...
    result.summary.backend, ...
    result.summary.initial_pressure_difference_pa, ...
    result.summary.final_pressure_difference_pa, ...
    result.summary.pressure_reduction_ratio, ...
    result.summary.mass_balance_relative_error, result.summary.status);
end

function backend = selectBackend(requestedBackend)
pore3dAvailable = exist('pore3d', 'class') == 8 || ...
    exist('pore3d', 'file') ~= 0;
switch requestedBackend
    case "auto"
        if pore3dAvailable
            backend = "matdem_pore3d";
        else
            backend = "reduced_hydraulic_network";
        end
    case "matdem_pore3d"
        assert(pore3dAvailable, ...
            'matdem_microplastic:Pore3dUnavailable', ...
            ['MatDEM pore3d was requested but is not visible in this ' ...
             'MATLAB process.']);
        backend = requestedBackend;
    case "reduced_hydraulic_network"
        backend = requestedBackend;
    otherwise
        error('matdem_microplastic:UnsupportedPoreBackend', ...
            'Unsupported pore backend: %s', requestedBackend);
end
end

function validateConfig(config)
positiveFiniteFields = ["particle_radius_m", ...
    "pressure_gradient_pa_per_m", "rate_scale", ...
    "fluid_dynamic_viscosity_pa_s", ...
    "fluid_compressibility_pa_inverse", "pore_volume_m3", ...
    "throat_radius_m", "throat_length_m", ...
    "time_step_fraction_of_pressure_time_constant"];
for fieldName = positiveFiniteFields
    value = config.(fieldName);
    assert(isscalar(value) && isfinite(value) && value > 0, ...
        'matdem_microplastic:InvalidConfig', ...
        '%s must be positive and finite.', fieldName);
end
assert(config.step_count >= 1 && ...
    config.step_count == floor(config.step_count), ...
    'matdem_microplastic:InvalidConfig', ...
    'step_count must be a positive integer.');
assert(config.matdem_core_step_count >= 1 && ...
    config.matdem_core_step_count == floor(config.matdem_core_step_count), ...
    'matdem_microplastic:InvalidConfig', ...
    'matdem_core_step_count must be a positive integer.');
assert(config.time_step_fraction_of_pressure_time_constant < 1, ...
    'matdem_microplastic:InvalidConfig', ...
    ['time_step_fraction_of_pressure_time_constant must be below 1 ' ...
     'for monotone explicit equilibration.']);
end

function geometry = createTwoPoreGeometry(radius)
ringRadius = radius / cosd(30);
height = sqrt((2 * radius)^2 - ringRadius^2);
theta = linspace(0, 360, 4);
theta = theta(1:end-1).';

geometry.x_m = ringRadius .* [0; cosd(theta); 0];
geometry.y_m = ringRadius .* [0; sind(theta); 0];
geometry.z_m = height .* [-1; zeros(3,1); 1];
geometry.radius_m = ones(size(geometry.x_m)) .* radius;
end

function result = runMatDEMPore3d(config, geometry)
poreModel = pore3d(geometry.x_m, geometry.y_m, geometry.z_m, ...
    geometry.radius_m);
poreModel.setInitialPores();
assert(numel(poreModel.pPressure) >= 2, ...
    'matdem_microplastic:InsufficientPores', ...
    'Expected at least two pores, but MatDEM produced %d.', ...
    numel(poreModel.pPressure));

referencePressure = poreModel.pPressure(1);
pressureIncrement = config.pressure_gradient_pa_per_m * ...
    (2 * config.particle_radius_m);
poreModel.pPressure(1) = referencePressure + pressureIncrement;
poreModel.setPressure();
poreModel.dT = 1.0e-11 / config.rate_scale;

time = poreModel.dT .* (0:config.step_count).';
pressureHistory = zeros(config.step_count + 1, ...
    numel(poreModel.pPressure));
pressureHistory(1,:) = poreModel.pPressure(:).';
if isprop(poreModel, 'pMass')
    initialTotalMass = sum(poreModel.pMass, 'all');
else
    initialTotalMass = NaN;
end

for stepIndex = 1:config.step_count
    poreModel.balance();
    pressureHistory(stepIndex + 1,:) = poreModel.pPressure(:).';
    assert(all(isfinite(poreModel.pPressure)), ...
        'matdem_microplastic:NonfinitePressure', ...
        'Nonfinite pore pressure detected at step %d.', stepIndex);
end

if isprop(poreModel, 'pMass')
    finalTotalMass = sum(poreModel.pMass, 'all');
    massError = abs(finalTotalMass - initialTotalMass) / ...
        max(abs(initialTotalMass), eps);
else
    finalTotalMass = NaN;
    massError = NaN;
end

result = assembleResult("matdem_pore3d", geometry, time, ...
    pressureHistory, initialTotalMass, finalTotalMass, massError, NaN, ...
    struct());
end

function result = runReducedHydraulicNetwork(config, geometry)
viscosity = config.fluid_dynamic_viscosity_pa_s;
throatRadius = config.throat_radius_m;
throatLength = config.throat_length_m;
conductance = pi * throatRadius^4 / (8 * viscosity * throatLength);
storageCompliance = config.fluid_compressibility_pa_inverse * ...
    config.pore_volume_m3;
pressureTimeConstant = storageCompliance / (2 * conductance);
timeStep = config.time_step_fraction_of_pressure_time_constant * ...
    pressureTimeConstant / config.rate_scale;
time = timeStep .* (0:config.step_count).';

pressureIncrement = config.pressure_gradient_pa_per_m * ...
    (2 * config.particle_radius_m);
pressureHistory = zeros(config.step_count + 1, 2);
pressureHistory(1,:) = [pressureIncrement, 0];
flowHistory = zeros(config.step_count, 1);

for stepIndex = 1:config.step_count
    pressureDifference = pressureHistory(stepIndex,1) - ...
        pressureHistory(stepIndex,2);
    flowHistory(stepIndex) = conductance * pressureDifference;
    transferredVolume = flowHistory(stepIndex) * timeStep;
    pressureHistory(stepIndex + 1,1) = ...
        pressureHistory(stepIndex,1) - ...
        transferredVolume / storageCompliance;
    pressureHistory(stepIndex + 1,2) = ...
        pressureHistory(stepIndex,2) + ...
        transferredVolume / storageCompliance;
    assert(all(isfinite(pressureHistory(stepIndex + 1,:))), ...
        'matdem_microplastic:NonfinitePressure', ...
        'Nonfinite reduced-model pressure at step %d.', stepIndex);
end

initialStoredVolume = storageCompliance * sum(pressureHistory(1,:));
finalStoredVolume = storageCompliance * sum(pressureHistory(end,:));
massError = abs(finalStoredVolume - initialStoredVolume) / ...
    max(abs(initialStoredVolume), realmin);

meanPressure = mean(pressureHistory(1,:));
initialDifference = pressureHistory(1,1) - pressureHistory(1,2);
analyticalDifference = initialDifference .* exp( ...
    -2 * conductance .* time ./ storageCompliance);
analyticalPressure = [ ...
    meanPressure + 0.5 .* analyticalDifference, ...
    meanPressure - 0.5 .* analyticalDifference];
maxAnalyticalErrorNormalized = max(abs( ...
    pressureHistory - analyticalPressure), [], 'all') / ...
    max(abs(initialDifference), eps);

assert(massError < 1.0e-12, ...
    'matdem_microplastic:MassBalanceFailed', ...
    'Reduced hydraulic storage balance error is %.3e.', massError);
assert(maxAnalyticalErrorNormalized < 1.0e-2, ...
    'matdem_microplastic:AnalyticalCheckFailed', ...
    'Reduced hydraulic analytical error is %.3e.', ...
    maxAnalyticalErrorNormalized);

details = struct();
details.throat_conductance_m3_per_pa_s = conductance;
details.storage_compliance_m3_per_pa = storageCompliance;
details.pressure_time_constant_s = pressureTimeConstant;
details.flow_m3_per_s = flowHistory;
details.analytical_pressure_pa = analyticalPressure;
result = assembleResult("reduced_hydraulic_network", geometry, time, ...
    pressureHistory, initialStoredVolume, finalStoredVolume, massError, ...
    maxAnalyticalErrorNormalized, details);
end

function result = assembleResult(backend, geometry, time, pressureHistory, ...
    initialTotal, finalTotal, massError, analyticalError, details)
initialDifference = abs(pressureHistory(1,1) - pressureHistory(1,2));
finalDifference = abs(pressureHistory(end,1) - pressureHistory(end,2));
reductionRatio = finalDifference / initialDifference;
assert(all(isfinite(pressureHistory), 'all') && ...
    isfinite(reductionRatio) && reductionRatio < 1, ...
    'matdem_microplastic:ToyFailed', ...
    ['Two-pore toy did not equilibrate: initial pressure ' ...
     'difference=%g Pa, final pressure difference=%g Pa.'], ...
    initialDifference, finalDifference);

summary = struct();
summary.status = "pass";
summary.backend = backend;
summary.scope = "two-pore pressure-equilibration verification";
summary.particle_count = numel(geometry.radius_m);
summary.pore_count = size(pressureHistory, 2);
summary.step_count = numel(time) - 1;
summary.time_step_s = time(2) - time(1);
summary.initial_pressure_difference_pa = initialDifference;
summary.final_pressure_difference_pa = finalDifference;
summary.pressure_reduction_ratio = reductionRatio;
summary.initial_total_storage_or_mass = initialTotal;
summary.final_total_storage_or_mass = finalTotal;
summary.mass_balance_relative_error = massError;
summary.max_analytical_pressure_error_normalized = analyticalError;
summary.timestamp_utc = string(datetime('now', ...
    'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));

result = struct();
result.summary = summary;
result.time_s = time;
result.pressure_pa = pressureHistory;
result.particle_x_m = geometry.x_m;
result.particle_y_m = geometry.y_m;
result.particle_z_m = geometry.z_m;
result.particle_radius_m = geometry.radius_m;
result.details = details;
end

function writeResult(outputDirectory, result, config)
if ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
save(fullfile(outputDirectory, 'two_pore_toy_result.mat'), ...
    'result', 'config');
summaryPath = fullfile(outputDirectory, 'two_pore_toy_summary.json');
fileId = fopen(summaryPath, 'w');
assert(fileId >= 0, 'matdem_microplastic:ResultWriteFailed', ...
    'Could not open result JSON for writing: %s', summaryPath);
cleanupFile = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', jsonencode(result.summary, PrettyPrint=true));
end
