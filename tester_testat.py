import os
import tempfile
import shutil
import pathlib
import importlib.util
import inspect
import subprocess


def load_storage_class(file_path):
    spec = importlib.util.spec_from_file_location("testat_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "Storage")


def check_docstring(storage_cls):
    methods = ["__init__", "create", "update", "search", "take", "add"]
    for name in methods:
        method = getattr(storage_cls, name, None)
        if not method or not inspect.getdoc(method):
            return 0
    return 1


def check_pep8(file_path):
    try:
        result = subprocess.run(["flake8", file_path], capture_output=True, text=True)
        return 2 if result.returncode == 0 else 0
    except FileNotFoundError:
        print("flake8 not installed. Skipping PEP8 test.")
        return 0


def test_init(storage_cls, temp_dir):
    file1 = pathlib.Path(temp_dir) / "RC0805FR-07100KL.txt"
    file2 = pathlib.Path(temp_dir) / "TPS73033DBVT.txt"
    file1.write_text("count = 100\ndescription=Chip Resistor\n", encoding="utf-8")
    file2.write_text("count=20\nvalue = TPS73033\npackage=SOT-23-5\n", encoding="utf-8")
    s = storage_cls(pathlib.Path(temp_dir))
    data = s._data
    if (
        data.get("RC0805FR-07100KL", {}).get("count") == "100"
        and data.get("TPS73033DBVT", {}).get("value") == "TPS73033"
        and hasattr(s, "_path")
    ):
        return s, 3
    return s, 0


def test_create(storage_cls, s):
    try:
        result = s.create("150080VS7500", {"count": 25, "value": "green", "price": 0.18})
        if result != True:
            return 0
        part = s._data.get("150080VS7500")
        if not part or part["count"] != "25" or part["value"] != "green":
            return 0
        result = s.create("150080VS7500", {"count": 100}, overwrite=False)
        if result != False:
            return 0
        result = s.create("150080VS7500", {"count": 100}, overwrite=True)
        if result != True or s._data["150080VS7500"]["count"] != "100":
            return 0
        return 3
    except Exception:
        return 0


def test_update(storage_cls, s):
    try:
        s.create("TPS73033DBVT", {"count": 20, "price": 0.81})
        s.update("TPS73033DBVT", {"package": "SOT-23-5"})
        if s._data["TPS73033DBVT"]["package"] != "SOT-23-5":
            return 0
        try:
            s.update("XYZ_NOT_EXIST", {"value": "fail"})
            return 0
        except KeyError:
            return 3
    except Exception:
        return 0


def test_search(storage_cls, s):
    try:
        s.create("BAT54S", {"count": 20, "price": 0.1, "package": "SOT-23-5"})
        exact = s.search(part_number="BAT54S")
        if not exact or exact["package"] != "SOT-23-5":
            return 0
        attr = s.search(attributes={"package": "SOT-23-5"})
        if "BAT54S" not in attr:
            return 0
        all_parts = s.search()
        if len(all_parts) < 3:
            return 0
        none_match = s.search(attributes={"value": "XXX"})
        if none_match is not None:
            return 0
        return 3
    except Exception:
        return 0


def test_take(storage_cls, s):
    try:
        s.create("RC0805FR-07100KL", {"count": 100})
        s.create("TPS73033DBVT", {"count": 20})
        result = s.take({"TPS73033DBVT": 5, "RC0805FR-07100KL": 2})
        if result is not None:
            return 0
        result2 = s.take({"TPS73033DBVT": 50, "RC0805FR-07100KL": 2})
        if result2 != {"TPS73033DBVT": -35}:
            return 0
        result3 = s.take({"NOT_EXIST": 5})
        if result3 != {"NOT_EXIST": -5}:
            return 0
        return 2
    except Exception:
        return 0


def test_add(storage_cls, s):
    try:
        s.create("RC0805FR-07100KL", {"count": 100})
        result = s.add({"RC0805FR-07100KL": 30})
        if result is not None or s._data["RC0805FR-07100KL"]["count"] != "130":
            return 0
        result2 = s.add({"HSMC-C190": 10, "PS1240P02BT": 15})
        if result2 != {"HSMC-C190": 10, "PS1240P02BT": 15}:
            return 0
        result3 = s.add({"HSMC-C190": 10, "RC0805FR-07100KL": 5})
        if result3 != {"HSMC-C190": 10}:
            return 0
        return 2
    except Exception:
        return 0


def run_all_tests(file_path):
    results = []
    Storage = load_storage_class(file_path)

    results.append(("T201 - Docstrings", check_docstring(Storage), 1))
    results.append(("T202 - PEP8", check_pep8(file_path), 2))

    temp_dir = tempfile.mkdtemp()
    try:
        s, pts = test_init(Storage, temp_dir)
        results.append(("T411–T414 - __init__", pts, 3))
        results.append(("T421–T424 - create()", test_create(Storage, s), 3))
        results.append(("T431–T434 - update()", test_update(Storage, s), 3))
        results.append(("T441–T444 - search()", test_search(Storage, s), 3))
        results.append(("T451–T454 - take()", test_take(Storage, s), 2))
        results.append(("T461–T463 - add()", test_add(Storage, s), 2))
    finally:
        shutil.rmtree(temp_dir)

    return results


def main():
    filename = input("Enter your Python filename (e.g., testat_name.py): ")
    if not os.path.isfile(filename):
        print("❌ File not found.")
        return

    results = run_all_tests(filename)
    total_score = sum(score for _, score, _ in results)
    max_score = sum(max_pts for _, _, max_pts in results)

    print("\n===== TEST RESULTS =====")
    for name, score, max_pts in results:
        print(f"{name}: {score}/{max_pts} pts")

    print("\n=========================")
    print(f"✅ TOTAL SCORE: {total_score}/{max_score} pts")
    if total_score >= max_score * 0.4:
        print("🟢 Passed (≥ 40%) — Eligible for module exam.")
    else:
        print("🔴 Failed (< 40%) — Not eligible for module exam.")
    print("=========================")


if __name__ == "__main__":
    main()
