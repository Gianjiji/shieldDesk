import pytest

from shielddesk.domain.value_objects.confidence import Confidence


def test_confidence_accepts_valid_range() -> None:
    assert Confidence(0.0).value == 0.0
    assert Confidence(1.0).value == 1.0
    assert Confidence(0.5).value == 0.5


@pytest.mark.parametrize("invalid", [-0.01, 1.01, -1.0, 2.0])
def test_confidence_rejects_out_of_range(invalid: float) -> None:
    with pytest.raises(ValueError, match="Confidence deve essere in"):
        Confidence(invalid)
