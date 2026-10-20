"""Run the accepted v4 primitive suite against the warm-started v4 solver."""
import inertial_contact_v4 as model
import verify_inertial_contact_v4 as previous

previous.model = model

if __name__ == "__main__":
    previous.main()
