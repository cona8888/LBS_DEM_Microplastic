function particles = generate_native_matdem_particle_distribution(config)
%GENERATE_NATIVE_MATDEM_PARTICLE_DISTRIBUTION Resolve mixture particle sizes.

arguments
    config (1,1) struct
end

validateInputs(config);

specimenVolume = config.geometry.volume_m3;
targetSolidVolume = (1 - config.sand.target_porosity) .* specimenVolume;
targetMicroplasticVolume = config.microplastic.solid_volume_fraction .* ...
    targetSolidVolume;
targetSandVolume = targetSolidVolume - targetMicroplasticVolume;

microplasticParticleVolume = pi ./ 6 .* ...
    config.microplastic.diameter_m.^3;
microplasticCount = max(1, round(targetMicroplasticVolume ./ ...
    microplasticParticleVolume));
microplasticDiameter = repmat(config.microplastic.diameter_m, ...
    microplasticCount, 1);

estimateQuantile = ((1:20000).' - 0.5) ./ 20000;
estimateDiameter = interp1(config.sand.grading_probability, ...
    config.sand.grading_diameter_m, estimateQuantile, 'linear');
meanSandParticleVolume = mean(pi ./ 6 .* estimateDiameter.^3);
sandCount = max(1, round(targetSandVolume ./ meanSandParticleVolume));

for iteration = 1:8
    sandQuantile = ((1:sandCount).' - 0.5) ./ sandCount;
    sandDiameter = interp1(config.sand.grading_probability, ...
        config.sand.grading_diameter_m, sandQuantile, 'linear');
    sandVolume = sum(pi ./ 6 .* sandDiameter.^3);
    countCorrection = round((targetSandVolume - sandVolume) ./ ...
        meanSandParticleVolume);
    if countCorrection == 0
        break
    end
    sandCount = max(1, sandCount + countCorrection);
end

sandQuantile = ((1:sandCount).' - 0.5) ./ sandCount;
sandDiameter = interp1(config.sand.grading_probability, ...
    config.sand.grading_diameter_m, sandQuantile, 'linear');
sandVolume = sum(pi ./ 6 .* sandDiameter.^3);
microplasticVolume = sum(pi ./ 6 .* microplasticDiameter.^3);
actualSolidVolume = sandVolume + microplasticVolume;

particles = struct();
particles.sand_diameter_m = sandDiameter;
particles.microplastic_diameter_m = microplasticDiameter;
particles.sand_count = sandCount;
particles.microplastic_count = microplasticCount;
particles.total_count = sandCount + microplasticCount;
particles.sand_solid_volume_m3 = sandVolume;
particles.microplastic_solid_volume_m3 = microplasticVolume;
particles.total_solid_volume_m3 = actualSolidVolume;
particles.target_total_solid_volume_m3 = targetSolidVolume;
particles.actual_porosity = 1 - actualSolidVolume ./ specimenVolume;
particles.actual_microplastic_solid_volume_fraction = ...
    microplasticVolume ./ actualSolidVolume;
particles.solid_volume_relative_error = abs(actualSolidVolume - ...
    targetSolidVolume) ./ targetSolidVolume;
end

function validateInputs(config)
required = ["geometry", "sand", "microplastic"];
for fieldName = required
    assert(isfield(config, fieldName), ...
        'matdem_microplastic:MissingNativeConfig', ...
        'Missing native MatDEM configuration group: %s', fieldName);
end
assert(config.geometry.volume_m3 > 0, ...
    'matdem_microplastic:InvalidNativeGeometry', ...
    'Specimen volume must be positive.');
assert(config.sand.target_porosity > 0 && ...
    config.sand.target_porosity < 1, ...
    'matdem_microplastic:InvalidNativePorosity', ...
    'Target porosity must lie in (0,1).');
assert(config.microplastic.solid_volume_fraction > 0 && ...
    config.microplastic.solid_volume_fraction < 1, ...
    'matdem_microplastic:InvalidNativeContent', ...
    'Microplastic solid-volume fraction must lie in (0,1).');
assert(all(diff(config.sand.grading_probability) > 0) && ...
    config.sand.grading_probability(1) == 0 && ...
    config.sand.grading_probability(end) == 1, ...
    'matdem_microplastic:InvalidNativeGrading', ...
    'Grading probabilities must increase from zero to one.');
assert(all(diff(config.sand.grading_diameter_m) > 0), ...
    'matdem_microplastic:InvalidNativeGrading', ...
    'Grading diameters must be strictly increasing.');
end
