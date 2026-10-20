"""Verify the call-scoped warm-contact trajectory binding."""
import trajectory_inertial_v4 as trajectory
import verify_inertial_trajectory_v2 as previous

previous.tr = trajectory

if __name__ == "__main__":
    previous.main()
