"""Apply unchanged independent audit to version 2; include added failure probes."""
import local_regression_v2 as revised
import audit_local_repair_v1 as audit


if __name__=='__main__':
    folder=revised.updated.base.EVAL/'refined_units_01'
    r=audit.api.read(folder/'results.json');s=audit.api.read(folder/'completion.json')
    audit.api.require(r['passed'] and len(r['probes'])==23 and all(x['passed'] for x in r['probes']) and s['results_sha256']==audit.api.sha(folder/'results.json'),'added 23 failure probes sealed')
    audit.main()
