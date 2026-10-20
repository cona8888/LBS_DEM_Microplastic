"""Run the accepted trajectory suite against the warm-started v3 trajectory."""
import trajectory_inertial_v3 as trajectory
import verify_inertial_trajectory_v2 as previous

previous.tr = trajectory

if __name__ == "__main__":
    previous.main()
