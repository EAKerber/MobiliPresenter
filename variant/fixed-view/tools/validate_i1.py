from __future__ import annotations

import importlib.util
from pathlib import Path

I2 = Path(__file__).with_name("validate_i2.py")
SPEC = importlib.util.spec_from_file_location("validate_i2", I2)
assert SPEC and SPEC.loader
validate_i2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_i2)

ValidationError = validate_i2.ValidationError
validate = validate_i2.validate


def main() -> None:
    validate_i2.main()


if __name__ == "__main__":
    main()
