# 📊 Causal ML — Marketing Uplift Modeling

> **"Don't just find who will buy. Find who will buy *because of* your ad."**

This project builds a full **Causal Inference + Uplift Modeling pipeline** for marketing optimization. It identifies which users an ad will *causally* influence — not just who happens to convert.

---

## 🎯 Problem Statement

Traditional ML asks: *"Who will convert?"*  
Causal ML asks: *"Who will convert **because of** the ad?"*

These are very different questions. Sending ads to people who would buy anyway wastes budget. Sending ads to people who are turned off by ads loses customers. This pipeline finds the **Persuadables** — users where the ad genuinely makes a difference.

---

## 🧠 The 4 Types of Users

```
┌─────────────────┬──────────────────────────────────────┐
│  PERSUADABLES   │  Only buy WITH the ad   → TARGET ✅  │
├─────────────────┼──────────────────────────────────────┤
│  SURE THINGS    │  Buy with OR without ad → WASTEFUL   │
├─────────────────┼──────────────────────────────────────┤
│  LOST CAUSES    │  Won't buy regardless   → SKIP       │
├─────────────────┼──────────────────────────────────────┤
│  SLEEPING DOGS  │  Ad makes them LESS likely → AVOID ❌│
└─────────────────┴──────────────────────────────────────┘
```

---

## 🗂️ Dataset

| Column | Description |
|--------|-------------|
| `f0` – `f11` | 12 anonymized user features |
| `treatment` | Did user receive the ad? (1 = yes, 0 = no) |
| `conversion` | Did user purchase? (1 = yes, 0 = no) |
| `visit` | Did user visit the site? (secondary outcome) |
| `exposure` | User's pre-existing interest level (confounder) |

---

## 🔬 Methodology

### Step 1 — Understand Assignment Types

| Type | Description | Purpose |
|------|-------------|---------|
| **Randomized (A/B)** | Ad shown by coin flip (50/50) | Ground truth benchmark |
| **Biased (Observational)** | Ad shown to interested users | Simulates real-world data |

### Step 2 — Naive Estimator (Baseline)

Simple difference-in-means — assumes data is perfectly randomized (it isn't).

```python
naive_effect = mean(conversion | treated=1) - mean(conversion | treated=0)
```

❌ Produces inflated, biased estimate due to confounding.

### Step 3 — Propensity Score Matching (PSM)

Corrects for selection bias by matching treated users with statistically similar control users.

```
e(x) = P(Treatment = 1 | X = x)   ← trained with RandomForestClassifier
```

Each treated user is matched to a control user within `caliper = 0.05` distance. Balance is verified using **Standardized Mean Difference (SMD < 0.1)**.

### Step 4 — Uplift Modeling

#### T-Learner (Two separate models)
```python
uplift = model_treated.predict_proba(X) - model_control.predict_proba(X)
```
- `model_treated` → trained on treated users only
- `model_control` → trained on control users only

#### S-Learner (Single model)
```python
# Predict with treatment=1 and treatment=0, take difference
uplift = p(Y | T=1, X) - p(Y | T=0, X)
```

### Step 5 — Business Decision

```python
expected_profit = uplift × $100 (revenue) - $1 (ad cost)

if expected_profit > 0 and uplift > 0.01:  → Send Ad
elif uplift < -0.01:                        → Do NOT Send
else:                                       → Neutral
```

---

## 📈 Results

| Method | Estimated Effect | Accuracy |
|--------|-----------------|----------|
| True Effect (Randomized A/B) | Ground truth | ✅ Perfect |
| Naive Estimator (Biased) | Inflated ~3-5× | ❌ Wrong |
| PSM Corrected Effect | ~80% error reduction | ✅ Close |

> PSM recovered the true causal effect from biased observational data with >80% error reduction over the naive estimator.

---

## 🏗️ Project Structure

```
├── model.ipynb                  # Main notebook — full pipeline
├── train_sample.parquet         # Training data
├── test_sample.parquet          # Test data
├── randomized_data.csv          # Synthetic A/B benchmark data
├── biased_data.csv              # Synthetic observational data
├── uplift_t_model.pkl           # Saved T-learner (treated model)
└── uplift_c_model.pkl           # Saved T-learner (control model)
```

---

## ⚙️ Tech Stack

| Library | Use |
|---------|-----|
| `pandas` / `numpy` | Data manipulation |
| `scikit-learn` | RandomForest, NearestNeighbors, PSM |
| `matplotlib` / `seaborn` | Visualization |
| `joblib` | Model serialization |

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install pandas numpy scikit-learn matplotlib seaborn joblib pyarrow

# Run the notebook
jupyter notebook model.ipynb
```

---

## 🔮 Predicting on New Users

```python
import joblib, pandas as pd

model_treated = joblib.load('uplift_t_model.pkl')
model_control = joblib.load('uplift_c_model.pkl')

new_user = pd.DataFrame([[28, 5000, 3, 1, 0, 120, 0.4, 200, 0.2, 6, 1, 0]],
                         columns=[f'f{i}' for i in range(12)])

uplift = model_treated.predict_proba(new_user)[0,1] - \
         model_control.predict_proba(new_user)[0,1]

expected_profit = uplift * 100 - 1  # revenue - ad cost

print(f"Uplift: {uplift:.4f}")
print(f"Decision: {'Send Ad' if expected_profit > 0 else 'Skip'}")
```

---

## 📚 Key Concepts

- **Causal Inference** — Estimating the effect of an action, not just correlation
- **Confounding** — A hidden variable that affects both treatment assignment and outcome
- **Propensity Score** — Probability of receiving treatment given observed features
- **ATE / ATT** — Average Treatment Effect (on the Treated)
- **Uplift** — Individual-level causal effect of treatment

---

## 📖 Further Reading

- [Causal Inference: The Mixtape — Scott Cunningham](https://mixtape.scunning.com/)
- [The Book of Why — Judea Pearl](http://bayes.cs.ucla.edu/WHY/)
- [Uplift Modeling for Clinical Trials — Radcliffe & Surry](https://arxiv.org/abs/1208.1689)

---

## 📝 License

MIT License — free to use and modify.