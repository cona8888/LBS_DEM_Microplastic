function bridgeTimer = start_codex_matlab_bridge()
%START_CODEX_MATLAB_BRIDGE Start a whitelisted file-based MATLAB bridge.
%
% The bridge exists because some restricted clients cannot discover MATLAB's
% shared-engine registry. It accepts JSON requests from control/inbox and
% supports only the actions declared in processBridgeTick. It never evaluates
% arbitrary MATLAB source supplied by a request.

projectRoot = string(fileparts(fileparts(mfilename('fullpath'))));
addpath(projectRoot);
addpath(fullfile(projectRoot, "config"));
addpath(fullfile(projectRoot, "src"));

paths = struct();
paths.root = fullfile(projectRoot, "control");
paths.inbox = fullfile(paths.root, "inbox");
paths.outbox = fullfile(paths.root, "outbox");
paths.processed = fullfile(paths.root, "processed");
paths.status = fullfile(paths.root, "bridge_status.json");

for folder = [paths.root, paths.inbox, paths.outbox, paths.processed]
    if ~isfolder(folder)
        mkdir(folder);
    end
end

if evalin('base', "exist('CODEX_MATLAB_BRIDGE_TIMER','var') == 1")
    existingTimer = evalin('base', 'CODEX_MATLAB_BRIDGE_TIMER');
    if isa(existingTimer, 'timer') && isvalid(existingTimer)
        if strcmp(existingTimer.Running, 'on')
            bridgeTimer = existingTimer;
            fprintf('CODEX_MATLAB_BRIDGE_ALREADY_RUNNING control=%s\n', ...
                paths.root);
            return
        end
        delete(existingTimer);
    end
end

bridgeTimer = timer( ...
    'Name', 'CodexMatDEMBridge', ...
    'ExecutionMode', 'fixedSpacing', ...
    'BusyMode', 'drop', ...
    'Period', 1.0, ...
    'TimerFcn', @(source, event) processBridgeTick( ...
        source, event, projectRoot, paths));
assignin('base', 'CODEX_MATLAB_BRIDGE_TIMER', bridgeTimer);

status = struct();
status.bridge_version = "1.2";
status.state = "running";
status.matlab_version = string(version);
status.matlab_release = string(version('-release'));
status.started_utc = utcNow();
status.control_root = paths.root;
writeJsonAtomic(paths.status, status);
start(bridgeTimer);

fprintf('CODEX_MATLAB_BRIDGE_READY control=%s\n', paths.root);
end

function processBridgeTick(timerObject, ~, projectRoot, paths)
requests = dir(fullfile(paths.inbox, '*.json'));
if isempty(requests)
    return
end

[~, order] = sort({requests.name});
requests = requests(order);

for requestIndex = 1:numel(requests)
    requestPath = fullfile(requests(requestIndex).folder, ...
        requests(requestIndex).name);
    [~, requestStem] = fileparts(requests(requestIndex).name);
    responsePath = fullfile(paths.outbox, ...
        string(requestStem) + ".response.json");

    response = struct();
    response.bridge_version = "1.2";
    response.request_file = string(requests(requestIndex).name);
    response.started_utc = utcNow();
    response.status = "error";
    response.action = "unknown";
    response.request_id = string(requestStem);
    stopRequested = false;

    try
        request = jsondecode(fileread(requestPath));
        assert(isstruct(request) && isscalar(request), ...
            'matdem_microplastic:InvalidBridgeRequest', ...
            'Bridge request must be one JSON object.');
        assert(isfield(request, 'action'), ...
            'matdem_microplastic:MissingBridgeAction', ...
            'Bridge request is missing the action field.');
        if isfield(request, 'request_id')
            response.request_id = string(request.request_id);
        end
        response.action = string(request.action);

        switch response.action
            case "probe_environment"
                environment = setup_matdem_microplastic();
                response.environment = environment;
                response.status = "pass";

            case "probe_matdem_capabilities"
                environment = setup_matdem_microplastic();
                response.environment = environment;
                response.capabilities = probe_matdem_capabilities( ...
                    environment);
                response.status = "pass";

            case "reload_project_functions"
                clear simulate_two_pore_toy
                clear simulate_matdem_two_balls_toy
                clear two_pore_toy_config
                clear simulate_microplastic_permeability_study
                clear simulate_hydraulic_protocols
                clear microplastic_study_config
                clear native_matdem_hydromechanical_config
                clear generate_native_matdem_particle_distribution
                clear build_native_matdem_case_manifest
                response.status = "pass";
                response.message = "Project simulation functions reloaded.";

            case "run_reduced_hydraulic_toy"
                environment = setup_matdem_microplastic();
                config = two_pore_toy_config(projectRoot);
                config.backend = "reduced_hydraulic_network";
                config.run_matdem_core_probe = false;
                result = simulate_two_pore_toy(config);
                response.environment = environment;
                response.summary = result.summary;
                response.output_directory = config.output_directory;
                response.status = "pass";

            case "run_matdem_core_toy"
                environment = setup_matdem_microplastic();
                config = two_pore_toy_config(projectRoot);
                coreConfig = struct();
                coreConfig.step_count = config.matdem_core_step_count;
                coreConfig.write_results = config.write_results;
                coreConfig.output_directory = ...
                    config.matdem_core_output_directory;
                result = simulate_matdem_two_balls_toy(coreConfig);
                response.environment = environment;
                response.summary = result.summary;
                response.output_directory = coreConfig.output_directory;
                response.status = result.summary.status;

            case "run_two_pore_toy"
                environment = setup_matdem_microplastic();
                config = two_pore_toy_config(projectRoot);
                result = simulate_two_pore_toy(config);
                response.environment = environment;
                response.summary = result.summary;
                response.output_directory = config.output_directory;
                response.status = result.summary.status;

            case "run_microplastic_study"
                environment = setup_matdem_microplastic();
                config = microplastic_study_config(projectRoot);
                result = simulate_microplastic_permeability_study(config);
                response.environment = environment;
                response.summary = result.summary;
                response.output_directory = config.output_directory;
                response.status = result.summary.status;

            case "run_project_tests"
                setup_matdem_microplastic();
                testResults = runtests(fullfile(projectRoot, "tests"));
                response.test_count = numel(testResults);
                response.passed_count = sum([testResults.Passed]);
                response.failed_count = sum([testResults.Failed]);
                response.incomplete_count = sum([testResults.Incomplete]);
                response.duration_seconds = sum([testResults.Duration]);
                if response.failed_count == 0 && ...
                        response.incomplete_count == 0
                    response.status = "pass";
                else
                    response.status = "fail";
                end

            case "stop_bridge"
                response.status = "pass";
                response.message = "Bridge stop requested.";
                stopRequested = true;

            otherwise
                error('matdem_microplastic:UnsupportedBridgeAction', ...
                    'Unsupported bridge action: %s', response.action);
        end
    catch exception
        response.status = "error";
        response.error_identifier = string(exception.identifier);
        response.error_message = string(exception.message);
        response.error_stack = exception.stack;
    end

    response.finished_utc = utcNow();
    writeJsonAtomic(responsePath, response);
    archiveRequest(requestPath, requests(requestIndex).name, ...
        paths.processed);

    status = struct();
    status.bridge_version = "1.2";
    status.state = "running";
    status.last_request_id = response.request_id;
    status.last_action = response.action;
    status.last_status = response.status;
    status.updated_utc = response.finished_utc;
    writeJsonAtomic(paths.status, status);

    if stopRequested
        stop(timerObject);
        status.state = "stopped";
        status.updated_utc = utcNow();
        writeJsonAtomic(paths.status, status);
        break
    end
end
end

function archiveRequest(requestPath, requestName, processedDirectory)
processedPath = fullfile(processedDirectory, requestName);
if isfile(processedPath)
    [~, stem, extension] = fileparts(requestName);
    suffix = string(datetime('now', 'TimeZone', 'UTC', ...
        'Format', 'yyyyMMdd''T''HHmmssSSS'));
    processedPath = fullfile(processedDirectory, ...
        string(stem) + "." + suffix + string(extension));
end
[moved, message] = movefile(requestPath, processedPath);
assert(moved, 'matdem_microplastic:BridgeArchiveFailed', ...
    'Could not archive bridge request: %s', message);
end

function writeJsonAtomic(destination, value)
temporaryPath = string(destination) + ".tmp";
fileId = fopen(temporaryPath, 'w');
assert(fileId >= 0, 'matdem_microplastic:BridgeWriteFailed', ...
    'Could not open temporary JSON file: %s', temporaryPath);
try
    fprintf(fileId, '%s\n', jsonencode(value, PrettyPrint=true));
    closeStatus = fclose(fileId);
    assert(closeStatus == 0, 'matdem_microplastic:BridgeCloseFailed', ...
        'Could not close temporary JSON file: %s', temporaryPath);
catch exception
    fclose(fileId);
    rethrow(exception)
end
[moved, message] = movefile(temporaryPath, destination, 'f');
assert(moved, 'matdem_microplastic:BridgeCommitFailed', ...
    'Could not commit JSON file: %s', message);
end

function timestamp = utcNow()
timestamp = string(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end
