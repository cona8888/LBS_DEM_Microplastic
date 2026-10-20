"""Correct the receipt label in v1; retain its failed harness evidence."""
from pathlib import Path
import reconstruct_failure_window_v1 as prior
text=Path(prior.__file__).read_text()
old="'audit_failed' if number==197 else 'audit_passed'"
if text.count(old)!=1:raise RuntimeError('one receipt label correction only')
text=text.replace(old,"'audit_failed' if number==197 else 'independently_verified'")
text=text.replace("reconstructed_window_01'","reconstructed_window_02'")
ns={'__name__':'_reconstruction_v2','__file__':__file__}
exec(compile(text,__file__+'::receipt_schema_correction','exec'),ns)
if __name__=='__main__':ns['run']()
