function manifest = build_native_matdem_case_manifest(config)
%BUILD_NATIVE_MATDEM_CASE_MANIFEST Summarize the resolved particle assembly.

arguments
    config (1,1) struct
end

particles = generate_native_matdem_particle_distribution(config);

manifest = struct();
manifest.case_name = config.case_name;
manifest.model_status = config.model_status;
manifest.engine = config.engine.name + " " + config.engine.version;
manifest.specimen_shape = config.geometry.specimen_shape;
manifest.specimen_diameter_m = config.geometry.diameter_m;
manifest.specimen_height_m = config.geometry.height_m;
manifest.target_porosity = config.sand.target_porosity;
manifest.resolved_porosity = particles.actual_porosity;
manifest.target_microplastic_solid_volume_fraction = ...
    config.microplastic.solid_volume_fraction;
manifest.resolved_microplastic_solid_volume_fraction = ...
    particles.actual_microplastic_solid_volume_fraction;
manifest.sand_count = particles.sand_count;
manifest.microplastic_count = particles.microplastic_count;
manifest.total_particle_count = particles.total_count;
manifest.sand_diameter_min_m = min(particles.sand_diameter_m);
manifest.sand_diameter_median_m = median(particles.sand_diameter_m);
manifest.sand_diameter_max_m = max(particles.sand_diameter_m);
manifest.microplastic_diameter_m = config.microplastic.diameter_m;
manifest.microplastic_to_sand_d50_ratio = ...
    config.microplastic.size_ratio_to_sand_d50;
manifest.specimen_diameter_to_sand_d50 = ...
    config.geometry.diameter_m ./ config.sand.d50_m;
manifest.specimen_height_to_sand_d50 = ...
    config.geometry.height_m ./ config.sand.d50_m;
manifest.solid_volume_relative_error = ...
    particles.solid_volume_relative_error;
manifest.flow_direction = config.boundary.flow_direction;
manifest.hydraulic_gradient = config.fluid.hydraulic_gradient;
manifest.pressure_difference_pa = config.fluid.pressure_difference_pa;
manifest.two_way_coupling = true;
manifest.mobile_microplastic_transport = ...
    config.microplastic.transport_enabled;
manifest.calibration_status = config.materials.status;
end
