"""
Template for analysing multiphase ASL data

This template applies bias correction with Michael Chappell's
additional bias reduction
"""

BIASCORR_MC_YAML = """
Processing:

  # Initial biased run
  - Fabber:
      data: %(data)s
      roi: %(roi)s
      model-group: asl
      model:  asl_multiphase
      method: spatialvb
      PSP_byname1: phase 
      PSP_byname1_type: N
      PSP_byname2: mag 
      PSP_byname2_type: M
      PSP_byname3: offset 
      PSP_byname3_type: M 
      max-iterations: 10
      repeats: 1
      nph: %(nph)i
      modfn: fermi
      alpha: 70
      beta: 19
      save-mean:

  # ... which is used to segment 
  - Supervoxels:
      data: mean_phase
      roi: %(roi)s
      n-supervoxels: %(n_supervoxels)i
      compactness: %(compactness)f
      sigma: %(sigma)f
      output-name: sv

  # So we do not overwrite original results
  - RenameData:
      mean_phase: mean_phase_orig
      mean_mag: mean_mag_orig
      mean_offset: mean_offset_orig
      
  # Michael's suggested approach - average signal in ROI regions
  # to increase SNR and fit phase which should be less biased
  - MeanValues:
      data: %(data)s
      roi: sv
      output-name: data_sv

  - Fabber:
      data: data_sv
      roi: %(roi)s
      model-group: asl
      model:  asl_multiphase
      method: spatialvb
      PSP_byname1: phase
      PSP_byname1_type: N 
      PSP_byname2: mag 
      PSP_byname2_type: M
      PSP_byname3: offset 
      PSP_byname3_type: M 
      max-iterations: 10
      repeats: 1
      nph: %(nph)i
      modfn: fermi
      alpha: 70
      beta: 19
      save-mean:

  # Create phase prior from results
  - MeanValues:
      data: mean_phase
      roi: sv
      output-name: phase_prior_sv

  # So we do not overwrite original results
  - RenameData:
      mean_phase: mean_phase_sv
      mean_mag: mean_mag_sv
      mean_offset: mean_offset_sv
      
  # Final run to fit mag and offset with fixed phase
  - Fabber:
      data: %(data)s
      roi: %(roi)s
      model-group: asl
      model:  asl_multiphase
      method: spatialvb
      PSP_byname1: phase 
      PSP_byname1_image: phase_prior_sv
      PSP_byname1_prec: 1e6
      PSP_byname1_type: I 
      PSP_byname2: mag 
      PSP_byname2_type: M
      PSP_byname3: offset 
      PSP_byname3_type: M 
      max-iterations: 10
      repeats: 1
      nph: %(nph)i
      modfn: fermi
      alpha: 70
      beta: 19
      save-mean:
      save-noise-mean:
      save-modelfit:
"""

# Template for analysing multiphase ASL data
#
# This template applies bias correction
BIASCORR_YAML = """
Processing:

  # Initial biased run
  - Fabber:
      data: %(data)s
      roi: %(roi)s
      model-group: asl
      model:  asl_multiphase
      method: spatialvb
      PSP_byname1: phase 
      PSP_byname1_type: N
      PSP_byname2: mag 
      PSP_byname2_type: M
      PSP_byname3: offset 
      PSP_byname3_type: M 
      max-iterations: 10
      repeats: 1
      nph: %(nph)i
      modfn: fermi
      alpha: 70
      beta: 19
      save-mean:

  # ... which is used to segment 
  - Supervoxels:
      data: mean_phase
      roi: %(roi)s
      n-supervoxels: %(n_supervoxels)i
      compactness: %(compactness)f
      sigma: %(sigma)f
      output-name: sv

  # So we do not overwrite original results
  - RenameData:
      mean_phase: mean_phase_orig
      mean_mag: mean_mag_orig
      mean_offset: mean_offset_orig

  # Create phase prior from results
  - MeanValues:
      data: mean_phase
      roi: sv
      output-name: phase_prior_sv
      
  # Final run to fit mag and offset with fixed phase
  - Fabber:
      data: %(data)s
      roi: %(roi)s
      model-group: asl
      model:  asl_multiphase
      method: spatialvb
      PSP_byname1: phase 
      PSP_byname1_image: phase_prior_sv
      PSP_byname1_prec: 10000000
      PSP_byname1_type: I 
      PSP_byname2: mag 
      PSP_byname2_type: M
      PSP_byname3: offset 
      PSP_byname3_type: M 
      max-iterations: 10
      repeats: 1
      nph: %(nph)i
      modfn: fermi
      alpha: 70
      beta: 19
      save-mean:
      save-noise-mean:
      save-modelfit:
"""

# Optional template to remove temporary results
DELETE_TEMP = """
  - Delete:
      data_sv:
      phase_prior_sv:
      mean_phase_orig:
      mean_mag_orig:
      mean_offset_orig:
      mean_phase_sv:
      mean_mag_sv:
      mean_offset_sv:
      noise_means:
      sv:
"""

# Template for analysing multiphase ASL data
#
# This template does not include bias correction
BASIC_YAML = """
Processing:

  - Fabber:
      data: %(data)s
      roi: %(roi)s
      model-group: asl
      model:  asl_multiphase
      method: spatialvb
      PSP_byname1: phase 
      PSP_byname1_type: N
      PSP_byname2: mag 
      PSP_byname2_type: M
      PSP_byname3: offset 
      PSP_byname3_type: M 
      max-iterations: 10
      repeats: 1
      nph: %(nph)i
      modfn: fermi
      alpha: 70
      beta: 19
      save-mean:
"""
