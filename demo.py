from pathlib import Path

from compass_lib.parser import CompassParser

# flake8: noqa

if __name__ == "__main__":
    paths = [
        "./tests/artifacts/1998.dat",
        "./tests/artifacts/flags.dat",
        "./tests/artifacts/fulford.dat",
        "./tests/artifacts/fulsurf.dat",
        "./tests/artifacts/random.dat",
        "./tests/artifacts/unicode.dat",
    ]

    for fp in paths:
        compass_file = Path(fp)
        print(
            f"--------------------------- {compass_file} ----------------------------"
        )
        parser = CompassParser(compass_file)

        # print(parser)
        # print(f"{parser.shots=}")
        # print(f"{parser.sections=}")
        # print(f"{parser.filepath=}")
        # print(f"{parser.filetype=}")
        # print(f"{parser.to_json()=}")
        # print(f"{parser.data=}")
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
        data = parser.to_dat(filepath="export.dat")

        parser = CompassParser("export.dat")
        data = parser.to_dat(filepath="export2.dat")

        input("awaiting ...")
