"""Source-bound literature trend comparison, without running or fitting a model.

Creates one new immutable output directory. PDF/image coordinates are retained.
Plots are read, not reproduced as publication figures. No simulation import.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pdfplumber
from PIL import Image

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
SRC = ROOT / 'literature_screen_20260917/sources'
BOUND = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path):
    p = Path(path).resolve()
    BOUND[str(p)] = sha(p)
    return {'path': str(p), 'sha256': BOUND[str(p)]}


def load(path):
    bind(path)
    return json.loads(Path(path).read_text(encoding='utf-8'))


def ratio_interval(value, baseline, uncertainty):
    """Digitisation sensitivity envelope only, not experimental confidence limits."""
    assert baseline > uncertainty
    return [max(0., value-uncertainty)/(baseline+uncertainty),
            (value+uncertainty)/(baseline-uncertainty)]


def aminzadeh():
    source = bind(SRC / 'aminzadeh_2025_permeability.pdf')
    image_path = BASE / 'source_previews/aminzadeh_figure3_native.jpg'
    image_binding = bind(image_path)
    rgb = np.asarray(Image.open(image_path).convert('RGB')).astype(float)
    assert rgb.shape[:2] == (1183, 1608)
    # Visually checked Fig.3a native image: zero at y527; 0.12 cm/s at y70.
    y0, y12 = 527., 70.
    slope = .12 / (y0-y12)
    e = 4*slope  # Conservative +/-4px sensitivity to outline/error-cap overlap and calibration.
    colors = {'clean': np.array([47, 82, 145]),
              '2': np.array([195, 151, 0]), '5': np.array([83, 129, 46])}
    # (centre x, visually located top window centre) for clean/2%/5% bars.
    centres = {
        'PE': {'fine': [(212,418),(259,481),(307,491)],
               'medium': [(449,257),(497,398),(545,457)],
               'coarse': [(687,142),(735,172),(782,366)]},
        'PVC': {'fine': [(972,418),(1019,411),(1067,456)],
                'medium': [(1209,257),(1257,302),(1305,363)],
                'coarse': [(1447,142),(1495,159),(1542,214)]}}
    porosity = {'fine':[.37,.34,.32,.36,.35],
                'medium':[.38,.36,.33,.37,.36],
                'coarse':[.39,.36,.34,.37,.34]}
    grains = {'fine':[100,500], 'medium':[400,800], 'coarse':[700,1200]}
    rows = []
    for polymer, groups in centres.items():
        for sand, bars in groups.items():
            local = []
            for j, (cx, guess_y) in enumerate(bars):
                label = ['clean','2','5'][j]
                patch = rgb[guess_y-12:guess_y+16, cx-17:cx+18]
                mask = np.linalg.norm(patch-colors[label], axis=2) < 55
                # Majority of bar interior avoids the central black errorbar stem.
                counts = mask.sum(axis=1)
                hits = np.flatnonzero(counts >= 19)
                assert len(hits), (polymer,sand,j)
                first_fill_y = guess_y-12+int(hits[0])
                top = first_fill_y-1.5  # Centre of the black bar outline.
                value = (y0-top)*slope
                local.append({'source': 'Aminzadeh2025', 'polymer':polymer,
                    'sand':sand, 'concentration_mass_percent': [0,2,5][j],
                    'concentration_denominator': 'mass basis; mixture-versus-sand denominator not explicit in inspected methods',
                    'grain_size_range_um': grains[sand],
                    'mp_size_range_um': [34,50] if polymer=='PE' else [80,200],
                    'K_cm_per_s':value, 'digitisation_uncertainty_cm_per_s':e,
                    'porosity_table1':porosity[sand][0 if j==0 else (j if polymer=='PE' else j+2)],
                    'experimental_errorbar': 'present, not extracted; type unspecified in Figure 3 caption',
                    'n_reported':3, 'coordinate':{'x_native_px':cx,'first_fill_y_px':first_fill_y,'bar_top_y_px':top},
                    'figure':'3a','pdf_page_1based':5,
                    'control_id': f'Aminzadeh2025_{sand}_clean',
                    'role': 'control duplicated between panels' if j==0 else 'treatment'})
            baseline = local[0]['K_cm_per_s']
            for r in local:
                r['K_over_K0'] = r['K_cm_per_s']/baseline
                r['digitisation_only_ratio_envelope'] = ([1.,1.] if r['concentration_mass_percent']==0 else ratio_interval(r['K_cm_per_s'],baseline,e))
                rows.append(r)
    # Independent prose checks are deliberately coarse; do not force digitisation to them.
    expected = {('PE','fine'):.33,('PE','medium'):.26,('PE','coarse'):.42,
                ('PVC','fine'):.65,('PVC','medium'):.61,('PVC','coarse'):.82}
    for r in rows:
        if r['concentration_mass_percent']==5:
            assert abs(r['K_over_K0']-expected[r['polymer'],r['sand']]) < .025
    return {'source_pdf':source,'image_derivative':image_binding,
            'method':'colour-segmented raster bars, not raw experimental observations',
            'axis':{'zero_y_px':y0,'value_0p12_y_px':y12,'unit':'cm/s'},'rows':rows}


def yu():
    source = bind(SRC / 'es2c09822_si_001.pdf')
    rows=[]
    colors={'pristine':(.737,.235,.161), 'field_weathered':(0.,.447,.71)}
    panels={'PES_fibre':([148.660,154.673,160.693,172.733,197.807,246.954], [0,.06,.12,.24,.49,.98]),
            'PP_granule':([283.823,289.136,294.624,305.425,327.020,370.217], [0,.30,.61,1.22,2.44,4.88])}
    y0,y15=539.370,450.407
    slope=15/(y0-y15)
    e=.15*slope  # PDF-coordinate reading sensitivity, not measurement noise.
    with pdfplumber.open(SRC / 'es2c09822_si_001.pdf') as pdf:
        p=pdf.pages[18]
        for material,(xs,cs) in panels.items():
            for condition,col in colors.items():
                local=[]
                for x,c in zip(xs,cs):
                    found=[o for o in p.lines if abs(o['x0']-x)<.02 and abs(o['x1']-x)<.02
                           and 450<o['top']<534 and o['bottom']<534
                           and np.allclose(o['stroking_color'],col,atol=.002)]
                    assert len(found)<=1
                    r={'source':'Yu2023','material':material,'condition':condition,
                       'concentration_mass_percent':c,'concentration_denominator':'source w/w label retained',
                       'soil':'silt loam','figure':'S6C','pdf_page_1based':19,'n_reported':3,
                       'control_id':f'Yu2023_{condition}_zero_repeated_across_material_panels'}
                    if not found:
                        assert (material,condition,c)==('PES_fibre','field_weathered',.24)
                        r.update(K_m_per_day=None,SD_m_per_day=None,K_over_K0=None,
                                 missing_reason='No coloured mean marker/errorbar recoverable at this location; not imputed.')
                    else:
                        o=found[0]; top,bottom=o['top'],o['bottom']
                        r.update(K_m_per_day=(y0-(top+bottom)/2)*slope,
                                 SD_m_per_day=(bottom-top)*slope/2,
                                 digitisation_uncertainty_m_per_day=e,
                                 coordinate={'x_pdf_pt':x,'errorbar_top_pdf_pt':top,'errorbar_bottom_pdf_pt':bottom})
                    local.append(r)
                baseline=local[0]['K_m_per_day']
                for r in local:
                    if r['K_m_per_day'] is not None:
                        r['K_over_K0']=r['K_m_per_day']/baseline
                        r['SD_divided_by_control_mean']=r['SD_m_per_day']/baseline
                        r['digitisation_only_ratio_envelope']=([1.,1.] if r['concentration_mass_percent']==0 else ratio_interval(r['K_m_per_day'],baseline,e))
                    rows.append(r)
    return {'source_pdf':source,'method':'vector errorbar midpoint gives plotted mean; half-length gives caption-defined SD',
            'axis':{'zero_y_pdf_pt':y0,'value15_y_pdf_pt':y15,'unit':'m/day'},
            'uncertainty_note':'Scaled SD is not the SD or confidence interval of a ratio; raw replicates and covariance were unavailable. Repeated zero controls are not independent.',
            'rows':rows}


def cohen():
    source=bind(SRC / 'es5c12359_si_001.pdf')
    rows=[]
    for label,lo,hi,trapped,not_trapped in [('20–50',20,50,10,30),('50–80',50,80,30,10),('>80',80,None,39,1)]:
        rows.append({'source':'Cohen2025','table':'S2','pdf_page_1based':4,
                     'length_bin_um':label,'length_lower_um':lo,'length_upper_um':hi,
                     'trapped':trapped,'not_trapped':not_trapped,'analysed':trapped+not_trapped,
                     'conditional_trapped_fraction':trapped/(trapped+not_trapped),
                     'conditional_not_trapped_fraction':not_trapped/(trapped+not_trapped),
                     'resident_release_fraction':None})
    return {'source_pdf':source,'method':'exact published count transcription, visually checked',
            'denominator':'analysed tracked fibres, not initial resident inventory; not-trapped is not proof of downstream export',
            'bin_note':'Source bin labels retained; endpoint convention unspecified; no midpoint invented for open bin.', 'rows':rows}


def ameen():
    source=bind(SRC / 'ameen_2024_spheres.pdf')
    im_path=BASE/'source_previews/ameen_figure3_native.png'
    pixels=np.asarray(Image.open(im_path).convert('RGB')).astype(float)
    assert pixels.shape[:2]==(652,1000)
    # Clear interior observed-circle subset. Dashed fitted lines are NOT data.
    xs=[329,371,392,413,434,455,476,498,518,540,561,582,603,624,645,667,687,709]
    ys={'R1':[374,329,314,342,319,340,307,354,295,319,312,319,328,362,377,442,484,525],
        'R2':[350,359,368,383,379,391,406,379,355,375,373,368,362,346,355,423,469,507]}
    colors={'R1':np.array([0,128,128]),'R2':np.array([92,158,161])}
    rows=[]
    for series,yvals in ys.items():
        for x,y in zip(xs,yvals):
            box=pixels[y-7:y+8,x-7:x+8]
            mask=np.linalg.norm(box-colors[series],axis=2)<24
            iy,ix=np.nonzero(mask)
            assert len(ix)>35,(series,x,y,len(ix))
            cx=x-7+float(np.median(ix)); cy=y-7+float(np.median(iy))
            assert abs(cx-x)<=3 and abs(cy-y)<=3,(series,x,y,cx,cy)
            t=(cx-96.)/(975.-96.)*500.
            c=(571.-cy)/(571.-11.)*.5
            volume=math.pi*(7/2)**2*30 # mL; 70mm ID,300mm length, methods p4
            rows.append({'source':'Ameen2024','figure':'3','pdf_page_1based':9,
                         'series_label':f'SMPs (1 um), {series}',
                         'time_after_injection_min':t,'C_over_C0':c,
                         'bulk_column_volumes_Qt_over_AL':4*t/volume,
                         'pore_volumes':None,
                         'digitisation_uncertainty_min':3*500/879,
                         'digitisation_uncertainty_C_over_C0':3*.5/560,
                         'coordinate':{'manual_roi_x_px':x,'manual_roi_y_px':y,'marker_centre_x_px':cx,'marker_centre_y_px':cy},
                         'dimensionless_size_dMP_over_d50':1/950})
    return {'source_pdf':source,'image_derivative':bind(im_path),
            'method':'colour-filtered circle-centre extraction within visually selected ROIs; fitted lines excluded',
            'coverage':'18 clear interior points per plotted sphere series, not full breakthrough curve; no recovery integration',
            'label_note':'Figure legend R1/R2 retained; caption calls curves averages. No independence or errorbar inference made.',
            'conditions':{'polymer':'polystyrene','particle_shape':'spherical','particle_diameter_um':1,
                          'sand_size_um':[600,1300],'sand_d50_um':950,
                          'column_diameter_cm':7,'column_length_cm':30,'Q_mL_per_min':4,
                          'flow_direction':'upward','injection_pore_volumes':2,'flush_pore_volumes':5},
            'normalisation_note':'Qt/(AL) is bulk-column throughput, NOT pore volumes. PV=Qt/(nAL) requires porosity; not guessed from the breakthrough curve.',
            'reported_recovery_comparison':{'spheres_1um_fraction':.245,'fragments_about1p4um_fraction':.31,
                 'source_location':'main text p9, Section 4.2 continuation; approximate source-reported percent mass recovery, not recalculated from this partial digitisation',
                 'denominator':'injected inventory; not resident inventory'},
            'rows':rows}


def simulations():
    legacy_path=ROOT/'stage31_evaluations/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_evaluation_01/evaluation.json'
    legacy=load(legacy_path)
    groups=[]
    for count in [1,2,4]:
        rr=[r for r in legacy['rows'] if r['fibre_count']==count]
        assert len(rr)==6
        vals=[r['paired_permeability_ratio'] for r in rr]
        groups.append({'fibre_count':count,'n_packing':3,'n_nested_block_per_packing':2,
                       'n_ratios':6,'mass_percent':rr[0]['achieved_dry_mass_percent'],
                       'mean_ratio':float(np.mean(vals)),'min_ratio':min(vals),'max_ratio':max(vals),
                       'six_ratios_not_independent_packing_replicates':True})
    current_path=ROOT/'stage134_evaluations/sphere_combined_budget_refinement_20260916/independent_evaluation_01/results.json'
    current=load(current_path); assert current['passed'] is True
    sentinels=[]
    for s in current['shapes']:
        rb=s['record_bindings']['cpd6']; assert sha(rb['path'])==rb['sha256']
        r=load(rb['path'])['result']
        assert r['time_s']==.5 and r['status']=='present_at_horizon'
        design_path = ROOT / ('stage134_designs/sphere_combined_budget_refinement_20260916/design_01.json' if s['shape']=='sphere' else 'stage133_designs/cpd6_response_refinement_20260916/design_01.json')
        design=load(design_path)
        case_id=load(rb['path'])['case_id']
        case=next(v for v in design['cases'] if v['id']==case_id)
        spec=case['spec']; cfg=spec['config']; meta=spec['field_metadata']
        axes=cfg['prolate_semiaxes_m']; deq=2*math.prod(axes)**(1/3)
        U=meta['achieved_mean_interstitial_velocity_m_s']; length=meta['cell_length_m']
        sentinels.append({'shape':s['shape'],'record':rb,'time_s':r['time_s'],
                          'event':r['status'],'observed_max_particle_Re':r['max_reynolds'],
                          'dimensionless':{'AR':max(axes)/min(axes),
                            'equivalent_volume_diameter_m':deq,'equivalent_diameter_over_cell_length':deq/length,
                            'density_ratio':cfg['particle_density_kg_m3']/cfg['fluid_density_kg_m3'],
                            'Re_mean_flow_equivalent_diameter':cfg['fluid_density_kg_m3']*abs(U)*deq/cfg['dynamic_viscosity_Pa_s'],
                            'advective_time_Ut_over_cell_length':U*r['time_s']/length,
                            'mean_interstitial_speed_m_s':U,'cell_length_m':length},
                          'combined_position_screen_over_minor_radius':s['combined_spatial_plus_twice_temporal']['position_difference_over_b'],
                          'population_release_fraction':None})
    # Bind the retrospective diagnosis, not just an old pass label.
    plan=bind(ROOT/'MASTER_PLAN.md')
    return {'legacy_static_hydraulic':{'evaluation':bind(legacy_path),'groups':groups,
             'status':'HISTORICAL_CONTEXT_ONLY: Stage113 diagnosed alternating-mode defects in two Stage31 clean states; these ratios are not requalified by current clean-field repair.',
             'comparison':'Descriptive obstruction sign agrees with some sand experiments; no accepted quantitative experimental agreement asserted.'},
            'current_numerically_screened':{'evaluation':bind(current_path),'sentinels':sentinels,
             'comparison':'Single-start 0.5-s endpoints cannot establish population release, a breakthrough curve, a length trend, or a permeability-concentration trend.'},
            'retrospective_status_source':plan}


def report(data):
    a,y,c,b,sim=[data[k] for k in ['aminzadeh','yu','cohen','ameen','simulation']]
    lines=['# Literature trend comparison — no parameter fitting','',
      '17 September 2026. Source-derived data and comparison notes only; no manuscript, publication figure or new simulation.', '',
      '## Decision','',
      '- Use control-normalised changes and mechanism comparisons. Keep all model parameters fixed; no optimisation, fitted contact parameters or experimental curve-matching loop.',
      '- This is a trend-consistency assessment, not empirical validation. Normalisation removes units/baselines, not differences in packing, polymer, shape, chemistry or release denominator.',
      '- Keep both agreeing and disagreeing trends. Do not force monotonicity or rescale concentration/time to make curves coincide.','',
      '## 1. Sand hydraulic data','',
      '[Aminzadeh et al. (2025)](https://doi.org/10.1038/s41598-025-30476-6), Figure 3a: 18 bars digitised (three controls repeated across two panels). Values below are treatment/control mean ratios.','',
      '| Sand | PE, 2% | PE, 5% | PVC, 2% | PVC, 5% |','|---|---:|---:|---:|---:|']
    for sand in ['fine','medium','coarse']:
        vals=[next(r['K_over_K0'] for r in a['rows'] if r['sand']==sand and r['polymer']==p and r['concentration_mass_percent']==q) for p,q in [('PE',2),('PE',5),('PVC',2),('PVC',5)]]
        lines.append('| '+sand+' | '+' | '.join(f'{v:.3f}' for v in vals)+' |')
    lines+=['','- Predominantly lower conductivity; the fine-sand 2% PVC point is above its control. Conservative bar-reading sensitivity is ±4 native pixels (about ±0.00105 cm/s), covering outline/error-cap overlap. Experimental errorbars are not represented by this sensitivity envelope.',
      '- Sand was mixed/repacked at 2–5% mass loading; PE/PVC size and density differ. This is not an ideal sphere-versus-fibre experiment. Our historical fibre mass loadings are much lower; no common concentration slope is claimed.','',
      '## 2. Fibre and granule counterexample','',
      '[Yu et al. (2023)](https://doi.org/10.1021/acs.est.2c09822), SI Figure S6C: 23 plotted means/SDs recovered from vector errorbars; one field-weathered fibre point is unavailable. Each series uses its own zero-loading control.','',
      '| Material/condition | Concentration (% w/w) | K/K0 |','|---|---|---|']
    for material in ['PES_fibre','PP_granule']:
        for condition in ['pristine','field_weathered']:
            rr=[r for r in y['rows'] if r['material']==material and r['condition']==condition]
            lines.append('| '+material.replace('_',' ')+' / '+condition.replace('_',' ')+' | '+', '.join(f"{r['concentration_mass_percent']:g}" for r in rr)+' | '+', '.join('missing' if r['K_over_K0'] is None else f"{r['K_over_K0']:.2f}" for r in rr)+' |')
    lines+=['','- Pristine polyester fibre conductivity rises at higher loading; the highest-loading weathered fibre point lies below its weathered control. A universal “microplastic always reduces permeability” statement is not supported.',
      '- The source reports SD, n=3. Raw SDs are retained; uncertainty of normalised experimental means cannot be reconstructed fully without replicate/control covariance. Several weathered errorbars are large.',
      '- Silt-loam packing and weathering can change structure and surfaces. The pristine/weathered comparison is not a direct calibration of our rigid-fibre length parameter or a unique degradation index.','',
      '## 3. Length and conditional trapping','',
      '[Cohen et al. (2025)](https://doi.org/10.1021/acs.est.5c12359), SI Table S2: exact count transcription, not plot digitisation.','',
      '| Fibre length (µm) | Trapped / analysed | Conditional trapped fraction |','|---|---:|---:|']
    for r in c['rows']:
        lines.append(f"| {r['length_bin_um']} | {r['trapped']}/{r['analysed']} | {100*r['conditional_trapped_fraction']:g}% |")
    lines+=['','- Supports length-dependent trapping in that experiment. Curved/flexible PP in a 2D device differs from our rigid PET body in 3D sand. Do not call the complementary fraction “release from the soil matrix.”','',
      '## 4. A directly observed sphere transport series','',
      '[Ameen et al. (2024)](https://doi.org/10.1002/jeq2.20618), Figure 3: 36 clearly identifiable interior circle markers digitised for 1-µm PS spheres, retaining the two plotted R1/R2 labels. The fitted dashed curves were excluded.','',
      '- Retain C/C0 and time; also calculate dimensionless throughput Qt/(AL) using the stated flow and column dimensions. This is **not PV** until divided by measured porosity. The selected points cover the rise/plateau/fall interior, not the complete tails; no cumulative recovery was integrated from them.',
      '- Source-reported recovery is about 24.5% for the 1-µm spheres and 31% for roughly 1.4-µm fragments. This is injected-particle recovery, not initial-resident release, and the fragments are not fibres.',
      '- The sphere/sand median size ratio is about 0.00105. Diffusion, attachment and solution chemistry may matter at this size; curve resemblance alone cannot establish validity of our nonadhesive rigid-body model.','',
      '## 5. Comparison against our existing evidence','',
      '| Existing output | What can be said now |','|---|---|']
    for g in sim['legacy_static_hydraulic']['groups']:
        lines.append(f"| Historical Stage31, {g['fibre_count']} fibres, {g['mass_percent']:.5f}% dry mass | Mean ratio {g['mean_ratio']:.5f}; range {g['min_ratio']:.5f}–{g['max_ratio']:.5f}; 3 packings × 2 nested placements. |")
    lines+=['| Corrected Stage134 sphere and AR4, one matched start | Both present at 0.5 s; finite numerical screen passed, but no population release curve or concentration response. |','',
      '**Important status distinction:** Stage113 later identified a persistent alternating mode in two archived Stage31 clean flow states. Historical Stage31 “passed” labels do not override that finding. The ratio summary above is archival context only, excluded from a claim of current experimental agreement. No repair or rerun is started by this comparison.',
      '', 'The defensible comparison today is a mechanism map: obstruction can lower conductivity; repacking/weathering can produce a different sign; fibre length can influence trapping. Our verified short-time trajectories are not yet enough to confirm a population-level experimental trend. Missing simulation outcomes stay missing rather than being fitted or inferred.','',
      '## 6. Dimensionless comparison rules','',
      '- Hydraulic response: Rk = K/K0; obstruction index B = 1 − Rk. For unchanged fluid properties, K/K0 = k/k0. A negative B is allowed and means enhancement.',
      '- Concentration: preserve the reported mass basis. If w = mMP/(mMP + ms), solid-volume fraction is φMP = (w/ρMP)/[(w/ρMP)+(1−w)/ρs]. If c = mMP/ms, use (c/ρMP)/[(c/ρMP)+(1/ρs)]. Do not silently interchange these or infer unreported densities.',
      '- Geometry: AR = fibre length/diameter; confinement ratios Lf/dthroat and df/dthroat; sphere ratio dMP/d50. Use actual paired measurements, not an invented common pore diameter. Aspect ratio alone does not capture curvature or flexibility.',
      '- Transport time: t* = U t/L = Qt/(nAL) for constant mean interstitial U = Q/(nA). Ameen throughput Qt/(AL) is recorded separately because porosity was not extracted here. No fitted time shift or timescale.',
      '- Release: FN(t*) = Nwhole-body-downstream(t*)/Ninitial-resident; a mass-based FM must use initial mass. Breakthrough C/Cin, injected recovery, conditional passage CDF and tracked-particle trapping are different observables and remain separate.',
      '- Regime checks: Re = ρf |up−u| deq/μ, density ratio ρp/ρf, and settling ratio |ws|/U. Particle stiffness, friction/adhesion, curvature and dimensionless loading must also be stated if relevant. A dimensionless axis is not proof of dynamic similarity.','',
      '### Values calculated from the existing corrected runs','',
      '| Shape | AR | Equal-volume diameter (µm) | Density ratio | Mean-flow Re based on equal-volume diameter | Advective time Ut/L at 0.5 s |','|---|---:|---:|---:|---:|---:|']
    for s in sim['current_numerically_screened']['sentinels']:
        q=s['dimensionless']
        lines.append(f"| {s['shape']} | {q['AR']:.0f} | {1e6*q['equivalent_volume_diameter_m']:.2f} | {q['density_ratio']:.3f} | {q['Re_mean_flow_equivalent_diameter']:.4f} | {q['advective_time_Ut_over_cell_length']:.5f} |")
    lines+=['','The archived particle-Re maxima are about 0.720 (sphere) and 0.626 (fibre), distinct from the small mean-flow Re above. Do not classify experimental and simulated particle motion from imposed water speed alone. The current time span is about 0.011 advective column times, not a completed population washout.','',
      '## Output and stopping point','',
      '- `measurements.json`: source coordinates, values, units, SD where reported, sensitivity envelopes, missingness and denominators.',
      '- `simulation_comparison.json`: archival ratios plus source-bound current sentinel status, explicitly separated.',
      '- `audit.json`: source/output hashes and checks. Originals and all simulation records remain unchanged.',
      '- Next publication step is an evidence-led outline/caption plan using these distinctions. No calibration loop, new physics job, manuscript or publication figure has been started.','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--out',required=True); args=parser.parse_args()
    out=Path(args.out).resolve()
    assert out.parent==BASE and not out.exists(), 'Use a new direct child directory; never overwrite.'
    bind(__file__)
    data={'aminzadeh':aminzadeh(),'yu':yu(),'cohen':cohen(),'ameen':ameen(),'simulation':simulations()}
    assert len(data['aminzadeh']['rows'])==18
    assert sum(r['K_over_K0'] is not None for r in data['yu']['rows'])==23
    assert sum(r['analysed'] for r in data['cohen']['rows'])==120
    assert len(data['ameen']['rows'])==36
    for block in ['aminzadeh','yu']:
        for r in data[block]['rows']:
            if r['K_over_K0'] is not None and r['concentration_mass_percent']==0:
                assert r['K_over_K0']==1.
    out.mkdir()
    (out/'measurements.json').write_text(json.dumps({k:v for k,v in data.items() if k!='simulation'},indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    (out/'simulation_comparison.json').write_text(json.dumps(data['simulation'],indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    (out/'TREND_COMPARISON.md').write_text(report(data),encoding='utf-8')
    unchanged=all(sha(p)==h for p,h in BOUND.items()); assert unchanged
    audit={'purpose':'trend consistency only; zero fitted parameters; zero simulations launched',
           'inputs_sha256':BOUND,'inputs_unchanged_after_analysis':unchanged,
           'counts':{'Aminzadeh_bars':18,'Yu_means':23,'Yu_unrecoverable_points':1,'Cohen_count_bins':3,'Ameen_observed_marker_subset':36},
           'checks':['control ratios exactly one','Aminzadeh 5% ratios within 0.025 of prose approximate reductions','Yu unique vector errorbars','Cohen count closure 120','Ameen coloured marker support and centre correction <=3px','Stage134 CPD6 record hashes verified','Stage134 endpoint times and event classes verified'],
           'limitations':['digitisation bounds are not experimental confidence intervals','Ameen subset is not full BTC and not used for integral recovery','legacy Stage31 not requalified','current corrected model has no population release trend'],
           'outputs_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    (out/'audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'counts':audit['counts'],'source_files_unchanged':unchanged},indent=2))


if __name__=='__main__':
    main()
