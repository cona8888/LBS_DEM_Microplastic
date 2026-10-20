%RUN_MICROPLASTIC_REDUCED_STUDY Run fixed and mobile mechanism toys.

projectRoot = string(fileparts(fileparts(mfilename('fullpath'))));
addpath(projectRoot);
setup_matdem_microplastic();
config = microplastic_study_config(projectRoot);
result = simulate_microplastic_permeability_study(config);
disp(jsonencode(result.summary, PrettyPrint=true));
