function result = simulate_matdem_two_balls_toy(config)
%SIMULATE_MATDEM_TWO_BALLS_TOY Run MatDEM's native two-ball CPU example.
%
% The setup follows examples2018/user_TwoBalls.m with plotting removed and
% deterministic pass/fail diagnostics added. It verifies the installed
% MatDEM mechanical engine independently of the hydraulic fallback.

arguments
    config (1,1) struct
end

requiredFields = ["step_count", "write_results", "output_directory"];
for fieldName = requiredFields
    assert(isfield(config, fieldName), ...
        'matdem_microplastic:MissingConfig', ...
        'Missing MatDEM core configuration field: %s', fieldName);
end
assert(config.step_count >= 1 && ...
    config.step_count == floor(config.step_count), ...
    'matdem_microplastic:InvalidConfig', ...
    'MatDEM core step_count must be a positive integer.');

fsPath = string(which('fs'));
assert(strlength(fsPath) > 0, ...
    'matdem_microplastic:MissingMatDEMCore', ...
    'MatDEM fs must be on the MATLAB path before running the core toy.');
matdemRoot = string(fileparts(fileparts(fsPath)));
originalDirectory = string(pwd);
restoreDirectory = onCleanup(@() cd(originalDirectory));
cd(matdemRoot);

diameter = 0.1;
radius = diameter / 2;
viscosityRate = 0.1;

modelBuild = build();
modelBuild.name = 'CodexTwoBalls';
movingObject.X = [0; 0];
movingObject.Y = [0; 0];
movingObject.Z = diameter .* [1; 3];
movingObject.R = radius .* [1; 1];
boundaryObject.X = [0; 0];
boundaryObject.Y = [0; 0];
boundaryObject.Z = diameter .* [0; 4];
boundaryObject.R = radius .* [1; 1];

ballMaterial = material('ball');
ballMaterial.setMaterial(7e6, 0.15, 1.5e5, 1e6, 1, ...
    diameter, 1500);
modelBuild.addMaterial(ballMaterial);

modelBuild.aX = [movingObject.X; boundaryObject.X; boundaryObject.X(end)];
modelBuild.aY = [movingObject.Y; boundaryObject.Y; boundaryObject.Y(end)];
modelBuild.aZ = [movingObject.Z; boundaryObject.Z; boundaryObject.Z(end)];
modelBuild.aR = [movingObject.R; boundaryObject.R; ...
    boundaryObject.R(end) / 4];
modelBuild.vRate = viscosityRate;
modelBuild.aNum = length(modelBuild.aR);
modelBuild.mNum = length(movingObject.R);
modelBuild.aMatId = ones(size(modelBuild.aR)) .* ballMaterial.Id;
modelBuild.g = -9.8;
modelBuild.setBuild();

modelBuild.GROUP.lefB = [];
modelBuild.GROUP.rigB = [];
modelBuild.GROUP.froB = [];
modelBuild.GROUP.bacB = [];
modelBuild.GROUP.botB = 3;
modelBuild.GROUP.topB = 4;
modelBuild.setModel();
modelBuild.mo.setGPU('off');

initialZ = modelBuild.mo.aZ(1:2);
initialTimeStep = modelBuild.mo.dT;
if isfinite(initialTimeStep) && initialTimeStep > 0
    integrationAttempted = true;
    modelBuild.balance(1, config.step_count);
    modelBuild.getModel();
    finalZ = modelBuild.aZ(1:2);
else
    integrationAttempted = false;
    finalZ = initialZ;
end
if isprop(modelBuild.mo, 'mVZ')
    finalVelocityZ = modelBuild.mo.mVZ(1:2);
else
    finalVelocityZ = [NaN; NaN];
end

topBallDrop = initialZ(2) - finalZ(2);
stateCandidates = collectStateCandidates(modelBuild.mo);
modelProperties = string(properties(modelBuild.mo));
propertyMatch = ~cellfun('isempty', regexpi(cellstr(modelProperties), ...
    '(^a[XYZ]$)|(^m[A-Z]*[XYZ]$)|(dT)|(totalT)|(step)|(time)|(GPU)'));
matchedProperties = modelProperties(propertyMatch);

positionFinite = all(isfinite(finalZ));
motionDetected = topBallDrop > 0.1 * diameter;

summary = struct();
if ~integrationAttempted
    summary.status = "fail";
    summary.failure_reason = "nonpositive MatDEM time step";
elseif positionFinite && motionDetected
    summary.status = "pass";
    summary.failure_reason = "";
elseif ~positionFinite
    summary.status = "fail";
    summary.failure_reason = "nonfinite particle position";
else
    summary.status = "fail";
    summary.failure_reason = "upper ball motion not detected";
end
summary.backend = "matdem_cpu";
summary.reference_example = "examples2018/user_TwoBalls.m";
summary.step_count = config.step_count;
summary.integration_attempted = integrationAttempted;
summary.initial_time_step_s = initialTimeStep;
summary.final_total_time_s = modelBuild.mo.totalT;
summary.moving_particle_count = modelBuild.mNum;
summary.initial_z_m = initialZ;
summary.final_z_m = finalZ;
summary.final_velocity_z_m_per_s = finalVelocityZ;
summary.upper_ball_drop_m = topBallDrop;
summary.model_property_matches = matchedProperties;
summary.state_candidates = stateCandidates;
summary.timestamp_utc = string(datetime('now', ...
    'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));

result = struct();
result.summary = summary;

if config.write_results
    if ~isfolder(config.output_directory)
        mkdir(config.output_directory);
    end
    save(fullfile(config.output_directory, ...
        'matdem_two_balls_toy_result.mat'), 'result', 'config');
    summaryPath = fullfile(config.output_directory, ...
        'matdem_two_balls_toy_summary.json');
    fileId = fopen(summaryPath, 'w');
    assert(fileId >= 0, 'matdem_microplastic:ResultWriteFailed', ...
        'Could not open MatDEM result JSON: %s', summaryPath);
    cleanupFile = onCleanup(@() fclose(fileId));
    fprintf(fileId, '%s\n', jsonencode(summary, PrettyPrint=true));
end

fprintf('MATDEM_TWO_BALLS_%s upper_ball_drop_m=%.9g steps=%d\n', ...
    upper(summary.status), topBallDrop, config.step_count);
end

function state = collectStateCandidates(modelObject)
candidateNames = ["aX", "aY", "aZ", "mX", "mY", "mZ", ...
    "mDX", "mDY", "mDZ", "mVX", "mVY", "mVZ", ...
    "mGX", "mGY", "mGZ", "dT", "totalT", "step", "time"];
state = struct();
for candidateName = candidateNames
    if ~isprop(modelObject, candidateName)
        continue
    end
    value = modelObject.(candidateName);
    entry = struct();
    entry.class = string(class(value));
    entry.size = double(size(value));
    if isnumeric(value) || islogical(value)
        flattened = value(:).';
        entry.values = double(flattened(1:min(numel(flattened), 20)));
        entry.truncated = numel(flattened) > 20;
    elseif ischar(value) || isstring(value)
        entry.values = string(value);
        entry.truncated = false;
    else
        entry.values = "not serialized";
        entry.truncated = true;
    end
    state.(candidateName) = entry;
end
end
