# Compass Python Lib

Short instructions

```bash
python demo.py
```

--------------------

## Conversion commands:

```bash
# Install in dev mod
pip install -e ".[dev,test]"

# Install latest stable version
pip install compass_lib

# run some commands
compass convert --input_file=./tests/artifacts/fulford.dat  --output_file=fulford.json --format=json --overwrite
compass convert --input_file=./tests/artifacts/random.dat  --output_file=random.json --format=json --overwrite
```
