# capturemodeltools
Simple proof of concept tools for working with annotation studio capture models.

Takes a capture model (which can be multi-level, and nested) provided as a CSV and rendered that CSV as JSON which can be imported directly into Omeka S using the Capture Model Importer module.

###Installation

```
pip install -r requirements.txt
```

(can be run in a virtualenv)

### Usage:

```
        python gen_json.py -i monkeys.csv -o monkeys.json -b http://www.example.com/monkeys
```

Or, to generate the WW1 capture model, as JSON:

```
        python gen_json.py -i nlw_ww1.csv -o nlw_ww1.json -b http://nlw-omeka.digtest.co.uk -t 2
```

### Command line args:

```'-i', '--input', help='Input CSV file name', required=True```

Path to the CSV that contains the capture model you wish to turn into JSON.

```'-o', '--output', help='Output JSON file name', required=True```

Filename for the JSON file you want to output.

```'-b', '--url_base', help='Base url for the Omeka instance', required=False```

Base URL for Omeka S installation. Used in the URIs in the capture model. For example: http://nlw-omeka.digtest.co.uk

```'-t', '--top_index', help='Numbered element to treat as the top level group', required=False```

Numbered row in the CSV to treat as the top level in the capture model. Defaults to 1.

