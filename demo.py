from pathlib import Path

from compass_lib.parser import CompassParser

# flake8: noqa: T201 E501

if __name__ == "__main__":
    paths = [
        # "tests/artifacts/synthese-psm_larra/gouffre_z510/Z510_2024_12_31.dat",
        # "tests/artifacts/fountainware/unicode.dat",
        # "tests/artifacts/dlubom/ciekawa/495Cieka.DAT",
        # "tests/artifacts/fountainware/1998.dat"
        # "tests/artifacts/synthese-psm_larra/database_criou/database_criou.dat"
        "tests/artifacts/synthese_clot_daspres/2soeurs_mtc.dat"
    ]
    #     "./tests/artifacts/1998.dat",
    #     "./tests/artifacts/flags.dat",
    #     "./tests/artifacts/fulford.dat",
    #     "./tests/artifacts/fulsurf.dat",
    #     "./tests/artifacts/random.dat",
    #     "./tests/artifacts/unicode.dat",
    # ]

    for fp in sorted(paths):
        _fp = Path(fp)
        if Path("tests/artifacts/invalid_files").resolve() in _fp.resolve().parents:
            continue

        compass_file = Path(fp)
        print(f"# ------------------------ {compass_file} ------------------------#")
        survey = CompassParser.load_dat_file(compass_file)

        survey.to_json(filepath=compass_file.with_suffix(".json"))

        # print(parser)
        # print(f"{parser.shots=}")
        # print(f"{parser.sections=}")
        # print(f"{parser.filepath=}")
        # print(f"{parser.filetype=}")
        # print(f"{parser.to_json()=}")
        # pprint(parser.data.model_dump())
        # print(f"{parser._data=}")
        # print(f"{parser.lstat=}")
        # print(f"{parser.date_created=}")
        # print(f"{parser.date_last_modified=}")
        # print(f"{parser.date_last_opened=}")
        # print(f"{parser.__hash__=}")
        # print(sections.to_json(filepath=fp[:-3] + "json"))
        # print("--------------")
        # activities = parser._data
        # print(type(activities))
        # for activity in activities:
        #     print("==============")
        #     print(len(activity))

        # print(parser.data)
        # parser.to_json(compass_file.parent / compass_file.name.replace(".dat", ".json"))
        # parser.to_dat("test.dat")
        # from pprint import pprint
        # pprint(parser.data.model_dump())
        # data = parser.to_json(include_depth=True)
        # print(data)
        # print(activities[-1])
        # data = parser.to_dat(filepath="export.dat")

        # parser = CompassParser("export.dat")
        # data = parser.to_dat(filepath="export2.dat")

        # input("awaiting ...")
