function result = native_matdem_run_coupled_permeability(projectRoot)
%NATIVE_MATDEM_RUN_COUPLED_PERMEABILITY Execute two-way pore3d coupling.
%
% The coupling sequence follows the installed MatDEM reference example:
% p.balance(2), p.fluid2Ball(), then p.d.balance(). Fixed boundary pressures
% are restored before every coupled increment.

arguments
    projectRoot (1,1) string = string(fileparts(fileparts( ...
        mfilename('fullpath'))))
end

requestedConfig = native_matdem_hydromechanical_config(projectRoot);
assert(isfile(requestedConfig.files.stage2_pore_network), ...
    'matdem_microplastic:MissingNativeStage2', ...
    'Run native_matdem_initialize_pore3d before coupled flow.');
loaded = load(requestedConfig.files.stage2_pore_network, ...
    'B', 'd', 'p', 'config', 'manifest', 'environment');
B = loaded.B;
d = loaded.d;
p = loaded.p;
config = loaded.config;
manifest = loaded.manifest;
environment = loaded.environment;

if ~isfolder(config.files.checkpoint_directory)
    mkdir(config.files.checkpoint_directory);
end

d.mo.setGPU(char(config.engine.dem_gpu_mode));
if config.engine.pore_gpu_mode == "on"
    p.setGPU('on');
else
    p.setGPU('off');
end

topPoreId = p.SET.topPoreId;
bottomPoreId = p.SET.bottomPoreId;
topPressure = p.SET.topPressure;
bottomPressure = p.SET.bottomPressure;
sampleIds = d.GROUP.sample;
initialX = gatherValue(d.mo.aX(sampleIds));
initialY = gatherValue(d.mo.aY(sampleIds));
initialZ = gatherValue(d.mo.aZ(sampleIds));

cycleCount = config.coupling.outer_cycles;
cycle = (1:cycleCount).';
simulationTimeS = zeros(cycleCount, 1);
topMassPerStepKg = zeros(cycleCount, 1);
bottomMassPerStepKg = zeros(cycleCount, 1);
massBalanceRelativeError = zeros(cycleCount, 1);
hydraulicConductivityMPerS = zeros(cycleCount, 1);
meanPorePressurePa = zeros(cycleCount, 1);
maximumParticleDisplacementM = zeros(cycleCount, 1);

for cycleIndex = 1:cycleCount
    for stepIndex = 1:config.coupling.steps_per_cycle
        p.pPressure(topPoreId) = topPressure;
        p.pPressure(bottomPoreId) = bottomPressure;
        p.setPressure();
        p.balance(config.coupling.fluid_substeps_per_mechanical_step);
        if p.isCouple
            p.fluid2Ball();
            p.d.balance();
        end
    end

    pressure = gatherValue(p.pPressure);
    assert(all(isfinite(pressure)), ...
        'matdem_microplastic:NativePressureDiverged', ...
        'Nonfinite pore pressure at cycle %d.', cycleIndex);
    poreFlowMass = gatherValue(p.fFlowMass(p.poreFacetIdx));
    topMass = sum(poreFlowMass(topPoreId, :), 'all');
    bottomMass = sum(poreFlowMass(bottomPoreId, :), 'all');
    balanceScale = max([abs(topMass), abs(bottomMass), realmin]);
    balanceError = abs(topMass + bottomMass) ./ balanceScale;

    timeStep = gatherValue(p.dT);
    dischargeM3PerS = abs(bottomMass) ./ timeStep ./ ...
        config.fluid.density_kg_per_m3;
    conductivity = dischargeM3PerS .* config.geometry.height_m ./ ...
        (config.geometry.area_m2 .* config.fluid.head_difference_m);

    currentX = gatherValue(d.mo.aX(sampleIds));
    currentY = gatherValue(d.mo.aY(sampleIds));
    currentZ = gatherValue(d.mo.aZ(sampleIds));
    displacement = sqrt((currentX - initialX).^2 + ...
        (currentY - initialY).^2 + (currentZ - initialZ).^2);

    assert(isfinite(conductivity) && conductivity > 0, ...
        'matdem_microplastic:NativeFlowInvalid', ...
        'Nonpositive hydraulic conductivity at cycle %d.', cycleIndex);
    assert(all(isfinite(currentX)) && all(isfinite(currentY)) && ...
        all(isfinite(currentZ)), ...
        'matdem_microplastic:NativeParticleDiverged', ...
        'Nonfinite particle coordinate at cycle %d.', cycleIndex);

    simulationTimeS(cycleIndex) = cycleIndex .* ...
        config.coupling.steps_per_cycle .* timeStep;
    topMassPerStepKg(cycleIndex) = topMass;
    bottomMassPerStepKg(cycleIndex) = bottomMass;
    massBalanceRelativeError(cycleIndex) = balanceError;
    hydraulicConductivityMPerS(cycleIndex) = conductivity;
    meanPorePressurePa(cycleIndex) = mean(pressure);
    maximumParticleDisplacementM(cycleIndex) = max(displacement);

    if mod(cycleIndex, ...
            config.coupling.checkpoint_every_cycles) == 0
        checkpointPath = fullfile(config.files.checkpoint_directory, ...
            sprintf('cycle_%04d.mat', cycleIndex));
        p.setGPU('off');
        d.mo.setGPU('off');
        save(checkpointPath, 'B', 'd', 'p', 'config', 'manifest', ...
            'environment', 'cycleIndex', '-v7.3');
        d.mo.setGPU(char(config.engine.dem_gpu_mode));
        if config.engine.pore_gpu_mode == "on"
            p.setGPU('on');
        end
    end

    fprintf(['NATIVE_HM_PROGRESS cycle=%d/%d K_m_per_s=%.9g ' ...
        'mass_error=%.3e max_disp_m=%.3e\n'], cycleIndex, cycleCount, ...
        conductivity, balanceError, max(displacement));
end

history = table(cycle, simulationTimeS, topMassPerStepKg, ...
    bottomMassPerStepKg, massBalanceRelativeError, ...
    hydraulicConductivityMPerS, meanPorePressurePa, ...
    maximumParticleDisplacementM, ...
    'VariableNames', ["cycle", "simulation_time_s", ...
    "top_mass_per_step_kg", "bottom_mass_per_step_kg", ...
    "mass_balance_relative_error", ...
    "hydraulic_conductivity_m_per_s", "mean_pore_pressure_pa", ...
    "maximum_particle_displacement_m"]);
writetable(history, config.files.stage3_history);

acceptanceStart = max(config.coupling.minimum_cycles_before_acceptance, ...
    cycleCount - 4);
acceptanceStart = min(acceptanceStart, cycleCount);
acceptedError = max(massBalanceRelativeError(acceptanceStart:end));
summary = struct();
summary.case_name = config.case_name;
summary.status = "pass";
summary.native_matdem_pore3d_prediction = true;
summary.two_way_coupling = true;
summary.fixed_microplastic_only = true;
summary.final_hydraulic_conductivity_m_per_s = ...
    hydraulicConductivityMPerS(end);
summary.final_mass_balance_relative_error = ...
    massBalanceRelativeError(end);
summary.maximum_post_warmup_mass_balance_relative_error = acceptedError;
summary.maximum_particle_displacement_m = ...
    max(maximumParticleDisplacementM);
summary.fluid_time_step_s = gatherValue(p.dT);
summary.total_coupled_steps = config.coupling.outer_cycles .* ...
    config.coupling.steps_per_cycle;
summary.throat_flow_factor = config.fluid.throat_flow_factor;
summary.contact_and_flow_calibration_status = config.materials.status;
summary.timestamp_utc = utcNow();
if acceptedError > config.coupling.mass_balance_relative_tolerance
    summary.status = "fail_mass_balance";
end

p.setGPU('off');
d.mo.setGPU('off');
save(config.files.stage3_result, 'B', 'd', 'p', 'config', ...
    'manifest', 'environment', 'history', 'summary', '-v7.3');
writeNativeJson(config.files.stage3_summary, summary);
result = struct('history', history, 'summary', summary, ...
    'config', config, 'manifest', manifest);

assert(summary.status == "pass", ...
    'matdem_microplastic:NativeMassBalanceFailed', ...
    ['Post-warmup mass-balance error %.3e exceeds tolerance %.3e. ' ...
     'Increase cycles or reduce the fluid time step.'], acceptedError, ...
    config.coupling.mass_balance_relative_tolerance);
fprintf('NATIVE_MATDEM_HM_PASS K_m_per_s=%.9g mass_error=%.3e\n', ...
    summary.final_hydraulic_conductivity_m_per_s, ...
    summary.final_mass_balance_relative_error);
end

function value = gatherValue(value)
try
    value = gather(value);
catch
    value = double(value);
end
end

function writeNativeJson(path, value)
fileId = fopen(path, 'w');
assert(fileId >= 0, 'matdem_microplastic:NativeWriteFailed', ...
    'Could not open JSON output: %s', path);
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', jsonencode(value, PrettyPrint=true));
end

function timestamp = utcNow()
timestamp = string(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));
end
