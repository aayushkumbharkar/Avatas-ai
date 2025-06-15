import pytest
from backend.app.reporting.pdf_generator import generate_bias_report_pdf

@pytest.fixture
def sample_analysis_results_for_pdf():
    """
    Provides a sample analysis results dictionary, similar to what the
    bias_detection endpoint would produce.
    """
    return {
        "message": "Analysis complete.",
        "metrics": {
            "demographic_parity_difference": 0.12345,
            "average_odds_difference": -0.05678,
            "statistical_significance": {
                "demographic_parity_p_value": 0.045,
                "true_positive_rate_difference_p_value": 0.150,
                "false_positive_rate_difference_p_value": 0.002
            }
        },
        "data_summary": {
            "data_shape": [100, 5], # rows, columns
            "label_name": "loan_approved",
            "protected_attributes": ["gender", "race"],
            "favorable_label_original": "Yes",
            "unfavorable_label_original": "No",
            "favorable_label_processed": 1,
            "unfavorable_label_processed": 0,
            "assumed_privileged_groups": [{"gender": "Male"}, {"race": "White"}],
            "assumed_unprivileged_groups": [{"gender": "Female"}, {"race": "Non-White"}],
            "metadata": {"source": "test_data.csv"}
        },
        "warnings": [
            "Privileged groups were assumed based on data order.",
            "Predictions are placeholders (copied true labels)."
        ]
    }

def test_generate_pdf_runs_and_produces_bytes(sample_analysis_results_for_pdf):
    try:
        pdf_bytes = generate_bias_report_pdf(sample_analysis_results_for_pdf)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # Optionally, check for PDF magic number
        assert pdf_bytes.startswith(b"%PDF-"), "Output does not look like a PDF"
    except Exception as e:
        pytest.fail(f"generate_bias_report_pdf failed: {e}")

def test_generate_pdf_handles_missing_optional_keys(sample_analysis_results_for_pdf):
    # Test with some optional keys missing to ensure robustness
    partial_results = sample_analysis_results_for_pdf.copy()
    del partial_results["data_summary"]["metadata"]
    partial_results["metrics"]["statistical_significance"] = {} # Empty significance
    partial_results["warnings"] = [] # No warnings

    try:
        pdf_bytes = generate_bias_report_pdf(partial_results)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF-")
    except Exception as e:
        pytest.fail(f"generate_bias_report_pdf failed with missing optional keys: {e}")

def test_generate_pdf_handles_none_values_gracefully(sample_analysis_results_for_pdf):
    results_with_nones = sample_analysis_results_for_pdf.copy()
    results_with_nones["metrics"]["demographic_parity_difference"] = None
    results_with_nones["metrics"]["statistical_significance"]["demographic_parity_p_value"] = None
    results_with_nones["data_summary"]["data_shape"] = None

    try:
        pdf_bytes = generate_bias_report_pdf(results_with_nones)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF-")
    except Exception as e:
        pytest.fail(f"generate_bias_report_pdf failed with None values: {e}")
