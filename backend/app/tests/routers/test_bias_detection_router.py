import pytest
from fastapi.testclient import TestClient
from backend.app.main import app # Import your FastAPI app instance

client = TestClient(app)

@pytest.fixture(scope="module")
def auth_token():
    """Fixture to get an authentication token for testuser."""
    response = client.post(
        "/api/auth/token",
        data={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200, f"Failed to get token: {response.text}"
    return response.json()["access_token"]

@pytest.fixture
def sample_payload_valid():
    """Provides a valid sample payload for bias analysis tests."""
    return {
        "data": [
            {"age": 25, "gender": "Male", "income": 50000, "loan_approved": 1, "education": "Bachelor"},
            {"age": 35, "gender": "Female", "income": 60000, "loan_approved": 0, "education": "Master"},
            {"age": 45, "gender": "Male", "income": 70000, "loan_approved": 1, "education": "PhD"},
            {"age": 22, "gender": "Female", "income": 45000, "loan_approved": 1, "education": "Bachelor"},
            {"age": 50, "gender": "Male", "income": 100000, "loan_approved": 0, "education": "Master"},
            {"age": 30, "gender": "Female", "income": 55000, "loan_approved": 1, "education": "PhD"},
             # Add more data to make significance tests more stable (avoid zero divisions)
            {"age": 28, "gender": "Male", "income": 52000, "loan_approved": 0, "education": "Bachelor"},
            {"age": 32, "gender": "Female", "income": 62000, "loan_approved": 1, "education": "Master"},
            {"age": 40, "gender": "Male", "income": 75000, "loan_approved": 0, "education": "PhD"},
            {"age": 26, "gender": "Female", "income": 48000, "loan_approved": 1, "education": "Bachelor"},
            {"age": 55, "gender": "Male", "income": 110000, "loan_approved": 1, "education": "Master"},
            {"age": 33, "gender": "Female", "income": 58000, "loan_approved": 0, "education": "PhD"},
        ],
        "feature_names": ["age", "income", "education"], # gender is protected
        "label_name": "loan_approved",
        "protected_attributes": ["gender"],
        "favorable_label": 1,
        "unfavorable_label": 0,
        "metadata": {"dataset_id": "loan_applications_v1"}
    }

def test_analyze_bias_success_json(sample_payload_valid, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/bias/analyze", headers=headers, json=sample_payload_valid)

    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    json_response = response.json()
    assert "metrics" in json_response
    assert "demographic_parity_difference" in json_response["metrics"]
    assert "statistical_significance" in json_response["metrics"]
    assert "data_summary" in json_response
    assert "warnings" in json_response

def test_analyze_bias_success_pdf(sample_payload_valid, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/bias/analyze?format=pdf", headers=headers, json=sample_payload_valid)

    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert "attachment; filename=bias_analysis_report.pdf" in response.headers['content-disposition']
    assert len(response.content) > 0

def test_analyze_bias_no_auth(sample_payload_valid):
    response = client.post("/api/bias/analyze", json=sample_payload_valid)
    assert response.status_code == 401  # Unauthorized

def test_analyze_bias_invalid_payload_schema_validation(auth_token, sample_payload_valid):
    headers = {"Authorization": f"Bearer {auth_token}"}
    invalid_payload = sample_payload_valid.copy()
    invalid_payload["protected_attributes"] = [] # This violates DatasetSchema validator

    response = client.post("/api/bias/analyze", headers=headers, json=invalid_payload)
    assert response.status_code == 422  # Unprocessable Entity for Pydantic validation errors

def test_analyze_bias_label_not_in_columns(auth_token, sample_payload_valid):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload_bad_label = sample_payload_valid.copy()
    payload_bad_label["label_name"] = "non_existent_label"

    response = client.post("/api/bias/analyze", headers=headers, json=payload_bad_label)
    assert response.status_code == 400 # Custom validation in endpoint
    assert "not found" in response.json()["detail"].lower()

def test_analyze_bias_protected_attr_not_in_columns(auth_token, sample_payload_valid):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload_bad_protected = sample_payload_valid.copy()
    payload_bad_protected["protected_attributes"] = ["non_existent_protected_attr"]

    response = client.post("/api/bias/analyze", headers=headers, json=payload_bad_protected)
    assert response.status_code == 400 # Custom validation in endpoint
    assert "not found" in response.json()["detail"].lower()

def test_analyze_bias_invalid_data_for_aif360(auth_token, sample_payload_valid):
    headers = {"Authorization": f"Bearer {auth_token}"}
    # Example: data that might cause issues in AIF360, e.g. all same values for a protected attribute
    # or labels that can't be mapped properly to 0/1 after initial favorable/unfavorable definition.
    problematic_payload = sample_payload_valid.copy()
    problematic_payload["data"] = [
        {"age": 25, "gender": "Male", "income": 50000, "loan_approved": 1},
        {"age": 35, "gender": "Male", "income": 60000, "loan_approved": 0}, # Only "Male" for gender
    ]
    problematic_payload["protected_attributes"] = ["gender"]
    # This specific case might lead to "Could not define distinct privileged and unprivileged groups"
    # or similar, which should result in a 400 or 500 from our endpoint's AIF360 error handling.

    response = client.post("/api/bias/analyze", headers=headers, json=problematic_payload)
    # Depending on the exact AIF360 error and how it's caught, this could be 400 or 500.
    # The current error handling for AIF360 issues like this often results in 400.
    assert response.status_code == 400
    assert "could not define distinct privileged and unprivileged groups" in response.json()["detail"].lower()

def test_analyze_bias_pdf_generation_failure_fallback(auth_token, sample_payload_valid, mocker):
    # Mock generate_bias_report_pdf to simulate an error
    mocker.patch(
        "backend.app.routers.bias_detection.generate_bias_report_pdf",
        side_effect=Exception("PDF generation failed miserably")
    )

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/bias/analyze?format=pdf", headers=headers, json=sample_payload_valid)

    assert response.status_code == 200 # Should fallback to JSON
    assert response.headers['content-type'] == 'application/json'
    json_response = response.json()
    assert "pdf_generation_error" in json_response
    assert "Could not generate PDF: PDF generation failed miserably" in json_response["pdf_generation_error"]
    assert any("PDF generation failed: PDF generation failed miserably" in w for w in json_response["warnings"])
