"""Material-specific membrane profiles, not bulk-soil conductance.
Uses reported hydrostatic regression slopes; raw replicates were not supplied.
The fixture flux and extrapolation from fully to partially wetted area are predictions.
"""
import json
from .fit import rows,HERE
from applications.rhizofield.run import uptake_rate,writecsv

def profiles():
    return {r['state']:{'Lp_m_Pa_s':float(r['mean_m_s_MPa'])/1e6,'SE_m_Pa_s':float(r['se_m_s_MPa'])/1e6} for r in rows('grapevine_tissue.csv') if r['tissue']=='intact_bark'}

def main():
    p=profiles();(HERE/'results'/'grapevine_profiles.json').write_text(json.dumps({'profiles':p,'tested_driving_pressure_Pa':[10000,20000,30000],'reported_advancing_deg':100.6,'reported_plus_minus_deg':4.2,'receding_deg':None,'wet_area_transfer':'Uniform active-surface scaling is an assumption; calibration used root total area in contact with water.'},indent=2)+'\n')
    writecsv(HERE/'results'/'grapevine_pressure_response.csv',[{'state':state,'deltaP_Pa':dp,'modeled_flux_m_s':uptake_rate(v['Lp_m_Pa_s'],1,dp,0),'model_flux_propagated_SE_m_s':v['SE_m_Pa_s']*dp} for state,v in p.items() for dp in [10000,20000,30000]])
if __name__=='__main__':main()
