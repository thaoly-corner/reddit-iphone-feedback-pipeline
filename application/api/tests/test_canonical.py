from app.canonical import canonical_ios, canonical_model, ios_major, model_generation, model_sort_key


def test_model_variants_fold():
    for raw in ["iPhone 13Pro", "iPhone13 Pro", "iPhone 13 Pro", "İphone 13 Pro", "iphone13pro"]:
        assert canonical_model(raw) == "iPhone 13 Pro"
    assert canonical_model("iPhone 16 Promax") == "iPhone 16 Pro Max"
    assert canonical_model("iPhonese") == "iPhone SE"
    assert canonical_model("iPhonex") == "iPhone X"
    assert canonical_model("iPhone XR") == "iPhone XR"


def test_invalid_models_become_other():
    for raw in ["iPhone 3 Pro", "iPhone 9", "iPhone 3", None, "", "Other / Unspecified", "Galaxy S24"]:
        assert canonical_model(raw) == "Other / Unspecified"


def test_ios():
    assert canonical_ios("iOS 26.4.1") == "iOS 26.4.1"
    assert canonical_ios("iOS 26.5 Beta") == "iOS 26.5 Beta"
    assert canonical_ios("iOS 24.5") == "iOS Unspecified"
    assert canonical_ios("iOS 28") == "iOS Unspecified"
    assert canonical_ios("iOS Beta") == "iOS Unspecified"
    assert ios_major("iOS 26.4.1") == "iOS 26"


def test_generation_and_sort():
    assert model_generation("iPhone 15 Pro Max") == "iPhone 15"
    names = ["iPhone 14", "iPhone 15 Pro Max", "iPhone 15", "Other / Unspecified", "iPhone 15 Pro"]
    assert sorted(names, key=model_sort_key) == [
        "iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max", "iPhone 14", "Other / Unspecified"
    ]
