function output = native_matdem_prepare_specimen(projectRoot)
%NATIVE_MATDEM_PREPARE_SPECIMEN Build the mixed cylindrical DEM specimen.
%
% This stage must run in the standalone MatDEM runtime. It creates randomly
% located shrunken particles and expands them frictionlessly to the target
% grading and solid volume inside rough cylindrical walls.

arguments
    projectRoot (1,1) string = string(fileparts(fileparts( ...
        mfilename('fullpath'))))
end

config = native_matdem_hydromechanical_config(projectRoot);
environment = setup_matdem_microplastic( ...
    MatDEMRoot=config.engine.matdem_root);
assert(strlength(string(which('obj_Box'))) > 0 && ...
    strlength(string(which('mfs'))) > 0, ...
    'matdem_microplastic:NativeMatDEMUnavailable', ...
    'MatDEM obj_Box and mfs must be visible in the active runtime.');
if config.engine.dem_gpu_mode == "on"
    assert(environment.gpu_available, ...
        'matdem_microplastic:NativeGPUUnavailable', ...
        ['The native case requests GPU mode, but gpuDevice is unavailable: ' ...
         '%s Run inside the GPU-enabled standalone MatDEM runtime or ' ...
         'install MATLAB Parallel Computing Toolbox.'], ...
        environment.gpu_message);
end

if ~isfolder(config.output_directory)
    mkdir(config.output_directory);
end

particles = generate_native_matdem_particle_distribution(config);
manifest = build_native_matdem_case_manifest(config);
rng(config.random_seed, 'twister');
fs.randSeed(config.random_seed);

B = obj_Box();
B.name = char(config.case_name);
B.GPUstatus = char(config.engine.dem_gpu_mode);
B.ballR = config.boundary.wall_particle_diameter_m ./ 2;
B.isSample = 0;
B.sampleW = config.geometry.diameter_m;
B.sampleL = config.geometry.diameter_m;
B.sampleH = config.geometry.height_m;
B.boundaryStatus = [0, 0, 0, 0, 0, 1];
B.buildInitialModel();
d = B.d;
d.mo.setGPU('off');
d.showB = 3;

wallRadius = config.boundary.wall_particle_diameter_m ./ 2;
denseRate = config.boundary.wall_dense_rate;
specimenRadius = config.geometry.diameter_m ./ 2;
specimenHeight = config.geometry.height_m;

tube = mfs.denseModel(denseRate, @mfs.makeTube, ...
    specimenRadius + wallRadius, specimenHeight, wallRadius);
tube = mfs.moveObj2Origin(tube);
tube = mfs.align2Value('bottom', tube, 0);
tube.groupId = ones(size(tube.X));

bottomDisc = mfs.denseModel(denseRate, @mfs.makeDisc, ...
    specimenRadius + 2 .* wallRadius, wallRadius);
bottomDisc = mfs.moveObj2Origin(bottomDisc);
bottomDisc = mfs.align2Value('top', bottomDisc, 0);
bottomDisc.groupId = 2 .* ones(size(bottomDisc.X));

topDisc = mfs.denseModel(denseRate, @mfs.makeDisc, ...
    specimenRadius + 2 .* wallRadius, wallRadius);
topDisc = mfs.moveObj2Origin(topDisc);
topDisc = mfs.align2Value('bottom', topDisc, specimenHeight);
topDisc.groupId = 3 .* ones(size(topDisc.X));

wallObject = mfs.combineObj(tube, bottomDisc, topDisc);
wallIds = d.addElement(1, wallObject, 'wall');
d.addGroup('tubeWall', wallIds(wallObject.groupId == 1));
d.addGroup('bottomPorousDisc', wallIds(wallObject.groupId == 2));
d.addGroup('topPorousDisc', wallIds(wallObject.groupId == 3));

sandRadius = particles.sand_diameter_m ./ 2;
microplasticRadius = particles.microplastic_diameter_m ./ 2;
sandObject = randomCylinderObject(sandRadius, specimenRadius, ...
    specimenHeight, config.preparation.initial_radius_scale);
microplasticObject = randomCylinderObject(microplasticRadius, ...
    specimenRadius, specimenHeight, ...
    config.preparation.initial_radius_scale);

sandIds = d.addElement(1, sandObject);
sandIds = sandIds(:);
microplasticIds = d.addElement(1, microplasticObject);
microplasticIds = microplasticIds(:);
d.addGroup('sand', sandIds);
d.addGroup('microplastic', microplasticIds);
d.addGroup('sample', [sandIds; microplasticIds]);
d.mo.frame = struct('minX', -specimenRadius, 'maxX', specimenRadius, ...
    'minY', -specimenRadius, 'maxY', specimenRadius, ...
    'minZ', 0, 'maxZ', specimenHeight);

d.mo.aMUp(d.GROUP.sample) = ...
    config.preparation.initial_friction_coefficient;
d.mo.setGPU(char(config.engine.dem_gpu_mode));
for radiusScale = config.preparation.radius_expansion_scales
    d.mo.setGPU('off');
    d.mo.aR(sandIds) = sandRadius .* radiusScale;
    d.mo.aR(microplasticIds) = microplasticRadius .* radiusScale;
    d.mo.setGPU(char(config.engine.dem_gpu_mode));
    d.balance(char(config.preparation.balance_mode), ...
        config.preparation.balance_duration_per_expansion);
end

d.mo.setGPU('off');
Mats = cell(2, 1);
Mats{1} = material('LBSB_Sand', ...
    config.materials.sand_parameters, config.sand.d50_m ./ 2);
Mats{1}.Id = 1;
Mats{2} = material('Microplastic', ...
    config.materials.microplastic_parameters, ...
    config.microplastic.diameter_m ./ 2);
Mats{2}.Id = 2;
d.Mats = Mats;
d.setGroupMat('sand', 'LBSB_Sand');
d.setGroupMat('microplastic', 'Microplastic');
d.groupMat2Model({'sand', 'microplastic'});
d.mo.aMUp(wallIds) = config.boundary.wall_friction_coefficient;
d.mo.setGPU(char(config.engine.dem_gpu_mode));
d.balance(char(config.preparation.balance_mode), ...
    config.preparation.final_balance_duration);

d.mo.setGPU('off');
assert(all(isfinite(d.mo.aX(d.GROUP.sample))) && ...
    all(isfinite(d.mo.aY(d.GROUP.sample))) && ...
    all(isfinite(d.mo.aZ(d.GROUP.sample))), ...
    'matdem_microplastic:NativePreparationFailed', ...
    'Nonfinite particle coordinates were detected after preparation.');

environment.timestamp_utc = utcNow();
save(config.files.stage1_specimen, 'B', 'd', 'config', 'manifest', ...
    'environment', '-v7.3');
manifest.model_status = "native_stage1_completed";
manifest.timestamp_utc = utcNow();
writeNativeJson(config.files.stage1_manifest, manifest);

output = struct('B', B, 'd', d, 'config', config, ...
    'manifest', manifest, 'environment', environment);
fprintf('NATIVE_MATDEM_STAGE1_PASS particles=%d porosity=%.9g\n', ...
    manifest.total_particle_count, manifest.resolved_porosity);
end

function object = randomCylinderObject(targetRadius, cylinderRadius, ...
    cylinderHeight, initialRadiusScale)
targetRadius = targetRadius(:);
radialLimit = cylinderRadius - targetRadius;
verticalRange = cylinderHeight - 2 .* targetRadius;
assert(all(radialLimit > 0) && all(verticalRange > 0), ...
    'matdem_microplastic:ParticleDoesNotFit', ...
    'At least one particle does not fit inside the target cylinder.');

angle = 2 .* pi .* rand(size(targetRadius));
radialPosition = sqrt(rand(size(targetRadius))) .* radialLimit;
object = struct();
object.X = radialPosition .* cos(angle);
object.Y = radialPosition .* sin(angle);
object.Z = targetRadius + rand(size(targetRadius)) .* verticalRange;
object.R = targetRadius .* initialRadiusScale;
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
