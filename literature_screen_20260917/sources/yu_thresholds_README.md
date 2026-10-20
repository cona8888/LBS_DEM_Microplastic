# ManuscriptThresholdsReanalysisYuetal.2023
Data analysis workflow to study non-linear and threshold dynamics on soil physical properties in response to microplastics, reusing the dataset from Yu et al., 2023. 

## Contents
- `thresholdfunctionsv2.R` – helper functions for model selection and threshold detection.
- `thresholdfinal.R` – main script running the workflow (requires helper functions).

The file **`Yu2023_ThresholdFinal.R`** contains the final, clean version of the code.

## Requirements
- **R version:** 2023.09.1+494
- **Packages:**
  - dplyr 1.1.4
  - tidyr 1.3.1
  - tibble 3.2.1
  - ggplot2 3.5.1
  - patchwork 1.3.1
  - mgcv 1.9.1
  - chngpt 2024.11.15
  - segmented 2.1.4
  - glue 1.7.0
  - rlang 1.1.4
  - psych 2.5.6

## How to run
1. Clone or download this repository.
2. Open `thresholdfunctionsv2.R` and `thresholdfinal.R` in R or RStudio.
3. Run the script to reproduce the analysis (make sure all required packages are installed).

## Citation
If you use this code, please cite the corresponding manuscript: [Manuscript in preparation].

## License
This repository is released under the MIT License.
