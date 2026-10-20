"""Run the accepted state-machine suite with normal-only caching."""
import trajectory_cached_trap_v2 as model
import verify_trajectory_cached_trap_v1 as previous

previous.model = model

if __name__ == "__main__":
    previous.main()
