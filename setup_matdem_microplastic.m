function environment = setup_matdem_microplastic(options)
%SETUP_MATDEM_MICROPLASTIC Configure project and external MatDEM paths.
%
% This function does not modify the MatDEM installation or save the MATLAB
% path. It configures only the current MATLAB process.

arguments
    options.MatDEMRoot (1,1) string = ...
        "C:\Users\wonjuncha-admin\Downloads\MatDEM\MatDEM5.00(Win&Linux)"
end

projectRoot = string(fileparts(mfilename('fullpath')));
matdemRoot = options.MatDEMRoot;

assert(isfolder(projectRoot), ...
    'matdem_microplastic:MissingProject', ...
    'Project folder does not exist: %s', projectRoot);
assert(isfolder(matdemRoot), ...
    'matdem_microplastic:MissingMatDEM', ...
    'MatDEM folder does not exist: %s', matdemRoot);

projectPaths = [projectRoot; ...
    fullfile(projectRoot, "config"); ...
    fullfile(projectRoot, "src"); ...
    fullfile(projectRoot, "native_matdem"); ...
    fullfile(projectRoot, "scripts"); ...
    fullfile(projectRoot, "tests")];
matdemPaths = [matdemRoot; ...
    fullfile(matdemRoot, "fun"); ...
    fullfile(matdemRoot, "app")];

for pathToAdd = [projectPaths; matdemPaths].'
    if isfolder(pathToAdd)
        addpath(pathToAdd);
    end
end

environment = struct();
environment.project_root = projectRoot;
environment.matdem_root = matdemRoot;
environment.matlab_version = string(version);
environment.matlab_release = string(version('-release'));
environment.fs_path = string(which('fs'));
environment.mfs_path = string(which('mfs'));
environment.pore3d_path = string(which('pore3d'));
environment.timestamp_utc = string(datetime('now', ...
    'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));

try
    gpu = gpuDevice;
    environment.gpu_available = true;
    environment.gpu_name = string(gpu.Name);
    environment.gpu_compute_capability = string(gpu.ComputeCapability);
    environment.gpu_available_memory_bytes = double(gpu.AvailableMemory);
    environment.gpu_message = "";
catch exception
    environment.gpu_available = false;
    environment.gpu_name = "";
    environment.gpu_compute_capability = "";
    environment.gpu_available_memory_bytes = NaN;
    environment.gpu_message = string(exception.message);
end

assert(strlength(environment.fs_path) > 0, ...
    'matdem_microplastic:MissingMatDEMCore', ...
    ['MatDEM function fs was not found after adding %s\fun. ' ...
     'Check that this is a complete MatDEM installation.'], matdemRoot);

if strlength(environment.pore3d_path) == 0
    warning('matdem_microplastic:Pore3dNotExposed', ...
        ['MatDEM pore3d is not currently visible to MATLAB. Auto mode ' ...
         'will use the labelled reduced hydraulic-network verification; ' ...
         'native pore3d runs require the missing MatDEM pore module.']);
end

fprintf('MATDEM_PROJECT_ROOT=%s\n', environment.project_root);
fprintf('MATDEM_ROOT=%s\n', environment.matdem_root);
fprintf('MATLAB_RELEASE=%s\n', environment.matlab_release);
fprintf('MATDEM_PORE3D_PATH=%s\n', environment.pore3d_path);
if environment.gpu_available
    fprintf('MATLAB_GPU=%s\n', environment.gpu_name);
else
    fprintf('MATLAB_GPU_UNAVAILABLE=%s\n', environment.gpu_message);
end
end
