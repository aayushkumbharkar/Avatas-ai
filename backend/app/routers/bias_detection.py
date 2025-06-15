from fastapi import APIRouter, HTTPException, Depends, Response
import pandas as pd
import logging
from typing import Optional # For query parameter

from ..schemas.bias_analysis import DatasetSchema
from ..auth.dependencies import get_current_active_user
from ..auth.schemas import User
from ..reporting.pdf_generator import generate_bias_report_pdf # PDF Report

# AIF360 Imports
from aif360.datasets import BinaryLabelDataset
from aif360.metrics import ClassificationMetric

# Scipy for statistical significance
from scipy.stats import chi2_contingency
import numpy as np # For constructing tables

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analyze")
async def analyze_bias(
    payload: DatasetSchema,
    current_user: User = Depends(get_current_active_user),
    format: Optional[str] = None # Query parameter for output format
):
    """
    Analyzes the dataset for fairness and bias metrics using AIF360.
    Optionally returns a PDF report if format=pdf.
    Requires authentication.
    """
    warnings = []

    try:
        df = pd.DataFrame(payload.data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error converting data to DataFrame: {str(e)}")

    if payload.label_name not in df.columns:
        raise HTTPException(status_code=400, detail=f"Label name '{payload.label_name}' not found.")
    for attr in payload.protected_attributes:
        if attr not in df.columns:
            raise HTTPException(status_code=400, detail=f"Protected attribute '{attr}' not found.")

    try:
        # --- Prepare data for AIF360 BinaryLabelDataset ---
        # AIF360 expects labels to be 0 or 1 for some metrics/algorithms.
        # We'll map favorable_label to 1 and unfavorable_label to 0.
        # This mapping should be done carefully if the original labels are not already 0/1.
        df_aif = df.copy()

        # Ensure label column is numeric for AIF360 processing if it's not already
        # This is a common requirement for many internal AIF360 functions
        try:
            df_aif[payload.label_name] = pd.to_numeric(df_aif[payload.label_name])
            payload.favorable_label = pd.to_numeric(payload.favorable_label)
            payload.unfavorable_label = pd.to_numeric(payload.unfavorable_label)
        except ValueError:
            # If labels are not directly convertible to numeric (e.g. string like "yes", "no")
            # we need to map them.
            # Forcing a map: favorable -> 1, unfavorable -> 0
            mapping = {payload.favorable_label: 1, payload.unfavorable_label: 0}
            df_aif[payload.label_name] = df_aif[payload.label_name].replace(mapping)

            # Check if all labels are mapped, if not, there's an issue.
            if not df_aif[payload.label_name].isin([0, 1]).all():
                 raise HTTPException(
                    status_code=400,
                    detail=f"Label column '{payload.label_name}' contains values other than the defined favorable/unfavorable labels after mapping. Ensure only two distinct label values are present."
                )
            payload.favorable_label = 1
            payload.unfavorable_label = 0


        privileged_groups = []
        unprivileged_groups = []

        for attr in payload.protected_attributes:
            # Ensure protected attribute columns are not all NaN, which can cause issues.
            if df_aif[attr].isnull().all():
                raise HTTPException(status_code=400, detail=f"Protected attribute '{attr}' contains only NaN values.")

            # Attempt to convert to numeric if possible, otherwise use as is (AIF360 handles categorical)
            try:
                df_aif[attr] = pd.to_numeric(df_aif[attr])
                unique_sorted_values = sorted(df_aif[attr].dropna().unique())
            except ValueError: # If not numeric, treat as categorical
                unique_sorted_values = sorted(df_aif[attr].dropna().astype(str).unique())


            if not unique_sorted_values:
                 raise HTTPException(status_code=400, detail=f"Protected attribute '{attr}' has no unique non-NaN values.")

            # Temporary Solution for privileged_classes: Assume first unique sorted value is privileged
            # This might not always be correct and is a simplification.
            assumed_privileged_value = unique_sorted_values[0]
            privileged_groups.append({attr: assumed_privileged_value})

            # All other values are unprivileged
            if len(unique_sorted_values) > 1:
                for val in unique_sorted_values[1:]:
                    unprivileged_groups.append({attr: val})
            else: # Only one value for this attribute, so no unprivileged group based on it.
                  # This case might need more sophisticated handling in AIF360 depending on metric.
                  # For now, ClassificationMetric might handle it or ignore this attribute for some metrics.
                  pass

            msg = (f"For protected attribute '{attr}', privileged group was assumed to be "
                   f"[{assumed_privileged_value}]. Unprivileged groups: values other than "
                   f"'{assumed_privileged_value}'. This is an assumption based on data order "
                   "and may not reflect true privilege. Consider adding explicit privileged_groups "
                   "to the DatasetSchema for accurate analysis.")
            warnings.append(msg)
            logger.warning(msg)

        # Ensure there's at least one unprivileged group for ClassificationMetric to work meaningfully.
        # This logic might need refinement based on specific AIF360 metric requirements.
        if not unprivileged_groups and len(payload.protected_attributes) > 0:
            # This scenario can happen if all protected attributes have only one unique value.
            # AIF360 metrics might not be meaningful. For now, we'll let it proceed but add a warning.
            msg = ("No distinct unprivileged groups could be determined based on the provided protected attributes "
                   "and data. Bias metrics might not be meaningful or calculable for all attributes.")
            warnings.append(msg)
            logger.warning(msg)


        dataset_true = BinaryLabelDataset(
            df=df_aif,
            label_name=payload.label_name,
            protected_attribute_names=payload.protected_attributes,
            favorable_label=float(payload.favorable_label), # AIF360 often expects float
            unfavorable_label=float(payload.unfavorable_label),
            # privileged_classes needs a list of lists, where each inner list is a value for a protected attribute
            # This part is complex with current AIF360 API if not handled carefully.
            # Using `privileged_groups` directly in ClassificationMetric is usually easier.
            # For BinaryLabelDataset, it's often about specifying which values in protected attributes are privileged.
            # We will pass empty privileged_protected_attributes and handle groups in ClassificationMetric
            instance_weights_name=None
        )

        # --- Assume Predictions (Placeholder) ---
        # Creating a copy for "predictions". For this example, predictions are same as true labels.
        dataset_pred = dataset_true.copy(deepcopy=True)
        # In a real scenario, you'd populate dataset_pred.labels with your model's predictions.
        # dataset_pred.labels = model.predict(dataset_true.features)
        pred_msg = ("Predictions are placeholders (copied true labels). Actual model predictions "
                    "are needed for meaningful bias analysis of model performance.")
        warnings.append(pred_msg)
        logger.warning(pred_msg)

        # --- Calculate Metrics ---
        # Ensure privileged/unprivileged groups are correctly formatted for ClassificationMetric
        # They should be lists of dictionaries, e.g., [{'sex': 1}], [{'sex': 0}]

        # Filter out empty dictionaries from unprivileged_groups if any were added due to single-value attributes
        # This might not be strictly necessary depending on AIF360 version but good for cleanliness
        valid_unprivileged_groups = [g for g in unprivileged_groups if g]
        valid_privileged_groups = [g for g in privileged_groups if g]

        if not valid_privileged_groups or not valid_unprivileged_groups:
             # This can happen if all protected attributes have only one unique value across the dataset
             # Or if the logic to derive them had issues.
            raise HTTPException(status_code=400, detail="Could not define distinct privileged and unprivileged groups for metric calculation. Ensure protected attributes have variation.")


        metric = ClassificationMetric(
            dataset_true,
            dataset_pred,
            unprivileged_groups=valid_unprivileged_groups,
            privileged_groups=valid_privileged_groups
        )

        dem_parity_diff = metric.statistical_parity_difference()
        avg_odds_diff = metric.average_odds_difference()

        # --- Statistical Significance Testing ---
        p_value_sp = None
        p_value_tpr = None
        p_value_fpr = None

        # Min expected cell count for chi-squared reliability
        MIN_EXPECTED_CELL_COUNT = 5

        # 1. Statistical Parity (on true labels)
        try:
            # Counts for privileged group
            n_priv = dataset_true.num_instances(privileged=True, favorable=True) + \
                     dataset_true.num_instances(privileged=True, favorable=False)
            fav_priv = dataset_true.num_favorable_outcomes(privileged=True)

            # Counts for unprivileged group
            n_unpriv = dataset_true.num_instances(privileged=False, favorable=True) + \
                       dataset_true.num_instances(privileged=False, favorable=False)
            fav_unpriv = dataset_true.num_favorable_outcomes(privileged=False)

            if n_priv > 0 and n_unpriv > 0 : # Ensure groups are not empty
                table_sp = np.array([
                    [fav_priv, n_priv - fav_priv],
                    [fav_unpriv, n_unpriv - fav_unpriv]
                ])
                if np.any(table_sp < 0): # Should not happen with AIF360 counts
                    raise ValueError("Contingency table for SP has negative values.")

                # Check for low counts
                if np.any(table_sp < MIN_EXPECTED_CELL_COUNT):
                    warnings.append(
                        f"Chi-squared test for demographic parity may be unreliable due to low cell counts in the contingency table: {table_sp.tolist()}."
                    )

                chi2_sp, p_value_sp, _, _ = chi2_contingency(table_sp, correction=False)
            else:
                warnings.append("Could not perform chi-squared test for demographic parity due to empty privileged or unprivileged group(s) in true labels.")

        except Exception as e:
            logger.error(f"Error during chi-squared test for statistical parity: {e}", exc_info=True)
            warnings.append(f"Could not calculate p-value for demographic parity: {str(e)}")

        # 2. True Positive Rate (TPR) Difference (Equal Opportunity)
        # This relies on ClassificationMetric which uses true and predicted labels
        try:
            tp_priv = metric.true_positives(privileged=True)
            fn_priv = metric.false_negatives(privileged=True)
            tp_unpriv = metric.true_positives(privileged=False)
            fn_unpriv = metric.false_negatives(privileged=False)

            # Check if actual positives are zero for any group
            actual_pos_priv = tp_priv + fn_priv
            actual_pos_unpriv = tp_unpriv + fn_unpriv

            if actual_pos_priv > 0 and actual_pos_unpriv > 0:
                table_tpr = np.array([
                    [tp_priv, fn_priv],
                    [tp_unpriv, fn_unpriv]
                ])
                if np.any(table_tpr < 0):
                     raise ValueError("Contingency table for TPR has negative values.")

                if np.any(table_tpr < MIN_EXPECTED_CELL_COUNT):
                     warnings.append(
                        f"Chi-squared test for TPR difference may be unreliable due to low cell counts in the contingency table: {table_tpr.tolist()}."
                    )
                chi2_tpr, p_value_tpr, _, _ = chi2_contingency(table_tpr, correction=False)
            else:
                warnings.append("Could not perform chi-squared test for TPR difference due to no positive instances in privileged or unprivileged group(s).")

        except Exception as e:
            logger.error(f"Error during chi-squared test for TPR difference: {e}", exc_info=True)
            warnings.append(f"Could not calculate p-value for TPR difference: {str(e)}")

        # 3. False Positive Rate (FPR) Difference
        try:
            fp_priv = metric.false_positives(privileged=True)
            tn_priv = metric.true_negatives(privileged=True)
            fp_unpriv = metric.false_positives(privileged=False)
            tn_unpriv = metric.true_negatives(privileged=False)

            # Check if actual negatives are zero for any group
            actual_neg_priv = fp_priv + tn_priv
            actual_neg_unpriv = fp_unpriv + tn_unpriv

            if actual_neg_priv > 0 and actual_neg_unpriv > 0:
                table_fpr = np.array([
                    [fp_priv, tn_priv],
                    [fp_unpriv, tn_unpriv]
                ])
                if np.any(table_fpr < 0):
                    raise ValueError("Contingency table for FPR has negative values.")

                if np.any(table_fpr < MIN_EXPECTED_CELL_COUNT):
                    warnings.append(
                        f"Chi-squared test for FPR difference may be unreliable due to low cell counts in the contingency table: {table_fpr.tolist()}."
                    )
                chi2_fpr, p_value_fpr, _, _ = chi2_contingency(table_fpr, correction=False)
            else:
                warnings.append("Could not perform chi-squared test for FPR difference due to no negative instances in privileged or unprivileged group(s).")

        except Exception as e:
            logger.error(f"Error during chi-squared test for FPR difference: {e}", exc_info=True)
            warnings.append(f"Could not calculate p-value for FPR difference: {str(e)}")

        analysis_results_dict = {
            "message": "Analysis complete.",
            "metrics": {
                "demographic_parity_difference": dem_parity_diff,
                "average_odds_difference": avg_odds_diff,
                "statistical_significance": {
                    "demographic_parity_p_value": p_value_sp,
                    "true_positive_rate_difference_p_value": p_value_tpr,
                    "false_positive_rate_difference_p_value": p_value_fpr
                 }
            },
            "data_summary": {
                "data_shape": df.shape,
                "label_name": payload.label_name,
                "protected_attributes": payload.protected_attributes,
                "favorable_label_original": payload.favorable_label if 'mapping' in locals() else "N/A (was numeric)", # show original if mapped
                "unfavorable_label_original": payload.unfavorable_label if 'mapping' in locals() else "N/A (was numeric)",
                "favorable_label_processed": 1 if 'mapping' in locals() else payload.favorable_label,
                "unfavorable_label_processed": 0 if 'mapping' in locals() else payload.unfavorable_label,
                "assumed_privileged_groups": valid_privileged_groups,
                "assumed_unprivileged_groups": valid_unprivileged_groups
            },
            "warnings": warnings
        }

        if format and format.lower() == "pdf":
            try:
                pdf_bytes = generate_bias_report_pdf(analysis_results_dict)
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=bias_analysis_report.pdf"}
                )
            except Exception as e:
                logger.error(f"Error generating PDF report: {e}", exc_info=True)
                # Fallback to JSON response if PDF generation fails
                analysis_results_dict["pdf_generation_error"] = f"Could not generate PDF: {str(e)}"
                # Add this error to warnings as well so it's visible in JSON
                analysis_results_dict["warnings"].append(f"PDF generation failed: {str(e)}")
                return analysis_results_dict # Return JSON with error message
        else:
            return analysis_results_dict

    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except ValueError as ve: # Catch ValueErrors from Pydantic or AIF360 data issues
        logger.error(f"ValueError during AIF360 processing: {ve}", exc_info=True)
        # If PDF format was requested, this error won't be caught by the PDF generation try-except
        # So we return a JSON response detailing the error.
        # A more sophisticated error handling might be needed for format=pdf here.
        raise HTTPException(status_code=400, detail=f"Data validation or processing error: {str(ve)}")
    except Exception as e:
        logger.error(f"Unexpected error during AIF360 processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during bias analysis: {str(e)}")
