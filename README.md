# yappp
Yet Another Python PNG Parser!

```
usage: yappp.py [-h] [-o OUTFILE] [--ihdr] [--check] [--idat] [--no-idat-data]
                [infile]

positional arguments:
  infile                Input PNG file [stdin]

optional arguments:
  -h, --help            show this help message and exit
  -o OUTFILE, --output OUTFILE
                        Output file [stdout]
  --ihdr                Parse IHDR chunk [false]
  --check               Perform random checks [false]
  --idat                Parse IDAT [false]
  --no-idat-data        Don't output IDAT data [false]
```
