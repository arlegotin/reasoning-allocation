import builtins
import os

import pytest

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


_THREAD_KEYS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
)


@pytest.mark.parametrize("initially_set", [False, True], ids=["unset", "nondefault"])
@pytest.mark.parametrize("outcome", ["success", "dependency_failure", "native_failure"])
def test_native_smoke_restores_caller_thread_environment(monkeypatch, initially_set, outcome):
    before = {}
    for index, key in enumerate(_THREAD_KEYS):
        value = str(index + 3) if initially_set else None
        before[key] = value
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    if outcome == "dependency_failure":
        original_import = builtins.__import__

        def unavailable(name, *args, **kwargs):
            if name == "pyscipopt":
                raise ImportError("injected dependency failure")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", unavailable)
        with pytest.raises(ImportError, match="injected dependency failure"):
            native_smoke()
    elif outcome == "native_failure":
        import pyscipopt

        def cannot_initialize(*args, **kwargs):
            raise RuntimeError("injected native initialization failure")

        monkeypatch.setattr(pyscipopt, "Model", cannot_initialize)
        with pytest.raises(RuntimeError, match="injected native initialization failure"):
            native_smoke()
    else:
        result = native_smoke()
        assert result["thread_environment_before"] == before
        assert result["thread_environment"] == {key: "1" for key in _THREAD_KEYS}
        assert result["parameters"]["parallel/maxnthreads"] == 1
        assert result["parameters"]["lp/threads"] == 1

    assert {key: os.environ.get(key) for key in _THREAD_KEYS} == before
