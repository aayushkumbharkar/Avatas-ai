import pytest
from pydantic import ValidationError
from backend.app.schemas.bias_analysis import DatasetSchema

@pytest.fixture
def valid_dataset_data():
    return {
        "data": [
            {"feature1": 1, "feature2": "A", "label": 0, "protected": "X"},
            {"feature1": 2, "feature2": "B", "label": 1, "protected": "Y"},
            {"feature1": 3, "feature2": "A", "label": 1, "protected": "X"},
        ],
        "feature_names": ["feature1", "feature2"],
        "label_name": "label",
        "protected_attributes": ["protected"],
        "favorable_label": 1,
        "unfavorable_label": 0,
        "metadata": {"dataset_name": "Test Dataset"}
    }

def test_dataset_schema_valid(valid_dataset_data):
    try:
        DatasetSchema(**valid_dataset_data)
    except ValidationError as e:
        pytest.fail(f"Valid data failed validation: {e}")

def test_dataset_schema_empty_protected_attributes(valid_dataset_data):
    invalid_data = valid_dataset_data.copy()
    invalid_data["protected_attributes"] = []

    with pytest.raises(ValidationError) as excinfo:
        DatasetSchema(**invalid_data)

    assert "protected_attributes list cannot be empty" in str(excinfo.value).lower()

def test_dataset_schema_identical_labels(valid_dataset_data):
    invalid_data = valid_dataset_data.copy()
    invalid_data["favorable_label"] = 1
    invalid_data["unfavorable_label"] = 1

    with pytest.raises(ValidationError) as excinfo:
        DatasetSchema(**invalid_data)

    assert "favorable_label and unfavorable_label must be distinct" in str(excinfo.value).lower()

def test_dataset_schema_label_name_not_in_data_columns_is_allowed_by_schema(valid_dataset_data):
    # Schema itself doesn't validate if label_name is in data's dict keys.
    # This validation happens at the endpoint/router level.
    data_with_missing_label_col = valid_dataset_data.copy()
    data_with_missing_label_col["label_name"] = "non_existent_label"
    try:
        DatasetSchema(**data_with_missing_label_col)
    except ValidationError:
        pytest.fail("Schema should not fail if label_name is not in data column keys itself; this is router logic.")

def test_dataset_schema_protected_attr_not_in_data_columns_is_allowed_by_schema(valid_dataset_data):
    # Similar to label_name, schema doesn't validate if protected_attributes are in data's dict keys.
    data_with_missing_protected_col = valid_dataset_data.copy()
    data_with_missing_protected_col["protected_attributes"] = ["non_existent_protected_attr"]
    try:
        DatasetSchema(**data_with_missing_protected_col)
    except ValidationError:
        pytest.fail("Schema should not fail if protected_attributes not in data col keys; this is router logic.")
