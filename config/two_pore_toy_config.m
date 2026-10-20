function config = two_pore_toy_config(projectRoot)
%TWO_PORE_TOY_CONFIG Deterministic settings for the hydraulic toy suite.

arguments
    projectRoot (1,1) string
end

config = struct();
config.backend = "auto";
config.particle_radius_m = 1.0e-4;
config.pressure_gradient_pa_per_m = 1.0e4;
config.rate_scale = 1.0;
config.step_count = 50;
config.fluid_dynamic_viscosity_pa_s = 1.0e-3;
config.fluid_compressibility_pa_inverse = 4.4e-10;
config.pore_volume_m3 = (4 / 3) * pi * config.particle_radius_m^3;
config.throat_radius_m = 0.25 * config.particle_radius_m;
config.throat_length_m = 2.0 * config.particle_radius_m;
config.time_step_fraction_of_pressure_time_constant = 0.05;
config.run_matdem_core_probe = false;
config.matdem_core_step_count = 800;
config.write_results = true;
config.output_directory = fullfile(projectRoot, "runs", "toy_two_pore");
config.matdem_core_output_directory = fullfile( ...
    projectRoot, "runs", "toy_matdem_two_balls");
end
