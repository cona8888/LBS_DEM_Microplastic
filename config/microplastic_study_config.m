function config = microplastic_study_config(projectRoot)
%MICROPLASTIC_STUDY_CONFIG Assumptions for the reduced mechanism study.

arguments
    projectRoot (1,1) string
end

config = struct();
config.backend = "reduced_kozeny_carman_retention";
config.content_definition = "microplastic solid-volume fraction";
config.case_name = "leighton_buzzard_fraction_b_dr50";
config.calibration_status = "uncalibrated literature-input case";
config.sand_name = "Leighton Buzzard sand, Fraction B";
config.sand_d10_m = 0.65e-3;
config.sand_d50_m = 0.82e-3;
config.sand_uniformity_coefficient = 1.38;
config.sand_d60_m = config.sand_d10_m .* ...
    config.sand_uniformity_coefficient;
config.sand_minimum_void_ratio = 0.46;
config.sand_maximum_void_ratio = 0.79;
config.sand_relative_density = 0.50;
config.sand_void_ratio = config.sand_maximum_void_ratio - ...
    config.sand_relative_density .* ...
    (config.sand_maximum_void_ratio - config.sand_minimum_void_ratio);
config.sand_diameter_m = config.sand_d50_m;
config.clean_porosity = config.sand_void_ratio ./ ...
    (1 + config.sand_void_ratio);
config.microplastic_to_sand_size_ratio = 0.30;
config.microplastic_diameter_m = ...
    config.microplastic_to_sand_size_ratio .* config.sand_d50_m;
config.microplastic_shape = "generic sphere";
config.microplastic_content_status = ...
    "1 percent solid-volume placeholder; clean comparator included";
config.literature_source = ...
    "Effect of Sample Reconstitution Methods on the Behaviors of Granular Materials under Shearing";
config.literature_source_url = ...
    "https://eprints.whiterose.ac.uk/128971/7/GTJ-2018.pdf";
config.porosity_change_per_unit_fraction = 0.0;
config.kozeny_constant = 5.0;
config.fixed_volume_fraction = [0; 0.01];

config.water_density_kg_per_m3 = 998.2;
config.water_dynamic_viscosity_pa_s = 1.002e-3;
config.gravity_m_per_s2 = 9.80665;
config.specimen_diameter_m = 0.05;
config.specimen_length_m = 0.02;
config.hydraulic_protocols = ["constant_head"; "falling_head"];
config.hydraulic_gradient = 1.0;
config.falling_head_standpipe_diameter_m = 0.01;
config.falling_head_initial_head_m = 0.10;
config.falling_head_terminal_head_m = 0.02;
config.falling_head_verification_time_step_fractions = [0.10; 0.05; 0.025];
config.falling_head_mobile_time_step_fraction = 0.001;
config.falling_head_maximum_steps = 100000;

config.mobile_enabled = true;
config.mobile_duration_s = 3600;
config.mobile_time_step_s = 10;
config.mobile_inlet_concentration_kg_per_m3 = 0.01;
config.mobile_filtration_coefficient_per_m = 5.0;
config.mobile_detachment_rate_per_s = 1.0e-5;
config.mobile_retention_capacity_kg = 1.0e-5;
config.mobile_clogging_exponent = 2.0;
config.mobile_minimum_permeability_ratio = 0.05;

config.write_results = true;
config.output_directory = fullfile(projectRoot, "runs", ...
    "leighton_buzzard_fraction_b_dr50_mp_ratio_0p30");
end
