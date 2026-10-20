function capabilities = probe_matdem_capabilities(environment)
%PROBE_MATDEM_CAPABILITIES Inspect relevant MatDEM and MATLAB capabilities.
%
% This probe is read-only. Its fixed checks avoid evaluating arbitrary input
% while recording enough evidence to choose a defensible model fidelity.

arguments
    environment (1,1) struct
end

capabilities = struct();
capabilities.pore = functionProbe("pore");
capabilities.pore3d = functionProbe("pore3d");
capabilities.gpu_device = functionProbe("gpuDevice");
capabilities.gpu_device_count = functionProbe("gpuDeviceCount");

try
    capabilities.parallel_computing_toolbox_license = ...
        logical(license('test', 'Distrib_Computing_Toolbox'));
    capabilities.parallel_computing_toolbox_license_message = "";
catch exception
    capabilities.parallel_computing_toolbox_license = false;
    capabilities.parallel_computing_toolbox_license_message = ...
        string(exception.message);
end

products = ver;
capabilities.matlab_products = repmat(struct( ...
    'name', "", 'version', "", 'release', "", 'date', ""), ...
    numel(products), 1);
for productIndex = 1:numel(products)
    capabilities.matlab_products(productIndex).name = ...
        string(products(productIndex).Name);
    capabilities.matlab_products(productIndex).version = ...
        string(products(productIndex).Version);
    capabilities.matlab_products(productIndex).release = ...
        string(products(productIndex).Release);
    capabilities.matlab_products(productIndex).date = ...
        string(products(productIndex).Date);
end

temporaryModelDirectory = fullfile(environment.matdem_root, "TempModel");
modelNames = [ ...
    "PorePermeability1.mat"; ...
    "PorePermeability2.mat"; ...
    "PoreAdsorption1.mat"; ...
    "pore3dTest1.mat"; ...
    "pore3dCoupleTest2.mat"];
capabilities.model_files = repmat(struct( ...
    'name', "", 'path', "", 'exists', false, 'variables', []), ...
    numel(modelNames), 1);
for modelIndex = 1:numel(modelNames)
    modelPath = fullfile(temporaryModelDirectory, modelNames(modelIndex));
    capabilities.model_files(modelIndex).name = modelNames(modelIndex);
    capabilities.model_files(modelIndex).path = modelPath;
    capabilities.model_files(modelIndex).exists = isfile(modelPath);
    if isfile(modelPath)
        variables = whos('-file', modelPath);
        capabilities.model_files(modelIndex).variables = ...
            simplifyVariables(variables);
    end
end

capabilities.timestamp_utc = string(datetime('now', ...
    'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end

function probe = functionProbe(name)
probe = struct();
probe.name = name;
probe.which = string(which(name));
allMatches = which(name, '-all');
if isempty(allMatches)
    probe.which_all = strings(0, 1);
elseif iscell(allMatches)
    probe.which_all = string(allMatches(:));
else
    probe.which_all = string(allMatches);
end
probe.exist_file = exist(name, 'file');
probe.exist_class = exist(name, 'class');
probe.exist_builtin = exist(name, 'builtin');
end

function simplified = simplifyVariables(variables)
simplified = repmat(struct( ...
    'name', "", 'size', [], 'bytes', 0, 'class', ""), ...
    numel(variables), 1);
for variableIndex = 1:numel(variables)
    simplified(variableIndex).name = string(variables(variableIndex).name);
    simplified(variableIndex).size = double(variables(variableIndex).size);
    simplified(variableIndex).bytes = double(variables(variableIndex).bytes);
    simplified(variableIndex).class = string(variables(variableIndex).class);
end
end
