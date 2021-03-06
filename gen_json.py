import os
import urllib
# noinspection PyCompatibility
import urlparse
import argparse
import yaml
import requests
import logging
import json
from jinja2 import Template
from collections import OrderedDict
import unicodecsv as csv


def get_uri(uri):
    """
    Get text from a URI
    :param uri: uri (can be file://, or http(s)://
    :return: text or None
    """
    if uri.startswith('file://'):
        f = urllib.url2pathname(urlparse.urlparse(uri).path)
        if os.access(f, os.R_OK):
            with open(f) as file_f:
                text = file_f.read()
                return text
        else:
            logging.warning('WARNING Cannot read: %s', uri)
            return None
    elif uri.startswith(('http://', 'https://')):
        r = requests.get(uri)
        if r.status_code == requests.codes.ok:
            text = r.text
            return text
        else:
            logging.warning('WARNING Cannot retrieve: %s', uri)
            return None
    else:
        logging.warning('WARNING Do not recognise requests of type: %s', uri)
        return None


def yaml_at(yaml_str):
    """
    Quote escape fields with @s in Yaml
    :param yaml_str: yaml as string
    :return: yaml as string or None
    """
    at_fields = ['@value', '@id', '@context', '@type']
    if yaml_str:
        for a in at_fields:
            repl = '"' + a + '"'
            yaml_str = yaml_str.replace(a, repl)
        return yaml_str
    else:
        return None


def read_yaml(yaml_uri, clean=False):
    """
    Read YAML from a URI, and optionally clean @ fields.
    :param clean:
    :param yaml_uri: uri
    :return: python object
    """
    if yaml_uri:
        yaml_str = get_uri(yaml_uri)
        if clean:
            yaml_str = yaml_at(yaml_str)
        return yaml_str
    else:
        return None


def yaml_d(yaml_str):
    """
    Yaml to python object
    :param yaml_str: yaml as string
    :return: python obj
    """
    if yaml_str:
        d = yaml.load(yaml_str, Loader=yaml.BaseLoader)
        return d
    else:
        return None


def template_element(dct, url, elem_t, irc_t, u_t):
    """
    Run an element dictionary through the element Jinja template to generate JSON.

    :param url: base url for the server
    :param elem_t:
    :param irc_t:
    :param u_t:
    :param dct: dictionary to process
    :return: json string from template.
    """
    with open('cs_element.jt', 'r') as f:
        t = f.read()
        if dct['input_options']:  # for drop-downs.
            dct['input_options'] = json.dumps([x.strip() for x in dct['input_options'].split(';')])
        dct['url'] = url
        dct['element_t'] = elem_t
        dct['irclass_t'] = irc_t
        dct['user'] = u_t
        template = Template(t)
        return template.render(dct)


def template_group(dct, url, grp_t, elem_t, irc_t, u_t, nlw_c, ida_c):
    """
    Run a group dictionary through the group Jinja template to generate JSON.

    :param elem_t:
    :param grp_t:
    :param irc_t:
    :param nlw_c:
    :param ida_c:
    :param u_t:
    :param url: base url for the server
    :param dct: dictionary to process
    :param context: boolean to set whether to include the @context in the JSON.
    :return: json string from template.
    """
    with open('cs_group.jt', 'r') as f:
        t = f.read()
        dct['url'] = url
        dct['group_t'] = grp_t
        dct['element_t'] = elem_t
        dct['irclass_t'] = irc_t
        dct['user'] = u_t
        dct['nlw_context'] = nlw_c
        dct['ida_context'] = ida_c
        template = Template(t)
        return template.render(dct)  # json.loads(template.render(dct))


def process_group(top_level, groupss, elemss, url_b, group_t, element_t, ir_c, u):
    """
    Recursively process a capture model group.

    :param url_b: base url for the server
    :param top_level: top level group
    :param groupss: group level rows
    :param elemss: element level rows
    :param u: Omeka User ID
    :param ida_c: Boolean, use IDA context.
    :param group_t: ID for group resource template
    :param element_t: ID for element resource template.
    :param ir_c: ID for the Interactive Resource class
    :return: top_level row with parts
    """
    parts = top_level['parts'].split(';')
    group_parts = [x for x in groupss if x['running_no'] in parts]
    element_parts = [x for x in elemss if x['running_no'] in parts]
    if group_parts:
        top_level['has_parts'] = json.dumps(
            [json.loads(template_group(process_group(top_level=g, groupss=groupss, elemss=elemss, url_b=url_b,
                                                     group_t=group_t, element_t=element_t, ir_c=ir_c, u=u
                                                     ),
                                       url=url_b, grp_t=group_t, elem_t=element_t, irc_t=ir_c, u_t=u,
                                       ida_c=False, nlw_c=False))
             for g in group_parts])
    elif element_parts:
        top_level['has_parts'] = json.dumps([json.loads(template_element(item, url=url_b, elem_t=element_t, irc_t=ir_c,
                                                                         u_t=u))
                                             for item in element_parts])
    else:
        pass
    return top_level


def csv_load(csv_file, url_base, group, element, irclass, user, top_index='1', delimiter='|', ida_context=False):
    """
    Load a CSV file and return formatted JSON. Defaults to assuming a pipe-delimited CSV file.

    top_index sets the numbered row in the CSV (using the running_no column) to treat as the top-level group.

    N.B. does no validation of the input.

    :param csv_file: the CSV file to open.
    :param url_base: the base for the Omeka server, e.g. 'http://nlw-omeka.digtest.co.uk'
    :param group: the Omeka ID number for the Crowd Source Group resource template
    :param element: the Omeka ID number for the Crowd Source Element resource template
    :param top_index: numbered row to treat as the top level group in the capture model
    :param user: Omeka User ID.
    :param irclass: Omeka ID for the Interactive resource class
    :param delimiter: the delimiter for the CSV, defaults to pipe '|'
    :return: json suitable for import into Omeka via the capture model importer module.
    """
    if ida_context:
        nlw_context = False
    else:
        nlw_context = True
    with open(csv_file, 'r') as csv_in:
        rows = list(csv.DictReader(csv_in, delimiter=delimiter))
        groups = [row for row in rows if row['type'] == 'group']
        elements = [row for row in rows if row['type'] == 'element']
        top = [t for t in groups if t['running_no'] == top_index][0]
        group_dict = json.loads(
            template_group((process_group(top_level=top, groupss=groups, elemss=elements, url_b=url_base,
                                          group_t=group, element_t=element, ir_c=irclass, u=user)),
                           nlw_c=nlw_context, ida_c=ida_context,
                           url=url_base, grp_t=group, elem_t=element, irc_t=irclass, u_t=user))
        group_json = json.dumps(group_dict)
        group_json = group_json.replace('TRUE', 'True').replace('FALSE', 'False')  # fix case on Booleans
        return json.loads(group_json)


def csv_gen(csv_file, delimiter='|'):
    """
    Generate an empty CSV file for creating capture model.
    :param csv_file: filename to write to
    :param delimiter: delimiter for CSV, defaults to pipe '|'.
    """
    all_fields = OrderedDict([
        ('running_no', None),
        ('type', None),
        ('parts', None),
        ('title', None),
        ('label', None),
        ('description', None),
        ('conforms_to', None),
        ('input_type', None),
        ('input_options', None),
        ('input_range', None),
        ('selector_type', None),
        ('selector_value', None),
        ('purpose', None),
        ('motivation', None),
        ('body_format', None),
        ('body_type', None),
        ('required', None),
        ('derived_anno_combine', None),
        ('derived_anno_externalize', None),
        ('derived_anno_humanreadable', None),
        ('derived_anno_serialize', None),
        ('ui_choice', None),
        ('ui_multiple', None),
        ('ui_hidden', None),
        ('ui_group', None),
        ('ui_formgroup', None),
        ('body_label_parts', None)
        ('ui_component', None)

    ])
    with open(csv_file, 'w') as csv_out:
        dw = csv.DictWriter(
            csv_out, delimiter=delimiter, fieldnames=all_fields)
        dw.writeheader()


def main():
    """
    Initialise logging.

    Parse args.

    Write JSON.

    For example:

        python gen_json.py -i monkeys.csv -o monkeys.json -b http://www.example.com/monkeys

    Or, to generate the WW1 capture model, as JSON:

        python gen_json.py -i nlw_ww1.csv -o nlw_ww1.json -b http://nlw-omeka.digtest.co.uk -t 2

    :return: None
    """
    logging.basicConfig(filename='capture_model.log', level=logging.DEBUG)
    parser = argparse.ArgumentParser(description='Simple CSV to JSON tool for annotation studio capture models.')
    parser.add_argument('-i', '--input', help='Input CSV file name', required=True)
    parser.add_argument('-o', '--output', help='Output JSON file name', required=True)
    parser.add_argument('-b', '--url_base', help='Base url for the Omeka instance', required=False)
    parser.add_argument('-t', '--top_index', help='Numbered element to treat as the top level group', required=False)
    parser.add_argument('-g', '--group_id', help='ID for the Crowd Source Group resource template', required=False)
    parser.add_argument('-e', '--element_id', help='ID for the Crowd Source Element resource template', required=False)
    parser.add_argument('-c', '--irclass', help='ID for the Interactive Resource class', required=False)
    parser.add_argument('-u', '--user', help='Omeka User ID for the Owner', required=False)
    parser.add_argument('-x', '--context', help='IDA Context', required=False)
    args = parser.parse_args()
    if not args.url_base:
        args.url_base = 'http://nlw-omeka.digtest.co.uk'
    if not args.irclass:
        args.irclass = 27
    if not args.group_id:
        args.group_id = 5
    if not args.element_id:
        args.element_id = 4
    if not args.user:
        args.user = 2
    if not args.context:
        args.conext = False
    if args.top_index:
        js = csv_load(csv_file=args.input, url_base=args.url_base, top_index=args.top_index, group=args.group_id,
                      element=args.element_id, irclass=args.irclass, user=args.user, ida_context=args.context)
    else:
        js = csv_load(csv_file=args.input, url_base=args.url_base, group=args.group_id,
                      element=args.element_id, irclass=args.irclass, user=args.user, ida_context=args.context)
    if js:
        with open(args.output, 'w') as o:
            json.dump(js, o, indent=4, sort_keys=True)


if __name__ == "__main__":
    main()
