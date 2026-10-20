"""Run the same declared integration checks for the optional algorithm."""
import verify_integration_v1 as verification
import trajectory_prefix_optional
verification.candidate = trajectory_prefix_optional
if __name__=='__main__':verification.main()
