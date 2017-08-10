# capturemodeltools
Simple proof of concept tools for working with annotation studio capture models.

Usage:


        python gen_json.py -i monkeys.csv -o monkeys.json -b http://www.example.com/monkeys

Or, to generate the WW1 capture model, as JSON:

        python gen_json.py -i nlw_ww1.csv -o nlw_ww1.json -b http://nlw-omeka.digtest.co.uk -t 2

Command line args:

'-i', '--input', help='Input CSV file name', required=True
'-o', '--output', help='Output JSON file name', required=True
'-b', '--url_base', help='Base url for the Omeka instance', required=False
'-t', '--top_index', help='Numbered element to treat as the top level group', required=False