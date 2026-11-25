"""Comprehensive text and data tables for FraudGuard 50-Page Report."""

import csv
from pathlib import Path

# --- Preliminaries Data ---
TEAM_MEMBERS = [
    ["Harshit Pahuja", "S24CSEU0736"],
    ["Rachit Nain", "S24CSEU2646"],
    ["Man Mohan Gaur", "S24CSEU2012"],
    ["Kunal Sehrawat", "S24CSEU2638"],
    ["Bhumi Jindal", "S24CSEU0884"],
]

TOC_ITEMS = [
    ["CHAPTER 1: PROBLEM ANALYSIS AND INTRODUCTION", "1"],
    ["   1.1 Background of the Study & FinTech Context", "1"],
    ["   1.2 The Big Data Paradigm: The 5Vs of Financial Transactions", "3"],
    ["   1.3 Problem Statement & Core FinTech Challenges", "5"],
    ["   1.4 Real-World Adversarial Evasion & Fraud Topologies", "7"],
    ["   1.5 Research Objectives & Quantifiable Engineering Goals", "9"],
    ["   1.6 Alignment with UN Sustainable Development Goals (SDGs)", "11"],
    ["   1.7 Organization of the Report", "13"],
    ["CHAPTER 2: PROJECT DESIGN AND METHODOLOGY", "14"],
    ["   2.1 State-of-the-Art Literature Review", "14"],
    ["   2.2 Comprehensive 12-Paper Comparative Literature Matrix", "17"],
    ["   2.3 Deep Learning vs. Gradient Boosted Trees on Tabular Data", "19"],
    ["   2.4 End-to-End System Architecture & Spark Catalyst Model", "21"],
    ["   2.5 Mathematical Formulations & Metric Foundation", "24"],
    ["   2.6 Data Provenance & Cross-Dataset Profiles", "27"],
    ["CHAPTER 3: PROJECT IMPLEMENTATION AND ENGINEERING", "29"],
    ["   3.1 Experimental Environment & Technology Stack", "29"],
    ["   3.2 Spark Data Ingestion, Schema Casting & Join Validation", "31"],
    ["   3.3 Missingness Profiling & Feature Pruning Protocols", "33"],
    ["   3.4 Leakage-Free Splitting & Deterministic Group Hashing", "35"],
    ["   3.5 Spark ML Feature Engineering Transformation Pipelines", "38"],
    ["   3.6 The Five Supervised Machine Learning Classifiers", "40"],
    ["   3.7 Validation Hyperparameter Tuning Protocol", "43"],
    ["   3.8 Automated PyTest Regression Suite Architecture", "45"],
    ["CHAPTER 4: PROJECT RESULTS, DISCUSSION AND BI", "47"],
    ["   4.1 Exploratory Data Analysis & Empirical Fraud Signatures", "47"],
    ["   4.2 Held-Out Classifier Evaluation & Comparative Diagnostics", "50"],
    ["   4.3 Validation-Based Operational Model Selection Audit", "53"],
    ["   4.4 Decision Threshold Scanning & Financial Risk Optimization", "55"],
    ["   4.5 Interactive Microsoft Power BI Business Intelligence Dashboard", "58"],
    ["   4.6 Power BI Semantic Model DAX Measures Reference", "61"],
    ["   4.7 Methodological Discussion & Empirical Insights", "63"],
    ["CHAPTER 5: PROJECT CONCLUSION AND FUTURE SCOPE", "65"],
    ["   5.1 Conclusion & Major Engineering Takeaways", "65"],
    ["   5.2 Academic Contributions & Technical Milestones", "66"],
    ["   5.3 Team Member Contributions & Project Management", "67"],
    ["   5.4 Technical Limitations & Production Boundaries", "68"],
    ["   5.5 Future Scope & Production Roadmap", "69"],
    ["   5.6 Academic References (IEEE Style)", "70"],
    ["APPENDIX A: Implementation Evidence & PyTest 21/21 Verification Logs", "73"],
    ["APPENDIX B: Comprehensive Feature Dictionaries (IEEE-CIS & ULB)", "76"],
    ["APPENDIX C: Core PySpark Pipeline Source Code Listings", "79"],
]
