# Causial Inference Engine for Market Attribution

A comprehensive pipeline for estimating causal effects of marketing treatments and predicting individual-level uplift using Propensity Score Matching (PSM) and uplift modeling techniques.

## 📋 Overview

This project implements a complete workflow to:
1. Measure the **true causal impact** of marketing campaigns (ads, emails, etc.)
2. Correct for selection bias using **Propensity Score Matching (PSM)**
3. Predict **individual customer uplift** using S-Learner and T-Learner models

### Key Results Example
```
True Uplift:           0.006632 (0.66%)
Naive Uplift:          0.001172 (0.12%)
Corrected (PSM) Uplift: 0.004176 (0.42%)
Error Reduction:       55.02%
```

## 🏗️ Project Structure
```
marketing-causal-uplift/
├── data/
│   ├── raw/              # Original marketing datasets
│   └── processed/        # Cleaned and preprocessed data
├── src/
│   ├── preprocessing.py  # Data cleaning and feature engineering
│   ├── psm.py           # Propensity Score Matching implementation
│   ├── uplift_models.py # S-Learner and T-Learner implementations
│   └── evaluation.py    # Metrics and visualization
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_psm_analysis.ipynb
│   └── 03_uplift_modeling.ipynb
├── results/
│   ├── figures/         # Plots and visualizations
│   └── reports/         # Summary reports
├── requirements.txt
└── README.md
```

## 🔄 Pipeline Workflow

### 1. Input Data Collection
**Dataset Requirements:**
- `user_id`: Unique customer identifier
- `f0-f11`: Customer features (age, loyalty score, income, activity level, etc.)
- `treatment`: Binary indicator (1 = received ad/email, 0 = control)
- `exposure`: Campaign exposure metrics
- `conversion`: Binary outcome (1 = purchased, 0 = not purchased)

### 2. Data Preprocessing
- Handle missing values (imputation or removal)
- Encode categorical variables (one-hot, label encoding)
- Normalize/scale numeric features (StandardScaler, MinMaxScaler)
- Train/test split for model validation

### 3. Bias & A/B Test Simulation
**Optional simulation for testing:**
- **Randomized assignment**: Generates unbiased "ground truth" causal effect
- **Biased assignment**: Creates confounding to test PSM correction capability

### 4. Naive Estimation (Baseline)
```python
Naive_Effect = mean(Y | T=1) - mean(Y | T=0)
```
- Simple difference in means
- **Biased** due to selection effects (treated users may be inherently different)

### 5. Propensity Score Modeling
- Train Decision Tree or Random Forest to predict: `P(T=1 | X)`
- Each user receives a **propensity score** (probability of treatment)
- Captures likelihood of treatment assignment based on features

### 6. Matching Engine (PSM)
- Match treated users to control users with similar propensity scores
- Create **balanced groups** (treated vs control)
- Remove unmatched users to ensure comparability

### 7. Causal Effect Estimation
```python
ATE = mean(Y_treated) - mean(Y_control)  # After matching
```
- **Average Treatment Effect (ATE)**: True causal impact
- Corrects for confounding bias

### 8. Comparison & Validation
Compare three estimates:
- **Naive Effect**: Biased baseline
- **True Effect**: From randomized simulation (if available)
- **PSM Effect**: Corrected causal estimate

**Metrics:**
- Absolute error reduction
- Percentage improvement over naive approach

### 9. Visualization & Reporting
**Generated Plots:**
- Propensity score distributions (before/after matching)
- Comparison chart: Naive vs True vs PSM effects
- Bayesian credible intervals (optional)

**Summary Report:**
- True uplift
- Corrected uplift (PSM)
- Error reduction percentage
- Confidence intervals

### 10. Uplift Modeling
After confirming causal effect (e.g., +0.42% conversion increase), train uplift models:

#### **S-Learner (Single Model)**
- Train one model on all data with treatment as a feature
- Predict: `Uplift = P(Y|T=1, X) - P(Y|T=0, X)`

#### **T-Learner (Two Models)**
- Train separate models for treated and control groups
- Predict: `Uplift = Model_treated(X) - Model_control(X)`

**Output:** Individual-level uplift scores for targeting high-value customers

## 🚀 Installation
```bash
# Clone repository
git clone https://github.com/yourusername/marketing-causal-uplift.git
cd marketing-causal-uplift

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Requirements
```
numpy>=1.21.0
pandas>=1.3.0
scikit-learn>=1.0.0
matplotlib>=3.4.0
seaborn>=0.11.0
scipy>=1.7.0
xgboost>=1.5.0  # Optional for advanced models
```

## 📊 Usage Example
```python
from src.preprocessing import preprocess_data
from src.psm import PropensityScoreMatching
from src.uplift_models import SLearner, TLearner

# 1. Load and preprocess data
df = preprocess_data('data/raw/campaign_data.csv')

# 2. Estimate causal effect with PSM
psm = PropensityScoreMatching(caliper=0.05)
psm.fit(df[features], df['treatment'])
matched_data = psm.match()
ate = psm.estimate_ate(matched_data)

print(f"Corrected ATE: {ate:.6f}")

# 3. Train uplift models
s_learner = SLearner()
s_learner.fit(df[features], df['treatment'], df['conversion'])

t_learner = TLearner()
t_learner.fit(df[features], df['treatment'], df['conversion'])

# 4. Predict individual uplift
df['uplift_s'] = s_learner.predict_uplift(df[features])
df['uplift_t'] = t_learner.predict_uplift(df[features])

# 5. Target high-uplift customers
top_10_percent = df.nlargest(int(0.1 * len(df)), 'uplift_t')
```

## 📈 Key Metrics

| Metric | Description |
|--------|-------------|
| **ATE** | Average Treatment Effect across all users |
| **CATE** | Conditional ATE (varies by user features) |
| **Uplift** | Individual-level predicted treatment effect |
| **Qini Coefficient** | Measures uplift model performance |
| **AUUC** | Area Under Uplift Curve |

## 🎯 Use Cases

- **Email campaign optimization**: Identify users most likely to respond
- **Ad spend allocation**: Target high-uplift customers
- **Promotional offers**: Personalize discounts based on predicted impact
- **Churn prevention**: Send interventions to users who'll benefit most

## 📚 Methodology References

- **Propensity Score Matching**: Rosenbaum & Rubin (1983)
- **Uplift Modeling**: Radcliffe & Surry (2011)
- **Causal Inference**: Pearl (2009), Imbens & Rubin (2015)

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 👥 Authors

- Your Name - Initial work

## 🙏 Acknowledgments

- Marketing science community for causal inference frameworks
- Open-source contributors to scikit-learn and uplift modeling libraries

---

**Questions?** Open an issue or contact [your.email@example.com]