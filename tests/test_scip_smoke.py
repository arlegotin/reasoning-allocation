from ra.doctor import native_smoke


def test_native_cover_optimum():
    result = native_smoke()
    assert result["objective"] == 2
    assert result["original_feasible"] is True
    x = result["assignment"]
    assert all(v in (0, 1) for v in x)
    assert x[0] + x[1] >= 1 and x[1] + x[2] >= 1
    assert x[0] + 2 * x[1] + x[2] == 2
    assert result["status"] == "optimal"
