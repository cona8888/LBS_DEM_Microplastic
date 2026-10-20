%RUN_TWO_PORE_TOY Configure MatDEM and execute the headless pore toy.

projectRoot = string(fileparts(fileparts(mfilename('fullpath'))));
addpath(projectRoot);
environment = setup_matdem_microplastic();
config = two_pore_toy_config(projectRoot);
result = simulate_two_pore_toy(config);

disp(jsonencode(environment, PrettyPrint=true));
disp(jsonencode(result.summary, PrettyPrint=true));
