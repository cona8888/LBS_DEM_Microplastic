#include <iostream>
int run_lbm_tests();
int run_ibm_tests();
int run_dem_tests();
int run_ibm_independent_tests();
int run_block_tests();
int run_quadrature_tests();
int test_ibm_prescribed();
int run_near_field_tests();
int run_wet_stage_tests();
int main(){int failures=run_lbm_tests()+run_ibm_tests()+run_dem_tests()+run_ibm_independent_tests()+run_block_tests()+run_quadrature_tests()+test_ibm_prescribed()+run_near_field_tests()+run_wet_stage_tests();std::cout<<"TOTAL_FAILURES "<<failures<<"\n";return failures?1:0;}
