import os
import shutil
import sys
from uuid import uuid4
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


if os.environ.get("TRITON_TEST_TMP_ROOT"):
    backend_tmp = Path(__file__).resolve().parents[1] / ".tmp"
    test_tmp_root = Path(os.environ["TRITON_TEST_TMP_ROOT"]).resolve()
    if test_tmp_root.parent != backend_tmp.resolve() or not test_tmp_root.name.startswith("postgres-test-"):
        raise RuntimeError("TRITON_TEST_TMP_ROOT deve ser uma pasta postgres-test-* dentro de backend/.tmp.")

    @pytest.fixture
    def tmp_path():
        path = test_tmp_root / uuid4().hex
        path.mkdir(parents=False, exist_ok=False)
        try:
            yield path
        finally:
            resolved = path.resolve()
            if resolved.parent != test_tmp_root:
                raise RuntimeError("Recusa de limpeza fora da pasta temporária criada para este teste.")
            shutil.rmtree(resolved)
