# Respiration Rate Estimation from Speech

This repository explores respiration rate (RR) estimation from speech audio. It provides a review of state-of-the-art methods, references to relevant datasets, and code adapted from Respiro-en:

"Frame-Wise Breath Detection with Self-Training: An Exploration of Enhancing Breath Naturalness in Text-to-Speech"  
INTERSPEECH 2024 (Official PyTorch implementation).  
Repository: https://github.com/ydqmkkx/Respiro-en

---

## Overview

Respiration is an important physiological biomarker. Speech can serve as a non-invasive modality for estimating respiration rate, offering applications in telehealth, remote monitoring, and speech-based human–computer interaction.

This repository contains:
- Analysis of state-of-the-art papers on respiration estimation from speech.  
- References to datasets used in the literature, with details on availability.  
- Code adapted from Respiro-en for breath detection and respiration modeling.  
- Modular structure for extending and experimenting with speech-to-respiration pipelines.  

---

## State-of-the-Art Analysis

### Measuring Respiration Rate from Speech (2025)
- Introduces speech as a virtual sensor for respiration rate.  
- Validated in noisy environments, achieving reliable agreement with ground truth.  

### Pre-Trained Foundation Models for Respiratory Parameters (2024)
- Uses embeddings from pre-trained foundation models to estimate respiration parameters including respiration rate.  
- Demonstrates improved correlation with belt-derived measurements.  

### Acoustics of Breath Noises in Human Speech (JSLHR, 2024)
- Analyzes the acoustics of inhalations and exhalations during speech.  
- Provides feature insights for breath segmentation and detection.  

### Deep Learning Architectures for Breathing Signal Estimation (Neural Networks, 2021)
- Compares CNN, LSTM, and attention-based models for predicting continuous breathing signals from speech.  
- Respiration rate is derived from peak-to-peak intervals of the estimated signals.  

### ComParE Breathing Sub-Challenge (2020–2021)
- Provides a benchmark for predicting respiration belt signals from conversational speech.  
- Demonstrates the feasibility of speech-based respiration estimation.  

---

## Datasets

| Dataset | Description | Ground Truth | Availability | Link |
|---------|-------------|--------------|--------------|------|
| ComParE 2020 – Breathing Sub-Challenge (UCL-SBM) | Speech recordings with simultaneous respiratory belt traces (25 Hz). Widely used in RR estimation research. | Respiration belt (continuous) | Restricted (request required) | https://www.compare.openaudio.eu/2020/ |
| ERS (Emotional Respiration Speech, ICMI 2022) | Approximately 20 participants, ~400 minutes. Spontaneous speech with piezo belt signals. Respiration frequency (RR) included. | Respiration rate and traces | Restricted (via authors) | https://dl.acm.org/doi/10.1145/3536221.3556602 |
| Coswara (IISc) | Crowdsourced breathing, cough, and speech tasks. Includes controlled breathing conditions (fast/slow, deep/shallow). | No direct RR labels, but derivable | Public | https://github.com/iiscleap/Coswara-Data |
| Apple ML Breath Dataset (2021) | Post-exercise breath audio for respiration rate estimation. | Respiration rate (proprietary) | Not public | https://machinelearning.apple.com/research/respiratory-rate |

---

## Research Directions

- Improved respiration rate estimation using foundation model embeddings (e.g., wav2vec2, HuBERT).  
- Robust breath detection and analysis in noisy environments.  
- Transfer learning across datasets (e.g., Coswara to ComParE/ERS).  
- Applications in telehealth, emotion recognition, and human–computer interaction.  
