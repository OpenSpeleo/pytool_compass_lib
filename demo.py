from pathlib import Path

from compass_lib.parser import CompassParser

if __name__ == "__main__":
    paths = [
        # "tests/artifacts/random.dat",
        "tests/artifacts/fulford.dat",
    ]

    for fp in paths:
        compass_file = Path(fp)
        print("-------------------------------------------------------")
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
        # print(f"{parser.hash=}")
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
        from pprint import pprint
        pprint(parser.survey.model_dump())
        # print(activities[-1])
