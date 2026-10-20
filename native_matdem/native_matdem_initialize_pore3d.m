function output = native_matdem_initialize_pore3d(projectRoot)
%NATIVE_MATDEM_INITIALIZE_PORE3D Build and saturate the 3D pore network.

arguments
    projectRoot (1,1) string = string(fileparts(fileparts( ...
        mfilename('fullpath'))))
end

requestedConfig = native_matdem_hydromechanical_config(projectRoot);
setup_matdem_microplastic(MatDEMRoot=requestedConfig.engine.matdem_root);
assert(isfile(requestedConfig.files.stage1_specimen), ...
    'matdem_microplastic:MissingNativeStage1', ...
    'Run native_matdem_prepare_specimen before pore initialization.');
assert(strlength(string(which('pore3d'))) > 0, ...
    'matdem_microplastic:Pore3dNotExposed', ...
    ['pore3d is not exposed in this MATLAB session. Run this stage in ' ...
     'the standalone MatDEM application.']);

loaded = load(requestedConfig.files.stage1_specimen, ...
    'B', 'd', 'config', 'manifest', 'environment');
B = loaded.B;
d = loaded.d;
config = loaded.config;
manifest = loaded.manifest;
environment = loaded.environment;

d.calculateData();
d.mo.setGPU('off');
d.getModel();
d.resetStatus();

p = pore3d(d);
p.setInitialPores();
p.fKFlow(:) = config.fluid.throat_flow_factor;
p.setTimeStep();
p.dT = p.dT .* config.fluid.time_step_scale;

topPoreId = unique(p.facetP(p.GROUP.topF, 1));
bottomPoreId = unique(p.facetP(p.GROUP.botF, 1));
assert(~isempty(topPoreId) && ~isempty(bottomPoreId), ...
    'matdem_microplastic:MissingPressureBoundary', ...
    'pore3d did not identify both top and bottom pore boundaries.');

referencePressure = p.Fluids.refP;
topPressure = referencePressure + config.fluid.pressure_difference_pa;
bottomPressure = referencePressure;
p.pPressure(topPoreId) = topPressure;
p.pPressure(bottomPoreId) = bottomPressure;
p.setPressure();
p.SET.totalMass0 = sum(p.pMass);
p.SET.topPoreId = topPoreId;
p.SET.bottomPoreId = bottomPoreId;
p.SET.topPressure = topPressure;
p.SET.bottomPressure = bottomPressure;
p.SET.initialPoreVolume = p.pVol;
p.setCouple('on');

p.setGPU('off');
d.mo.setGPU('off');
summary = struct();
summary.status = "native_stage2_completed";
summary.case_name = config.case_name;
summary.pore_count = numel(p.pPressure);
summary.flow_connection_count = numel(p.fKFlow);
summary.top_boundary_pore_count = numel(topPoreId);
summary.bottom_boundary_pore_count = numel(bottomPoreId);
summary.reference_pressure_pa = referencePressure;
summary.pressure_difference_pa = config.fluid.pressure_difference_pa;
summary.fluid_time_step_s = p.dT;
summary.throat_flow_factor = config.fluid.throat_flow_factor;
summary.two_way_coupling = logical(p.isCouple);
summary.timestamp_utc = utcNow();

save(config.files.stage2_pore_network, 'B', 'd', 'p', 'config', ...
    'manifest', 'environment', 'summary', '-v7.3');
writeNativeJson(config.files.stage2_summary, summary);
output = struct('B', B, 'd', d, 'p', p, 'config', config, ...
    'manifest', manifest, 'environment', environment, 'summary', summary);
fprintf('NATIVE_MATDEM_STAGE2_PASS pores=%d connections=%d\n', ...
    summary.pore_count, summary.flow_connection_count);
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
