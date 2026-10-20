function config = native_matdem_hydromechanical_config(projectRoot)
%NATIVE_MATDEM_HYDROMECHANICAL_CONFIG Native pore3d application case.
%
% Literature-backed sand geometry is separated from deliberately uncalibrated
% contact, fluid-throat and microplastic properties. The model represents
% fixed microplastic inclusions; it does not implement mobile-particle transport.

arguments
    projectRoot (1,1) string
end

localMatDEMRoot = fullfile(projectRoot, "MatDEM5.00(Win&Linux)");
if ~isfolder(localMatDEMRoot)
    localMatDEMRoot = ...
        "C:\Users\wonjuncha-admin\Downloads\MatDEM\MatDEM5.00(Win&Linux)";
end

config = struct();
config.case_name = "lbsb_dr50_fixed_mp1_hm_coupled";
config.model_status = "prepared_not_native_executed";
config.claim_boundary = ...
    "native MatDEM pore3d implementation; uncalibrated and unvalidated";
% MatDEM fs.randSeed interprets large integers as array dimensions. The
% installed examples use small positive integers such as 1, 2, 3 and 4.
config.random_seed = 1;

config.engine = struct();
config.engine.name = "MatDEM";
config.engine.version = "5.00 standalone runtime";
config.engine.matdem_root = string(localMatDEMRoot);
config.engine.required_fluid_class = "pore3d";
config.engine.dem_gpu_mode = "on";
config.engine.pore_gpu_mode = "on";

config.geometry = struct();
config.geometry.specimen_shape = "cylinder";
config.geometry.diameter_m = 0.050;
config.geometry.height_m = 0.020;
config.geometry.area_m2 = pi .* config.geometry.diameter_m.^2 ./ 4;
config.geometry.volume_m3 = config.geometry.area_m2 .* ...
    config.geometry.height_m;

config.sand = struct();
config.sand.name = "Leighton Buzzard sand, Fraction B";
config.sand.shape = "sphere approximation";
config.sand.d_min_m = 0.60e-3;
config.sand.d10_m = 0.65e-3;
config.sand.d50_m = 0.82e-3;
config.sand.d60_m = 0.65e-3 .* 1.38;
config.sand.d_max_m = 1.18e-3;
config.sand.uniformity_coefficient = 1.38;
config.sand.minimum_void_ratio = 0.46;
config.sand.maximum_void_ratio = 0.79;
config.sand.relative_density = 0.50;
config.sand.void_ratio = config.sand.maximum_void_ratio - ...
    config.sand.relative_density .* ...
    (config.sand.maximum_void_ratio - config.sand.minimum_void_ratio);
config.sand.target_porosity = config.sand.void_ratio ./ ...
    (1 + config.sand.void_ratio);
config.sand.particle_density_kg_per_m3 = 2650;
config.sand.grading_probability = [0; 0.10; 0.50; 0.60; 1.00];
config.sand.grading_diameter_m = [config.sand.d_min_m; ...
    config.sand.d10_m; config.sand.d50_m; config.sand.d60_m; ...
    config.sand.d_max_m];
config.sand.grading_reconstruction = ...
    "piecewise-linear inverse CDF through Dmin, D10, D50, D60 and Dmax";
config.sand.literature_source_url = ...
    "https://eprints.whiterose.ac.uk/128971/7/GTJ-2018.pdf";

config.microplastic = struct();
config.microplastic.population = "fixed inclusion";
config.microplastic.shape = "sphere placeholder";
config.microplastic.solid_volume_fraction = 0.01;
config.microplastic.size_ratio_to_sand_d50 = 0.30;
config.microplastic.diameter_m = ...
    config.microplastic.size_ratio_to_sand_d50 .* config.sand.d50_m;
config.microplastic.material_label = "PVC-like MatDEM placeholder";
config.microplastic.particle_density_kg_per_m3 = 930;
config.microplastic.transport_enabled = false;

config.materials = struct();
config.materials.parameter_order = ["Young_modulus_Pa", ...
    "Poisson_ratio", "tensile_strength_Pa", ...
    "compressive_strength_Pa", "friction_coefficient", ...
    "density_kg_per_m3"];
config.materials.sand_parameters = [2.0e9, 0.15, 5.0e6, ...
    50.0e6, 0.50, config.sand.particle_density_kg_per_m3];
config.materials.microplastic_parameters = [2.0e6, 0.19, 2.0e3, ...
    50.0e3, 0.30, config.microplastic.particle_density_kg_per_m3];
config.materials.status = ...
    "soft-particle numerical placeholders requiring contact calibration";

config.boundary = struct();
config.boundary.wall_type = "rough particle tube plus fixed porous discs";
config.boundary.wall_particle_diameter_m = config.sand.d_min_m;
config.boundary.wall_dense_rate = 0.70;
config.boundary.wall_friction_coefficient = 0.0;
config.boundary.flow_direction = "top_to_bottom";

config.preparation = struct();
config.preparation.method = ...
    "random shrunken placement followed by frictionless radius expansion";
config.preparation.initial_radius_scale = 0.20;
config.preparation.radius_expansion_scales = ...
    linspace(config.preparation.initial_radius_scale, 1.0, 9);
config.preparation.balance_mode = "Standard";
config.preparation.balance_duration_per_expansion = 1;
config.preparation.final_balance_duration = 5;
config.preparation.initial_friction_coefficient = 0.0;

config.fluid = struct();
config.fluid.name = "water";
config.fluid.density_kg_per_m3 = 1000;
config.fluid.gravity_m_per_s2 = 9.80665;
config.fluid.reference_pressure_pa = 101325;
config.fluid.hydraulic_gradient = 1.0;
config.fluid.head_difference_m = config.fluid.hydraulic_gradient .* ...
    config.geometry.height_m;
config.fluid.pressure_difference_pa = ...
    config.fluid.density_kg_per_m3 .* config.fluid.gravity_m_per_s2 .* ...
    config.fluid.head_difference_m;
config.fluid.throat_flow_factor = 1.0e-8;
config.fluid.throat_flow_factor_status = ...
    "MatDEM example placeholder requiring clean-sand calibration";
config.fluid.time_step_scale = 1.0;

config.coupling = struct();
config.coupling.mode = "two_way_pore_pressure_particle_force";
config.coupling.outer_cycles = 20;
config.coupling.steps_per_cycle = 50;
config.coupling.fluid_substeps_per_mechanical_step = 2;
config.coupling.mass_balance_relative_tolerance = 0.02;
config.coupling.minimum_cycles_before_acceptance = 5;
config.coupling.checkpoint_every_cycles = 1;

config.verification = struct();
config.verification.required = ["finite pressure and coordinates"; ...
    "positive discharge and conductivity"; ...
    "inlet-outlet mass balance"; ...
    "fluid time-step refinement"; ...
    "coupling-frequency refinement"; ...
    "particle-size and specimen-size sensitivity"];

config.output_directory = fullfile(projectRoot, "runs", ...
    "native_hm_lbsb_dr50_fixed_mp1");
config.files = struct();
config.files.stage1_specimen = fullfile(config.output_directory, ...
    "stage1_prepared_specimen.mat");
config.files.stage1_manifest = fullfile(config.output_directory, ...
    "stage1_manifest.json");
config.files.stage2_pore_network = fullfile(config.output_directory, ...
    "stage2_initialized_pore3d.mat");
config.files.stage2_summary = fullfile(config.output_directory, ...
    "stage2_pore3d_summary.json");
config.files.stage3_result = fullfile(config.output_directory, ...
    "stage3_coupled_result.mat");
config.files.stage3_history = fullfile(config.output_directory, ...
    "stage3_coupled_history.csv");
config.files.stage3_summary = fullfile(config.output_directory, ...
    "stage3_coupled_summary.json");
config.files.checkpoint_directory = fullfile(config.output_directory, ...
    "checkpoints");
end
