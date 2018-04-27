#
# Options: number of phases, 
#
# Cases:
#   - Case1:
#       Fabber:
#         data: %s
#         nphases: %i
#       Supervoxels:
#         sigma: %f
#         n-supervoxels: %i
#         compactness: %i
#

MULTIPHASE_YAML = """
# Template for analysing multiphase ASL data
Processing:

  # Initial biased run
  - Fabber:
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
      modfn: fermi
      alpha: 70
      beta: 19
      nph: 8
      save-mean:

  # ... which is used to segment 
  - Supervoxels:
      data: mean_phase
      roi: mask
      n-supervoxels: 8
      compactness: 0.01
      sigma: 0.5
      output-name: sv

  # So we do not overwrite original results
  - RenameData:
      mean_phase: mean_phase_orig
      mean_mag: mean_mag_orig
      mean_offset: mean_offset_orig
      
  # Michael's suggested approach - average signal in ROI regions
  # to increase SNR and fit phase which should be less biased
  - MeanValues:
      Id: MC
      roi: sv
      output-name: data_sv

  - Fabber:
      model-group: asl
      model:  asl_multiphase
      data: data_sv
      method: spatialvb
      PSP_byname1: phase
      PSP_byname1_type: N 
      PSP_byname2: mag 
      PSP_byname2_type: M
      PSP_byname3: offset 
      PSP_byname3_type: M 
      max-iterations: 10
      repeats: 1
      modfn: fermi
      alpha: 70
      beta: 19
      nph: 8
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
      modfn: fermi
      alpha: 70
      beta: 19
      nph: 8
      save-mean:
      save-noise-mean:
      save-modelfit:
"""
