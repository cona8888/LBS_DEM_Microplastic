"""Run the state-machine suite using the robust cold Coulomb policy."""
import trajectory_cold_trap_v1 as model
import verify_trajectory_cached_trap_v1 as previous

previous.model = model

if __name__ == "__main__":
    previous.main()
