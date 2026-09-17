# Operational Reference Baselines & Skill Scores — AeroCast-Now AI

## 1. Requirement for Meteorological Baselines
In meteorology and nowcasting, an AI model reporting an accuracy of 90% or MAE of 2.5 is completely uninformative if a simple baseline achieves the same or better score.
AeroCast-Now AI requires that all candidate and production models be evaluated alongside two deterministic operational reference baselines:
1. **Persistence Baseline**: Assumes that atmospheric conditions at valid time $T_v$ will remain identical to conditions at initialization time $T_{\text{init}}$:
   $$\hat{Y}_{\text{persistence}}(T_{\text{init}} + \Delta t) = Y(T_{\text{init}})$$
2. **Climatological Baseline**: The long-term historical mean or typical diurnal state for the region during the corresponding month/hour:
   $$\hat{Y}_{\text{climatology}} = \mu_{\text{climate}}(\text{month}, \text{hour})$$

---

## 2. Skill Score Formulation
To establish genuine meteorological value-add, model skill is quantified against the reference baseline:

$$\text{Skill Score (SS)} = 1 - \frac{\text{MSE}_{\text{model}}}{\text{MSE}_{\text{baseline}}}$$

* **$\text{SS} > 0$**: The model outperforms the reference baseline.
* **$\text{SS} = 0$**: The model offers zero value over the reference baseline.
* **$\text{SS} < 0$**: The model performs worse than simple persistence or climatology.

### Production Promotion Requirement
A candidate model **cannot** be promoted to production unless:
$$\text{Skill Score vs. Persistence} > 0 \quad \text{across lead times } +15\text{m, } +30\text{m, and } +45\text{m}$$
$$\text{CSI}_{\text{model}} > \text{CSI}_{\text{persistence}}$$
