import os
import tempfile
import shutil
import pathlib
import importlib.util
import inspect
import subprocess


def load_class(file_path, class_name):
    spec = importlib.util.spec_from_file_location("testat_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def check_docstring(storage_cls, bom_cls=None):
    total = 0
    required = 0

    storage_methods = [
        "__init__", "create", "update", "search", "take", "add"
    ]
    for name in storage_methods:
        method = getattr(storage_cls, name, None)
        required += 1
        if method and inspect.getdoc(method):
            total += 1

    if bom_cls:
        bom_methods = ["__init__", "availability"]
        for name in bom_methods:
            method = getattr(bom_cls, name, None)
            required += 1
            if method and inspect.getdoc(method):
                total += 1

    return 1 if total == required else 0


def check_pep8(file_path):
    try:
        result = subprocess.run(["flake8", file_path], capture_output=True, text=True)
        return 2 if result.returncode == 0 else 0
    except FileNotFoundError:
        print("flake8 not installed. Skipping PEP8 test.")
        return 0


def create_sample_bom_csv(csv_path):
    content = """Reference;Value;Description;Package;Part Number;Supplier;Supplier Part Number;Price
C1;1nF;Ceramic Capacitor;0805;0805N102J500CT;Digikey;1292-1591-1-ND;0.1
C2;10nF;Ceramic Capacitor;0805;CL21B103JBANNNC;Digikey;1276-1245-1-ND;0.1
C3;47nF;Ceramic Capacitor;0805;CL21B105KAFNNNE;Digikey;1276-1247-1-ND;0.1
C4;47nF;Ceramic Capacitor;0805;CL21B105KAFNNNE;Digikey;1276-1247-1-ND;0.1
C5;47nF;Ceramic Capacitor;0805;CL21B105KAFNNNE;Digikey;1276-1247-1-ND;0.1
C6;47nF;Ceramic Capacitor;0805;CL21B105KAFNNNE;Digikey;1276-1247-1-ND;0.1
U4;;Linear Voltage Regulator;SOT-23-5;TPS73033DBVT;Digikey;296-27057-1-ND;0.81
"""
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(content)


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


def test_bom_init(bom_cls, csv_path):
    try:
        b = bom_cls(csv_path)
        parts = b._parts
        if "CL21B105KAFNNNE" in parts and sorted(
            parts["CL21B105KAFNNNE"]["reference"]
        ) == ["C3", "C4", "C5", "C6"]:
            return b, 2
    except Exception:
        return None, 0
    return None, 0


def test_bom_availability(bom_cls, b, storage_cls, temp_dir):
    try:
        s = storage_cls(pathlib.Path(temp_dir))
        result = b.availability(storage=s, units=1)
        if "TPS73033DBVT" not in result or "missing" not in result["TPS73033DBVT"]:
            return 0
        _, txt = b.availability(storage=s, units=10, output_text=True)
        if not isinstance(txt, str) or "Part Number" not in txt:
            return 0
        return 3
    except Exception:
        return 0


def run_all_tests(file_path):
    results = []

    try:
        Storage = load_class(file_path, "Storage")
        storage_available = True
    except AttributeError:
        Storage = None
        storage_available = False

    try:
        BOM = load_class(file_path, "BOM")
        bom_available = True
    except AttributeError:
        BOM = None
        bom_available = False

    results.append(("T201 - Docstrings", check_docstring(Storage, BOM), 1))
    results.append(("T202 - PEP8", check_pep8(file_path), 2))

    temp_dir = tempfile.mkdtemp()
    try:
        if storage_available:
            s, pts = test_init(Storage, temp_dir)
            results.append(("T411–T414 - __init__", pts, 3))
            results.append(("T421–T424 - create()", test_create(Storage, s), 3))
            results.append(("T431–T434 - update()", test_update(Storage, s), 3))
            results.append(("T441–T444 - search()", test_search(Storage, s), 3))
            results.append(("T451–T454 - take()", test_take(Storage, s), 2))
            results.append(("T461–T463 - add()", test_add(Storage, s), 2))
        else:
            results.extend([
                ("T411–T414 - __init__", 0, 3),
                ("T421–T424 - create()", 0, 3),
                ("T431–T434 - update()", 0, 3),
                ("T441–T444 - search()", 0, 3),
                ("T451–T454 - take()", 0, 2),
                ("T461–T463 - add()", 0, 2),
            ])

        if bom_available and storage_available:
            csv_path = pathlib.Path(temp_dir) / "stueckliste.csv"
            create_sample_bom_csv(csv_path)
            b, pts_bom_init = test_bom_init(BOM, csv_path)
            results.append(("T511–T515 - BOM.__init__", pts_bom_init, 2))
            pts_bom_avail = test_bom_availability(BOM, b, Storage, temp_dir) if b else 0
            results.append(("T521–T524 - BOM.availability", pts_bom_avail, 3))
        else:
            results.append(("T511–T515 - BOM.__init__", 0, 2))
            results.append(("T521–T524 - BOM.availability", 0, 3))
    finally:
        shutil.rmtree(temp_dir)

    return results


def main():
    filename = input("Enter your Python filename (e.g., testat_Tobia_Rossi.py): ")
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
