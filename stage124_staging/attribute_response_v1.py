"""Finite-level amplitude attribution; no fitted parameters or convergence claim."""
import numpy as np
import mean_offset_diagnostic_v1 as job
api=job.api

def old_group(shape,cpd):
    owner=job.previous if shape==api.SHAPES[0] else job.previous.previous
    d=api.read(owner.DESIGN);e=api.read(owner.EVAL/'independent_evaluation_01/results.json')
    group=next(g for g in e['groups'] if g['name']==f'CPD{cpd}_{shape}')
    done=api.read(owner.RUN/'completion.json')
    entries=[next(e for e in done['ledger'] if e['case_id']==name) for name in group['ids']]
    records=[api.read(e['last_record']) for e in entries]
    spec=next(c['spec'] for c in d['cases'] if c['id']==group['ids'][-1])
    return records,spec,entries

def distance(r,s,b,vscale,fibre):
    x=np.asarray(r['position_m'])-s['position_m']
    v=np.asarray(r['velocity_generalized'][:3])-s['velocity_generalized'][:3]
    p=np.asarray(r['orientation']);q=np.asarray(s['orientation'])
    return {'position':float(np.linalg.norm(x)/b),'velocity':float(np.linalg.norm(v)/vscale),
        'axis':float(np.arccos(np.clip(abs(np.dot(p,q)),0,1))) if fibre else 0.}

def tests():
    # Explicitly exercise a nonzero perturbation that cannot explain the remainder,
    # and a noise-dominated example which must remain unresolved.
    def decide(a,r,ea,ec,eb):return max(0,r-ec-eb)>a+ea+ec
    return {'small_amplitude_detected':decide(.01,.1,.005,.005,.005),
        'noise_dominated_unresolved':not decide(.01,.03,.02,.02,.02),
        'amplitude_dominant_unresolved':not decide(.1,.01,0,0,0),
        'equality_unresolved':not decide(.1,.1,0,0,0),
        'vector_identity':np.array_equal(np.array([1.,2.,3.])-np.array([0.,3.,1.]),(np.array([1.,2.,3.])-np.array([2.,2.,2.]))+(np.array([2.,2.,2.])-np.array([0.,3.,1.])))}

def analyze(d,records,temporal_passed):
    self_tests=tests();api.require(all(self_tests.values()),'attribution self-test failed')
    if not temporal_passed:return {'status':'unresolved_temporal_or_health_gate','tests':self_tests}
    rows=[];bindings={};endpoints={}
    for shape in api.SHAPES:
        ar,sa,ae=old_group(shape,2);br,sb,be=old_group(shape,4)
        names=next(g['ids'] for g in d['groups'] if g['name']==f'CPD2_{shape}')
        cr=[records[n] for n in names]
        for entry in ae+be:bindings[entry['last_record']]=entry['record_sha256']
        A,B,C=[r[-1]['result'] for r in [ar,br,cr]]
        b=sa['config']['prolate_semiaxes_m'][1];scale=max(np.linalg.norm(B['velocity_generalized'][:3]),sb['field_metadata']['achieved_mean_interstitial_velocity_m_s'])
        fibre=shape==api.SHAPES[1]
        total=distance(A,B,b,scale,fibre);amp=distance(A,C,b,scale,fibre);remaining=distance(C,B,b,scale,fibre)
        noise=[distance(r[-2]['result'],r[-1]['result'],b,scale,fibre) for r in [ar,br,cr]]
        mult=d['attribution']['noise_proxy_multiplier'];screen={}
        for k in total:
            ea,eb,ec=[mult[n] if False else mult*n[k] for n in noise]
            lower=max(0.,remaining[k]-ec-eb);upper=amp[k]+ea+ec
            screen[k]={'total_difference':total[k],'amplitude_effect':amp[k],'remaining_difference':remaining[k],
                'twice_adjacent_level_differences':{'A':ea,'B':eb,'C':ec},'remainder_lower_proxy':lower,'amplitude_upper_proxy':upper,
                'mean_offset_alone_insufficient_under_screen':bool(lower>upper),
                'interpretation':'Finite-level resolution diagnostic, not a rigorous continuum-error confidence bound.'}
        closure={}
        for key,normalizer in [('position_m',b),('velocity_generalized',scale)]:
            u,v,w=[np.asarray(r[key][:3]) for r in [A,B,C]]
            residual=np.linalg.norm(((u-v)-((u-w)+(w-v)))/normalizer)
            api.require(residual<=d['attribution']['closure_max'],'attribution vector closure failure')
            closure[key]=float(residual)
        rows.append({'shape':shape,'fixed_velocity_scale_m_s':float(scale),'minor_radius_m':b,'metrics':screen,'vector_closure':closure})
        endpoints[shape]={'A':A,'B':B,'C':C,'initial_x_m':sa['initial_state']['position_m'][0]}
    contrast={}
    for field in ['A','B','C']:
        f,s=[endpoints[shape] for shape in reversed(api.SHAPES)]
        contrast[field]=(f[field]['position_m'][0]-f['initial_x_m'])-(s[field]['position_m'][0]-s['initial_x_m'])
    api.verify_mapping(bindings)
    return {'status':'finite_level_attribution_complete','tests':self_tests,'rows':rows,'reused_records':bindings,
        'downstream_travel_fibre_minus_sphere_m':contrast,'contrast_label':'One sentinel at 0.5 s; descriptive travel contrast, not release fraction or population shape effect.'}

def fixed_pose_probe(d):
    f2,g,m2=job.ORIGINAL_LOAD(2,1.,2);f4,_,m4=job.ORIGINAL_LOAD(2,1.,4);fc,_,_=job.diagnostic_load(2,1.,2)
    U=m4['achieved_mean_interstitial_velocity_m_s'];L=m2['cell_length_m'];dx=f2.dx
    rows=[];inputs={}
    for cpd in [2,4]:
        _,_,entries=old_group(api.SHAPES[1],cpd)
        entry=entries[-1];record_path=job.ROOT/entry['last_record']
        path=record_path.parent/'accepted_intervals.json';inputs[str(path)]=api.sha(path);dense=api.read(path)
        ids=np.unique(np.linspace(0,len(dense)-1,d['field_probe']['samples_per_original_finest_path']).round().astype(int))
        for i in ids:
            state=dense[int(i)];x=np.asarray(state['position_m']);u2,G2=f2.sample(x);u4,G4=f4.sample(x);uc,Gc=fc.sample(x)
            delta=x-g['sand_centres_m'];delta-=np.round(delta/L)*L
            clearance=float(np.min(np.linalg.norm(delta,axis=1)-g['sand_radii_m']))
            velclosure=float(np.linalg.norm((u2-u4)-((u2-uc)+(uc-u4)))/U)
            gradclosure=float(np.linalg.norm((G2-G4)-((G2-Gc)+(Gc-G4)))*dx/U)
            api.require(max(velclosure,gradclosure)<=d['attribution']['closure_max'],'fixed-pose decomposition failed')
            rows.append({'source_path_cpd':cpd,'accepted_index':int(i),'time_s':state['time_s'],'position_m':x.tolist(),
                'centre_to_grain_surface_clearance_m':clearance,'near_wall':clearance<=2*dx,
                'velocity_difference_over_U4':float(np.linalg.norm(u2-u4)/U),'amplitude_velocity_effect_over_U4':float(np.linalg.norm(u2-uc)/U),
                'remaining_velocity_difference_over_U4':float(np.linalg.norm(uc-u4)/U),
                'remaining_gradient_difference_over_U4_by_dx2':float(np.linalg.norm(Gc-G4)*dx/U),
                'velocity_closure':velclosure,'gradient_closure':gradclosure})
    return {'rows':rows,'input_hashes':inputs,'sampling':'42 path-conditioned fixed poses, not independent samples or a whole-pore population.',
        'summary':[{'near_wall':near,'count':len(sub),**{k:float(np.median([r[k] for r in sub])) for k in ['velocity_difference_over_U4','amplitude_velocity_effect_over_U4','remaining_velocity_difference_over_U4','remaining_gradient_difference_over_U4_by_dx2']}} for near in [True,False] if (sub:=[r for r in rows if r['near_wall']==near])]}
